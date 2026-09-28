import json
import os
from django.conf import settings
from django.utils import timezone
from google.cloud.video import transcoder_v1
from transcoder.models import Stream, StreamVariant, StreamStatus
from transcoder.services.gcs_client import gcs_service_instance
from transcoder.services.s3_client import s3_service_instance

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "transcoder_config.json")


def build_job_config(file_prefix):
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    for mux in config["muxStreams"]:
        mux["fileName"] = f"{file_prefix}_{mux['fileName']}"
    return transcoder_v1.types.JobConfig.from_json(json.dumps(config))


class TranscodeTask:

    def __init__(self):
        self.client = transcoder_v1.TranscoderServiceClient()
        self.parent = f"projects/{settings.GCP_PROJECT_ID}/locations/{settings.GCP_LOCATION}"

    def find_job(self, stream_id):
        jobs = self.client.list_jobs(
            request={"parent": self.parent, "filter": f'labels.stream_id="{stream_id}"'}
        )
        return next((j for j in jobs if j.state.name != "FAILED"), None)

    def create_job(self, stream_id, input_uri, output_uri, file_prefix, has_audio=True):
        response = self.find_job(stream_id) or self.client.create_job(
            parent=self.parent,
            job=transcoder_v1.types.Job(
                input_uri=input_uri,
                output_uri=output_uri,
                config=build_job_config(file_prefix, has_audio),
                labels={"stream_id": str(stream_id)},
            ),
        )

        Stream.objects.filter(id=stream_id).update(
            job_name=response.name,
            output_uri=output_uri,
            status=StreamStatus.PROCESSING,
            updated_at=timezone.now(),
        )

    def get_job(self, job_name):
        return self.client.get_job(name=job_name)

    def mark_completed(self, video_id):
        stream = Stream.objects.filter(id=video_id).first()
        if not stream:
            return

        gcs_output_key = stream.output_uri[len(f"gs://{settings.GCS_BUCKET_NAME}/"):]
        gcs_source_key = stream.gcs_uri[len(f"gs://{settings.GCS_BUCKET_NAME}/"):]
        s3_folder = stream.s3_uri[len(f"s3://{settings.AWS_S3_BUCKET_NAME}/"):].rsplit("/", 1)[0] + "/"

        variants_meta = [
            {"resolution": "1080p", "fps": 60, "filename": f"{stream.id}_1080p_60fps_video.mp4"},
            {"resolution": "720p", "fps": 30, "filename": f"{stream.id}_720p_30fps_video.mp4"},
        ]

        for v in variants_meta:
            try:
                with gcs_service_instance.open_reader(f"{gcs_output_key}{v['filename']}") as reader:
                    s3_uri = s3_service_instance.upload_file(reader, f"{s3_folder}{v['filename']}")
            except Exception as exc:
                self.mark_failed(video_id, f"S3 bridge failed for {v['filename']}: {exc}")
                return
            StreamVariant.objects.get_or_create(
                stream=stream,
                resolution=v["resolution"],
                fps=v["fps"],
                defaults={"uri": s3_uri},
            )
            
        gcs_service_instance.delete_files(
            [gcs_source_key] + [f"{gcs_output_key}{v['filename']}" for v in variants_meta]
        )

        stream.status = StreamStatus.COMPLETE
        stream.error = ""
        stream.save()

    def mark_failed(self, video_id, error_message):
        Stream.objects.filter(id=video_id).update(
            status=StreamStatus.FAILED, error=error_message, updated_at=timezone.now()
        )
task_instance = TranscodeTask()