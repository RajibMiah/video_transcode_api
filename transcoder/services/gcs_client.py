import logging
from django.conf import settings
from google.api_core.exceptions import NotFound
from google.cloud import storage

logger = logging.getLogger(__name__)


class GCSClient:

    def __init__(self):
        self.bucket_name = settings.GCS_BUCKET_NAME
        self.bucket = storage.Client().bucket(self.bucket_name)

    def upload_file(self, file, d_path):
        file.seek(0)
        self.bucket.blob(d_path).upload_from_file(file, content_type=getattr(file, "content_type", None))
        return f"gs://{self.bucket_name}/{d_path}"

    def open_reader(self, d_path):
        return self.bucket.blob(d_path).open("rb")

    def delete_files(self, d_paths):
        for d_path in d_paths:
            try:
                self.bucket.blob(d_path).delete()
            except NotFound:
                pass
            except Exception:
                logger.exception("Could not delete gs://%s/%s", self.bucket_name, d_path)


gcs_service_instance = GCSClient()