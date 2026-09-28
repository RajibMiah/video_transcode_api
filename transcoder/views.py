import logging
from django.conf import settings
from django.utils import timezone
from rest_framework.response import Response
from django.db import transaction , IntegrityError
from rest_framework.views import APIView
from transcoder.models import Stream, StreamStatus
from rest_framework import status
from transcoder.serializers import StreamSerializer , StreamVariantSerializer
from transcoder.services.gcs_client import gcs_service_instance
from transcoder.services.s3_client import s3_service_instance
from transcoder.tasks import create_transcode_job
from transcoder.utils import get_file_hash, should_retry , get_stream_path

logger = logging.getLogger(__name__)

class StreamAPIView(APIView):
    def post(self, request):
        serialized_data = StreamSerializer(data=request.data)
        serialized_data.is_valid(raise_exception=True)
        stream = serialized_data.validated_data["video_files"]
        file_hash = get_file_hash(stream)

        has_stream = Stream.objects.filter(content_hash=file_hash).first()
        if has_stream:
            if should_retry(has_stream):
                reset = Stream.objects.filter(id=has_stream.id, status=StreamStatus.FAILED).update(
                    status=StreamStatus.QUEUED,
                    job_name=None,
                    output_uri="",
                    error="",
                    updated_at=timezone.now(),
                )
                if reset:
                    transaction.on_commit(lambda: create_transcode_job.delay(str(has_stream.id)))
                has_stream.refresh_from_db()

            data = {"id": str(has_stream.id), "status": has_stream.status, "duplicate": True}
            if has_stream.status == StreamStatus.COMPLETE:
                data["variants"] = StreamVariantSerializer(has_stream.variants.all(), many=True).data
            return Response(data)
        
        stream_id , path = get_stream_path()

        try:
            s3_uri = s3_service_instance.upload_file(stream, path)
        except Exception:
            logger.exception("S3 upload failed for %s ", stream.name)
            return Response(
                {"error": {"message": "Upload failed."}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            gcs_service_instance.upload_file(stream, path)
        except Exception:
            logger.exception("GCS staging upload failed for %s ", stream.name)
            return Response(
                {"error": {"message": "Upload failed."}},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        try:
            with transaction.atomic():
                stream = serialized_data.save(
                        id=stream_id,
                        content_hash=file_hash,
                        s3_uri=s3_uri,
                        gcs_uri=f"gs://{settings.GCS_BUCKET_NAME}/{path}",
                    )
                transaction.on_commit(lambda: create_transcode_job.delay(str(stream_id)))
        except IntegrityError:
            exists = Stream.objects.get(content_hash=file_hash)
            return Response({"id": str(exists.id), "status": exists.status, "duplicate": True})
        except Exception:
            logger.exception("DB save failed for %s", path)
            return Response(
                {"error": {"message": "Internal server error "}},status=status.HTTP_500_INTERNAL_SERVER_ERROR,)
                            
        return Response(
            {"id": str(stream.id), "status": stream.status},
            status=status.HTTP_202_ACCEPTED,
        )