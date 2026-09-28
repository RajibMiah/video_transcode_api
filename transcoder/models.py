import uuid
from django.db import models

class StreamStatus(models.TextChoices):
    UPLOADING = "uploading", "Uploading" 
    QUEUED = "queued", "Queued"
    PROCESSING = "processing", "Processing"
    COMPLETE = "complete", "Complete"
    FAILED = "failed", "Failed"

class BaseModel(models.Model):
    id = models.UUIDField( primary_key = True , default = uuid.uuid4 , editable = False)
    created_at = models.DateTimeField( auto_now_add = True )
    updated_at = models.DateTimeField( auto_now = True)

    class Meta:
        abstract = True

class Stream(BaseModel):
    status = models.CharField( max_length = 30 , choices = StreamStatus.choices , db_index = True , default = StreamStatus.QUEUED )
    content_hash = models.CharField( max_length =  64, unique = True, editable = False , blank = True , null = True)
    output_uri = models.CharField(max_length=1024, blank=True, default="")
    gcs_uri = models.CharField(max_length=255, unique=True, null=True, blank=True)
    s3_uri = models.CharField(max_length=255, blank=True, default="")
    job_name = models.CharField( max_length = 255 , unique = True , null = True , blank = True ,  editable = False )
    error = models.TextField(  default = "" , blank = True )

    class Meta:
        ordering = [ "-created_at"]

    def __str__(self):
        return f" Stream :  {self.id}"
    
    @property
    def output_folder(self):
        return self.gcs_uri.rsplit("/", 1)[0] + "/"

class StreamVariant(BaseModel):
    stream = models.ForeignKey( Stream  , on_delete = models.CASCADE , related_name = "variants")
    resolution = models.CharField( max_length=30)
    fps = models.PositiveIntegerField()
    uri = models.CharField( max_length = 255 )

    def __str__(self):
        return f" Stream :  {self.id}"