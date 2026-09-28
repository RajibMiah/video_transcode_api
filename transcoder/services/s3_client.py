import boto3
from django.conf import settings

class S3Client:

    def __init__(self):
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.client = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    def upload_file(self, file, key):
        file.seek(0)
        self.client.upload_fileobj(
            file, self.bucket_name, key,
            ExtraArgs={"ContentType": getattr(file, "content_type", None) or "video/mp4"},
        )
        return f"s3://{self.bucket_name}/{key}"


s3_service_instance = S3Client()