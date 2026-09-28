from unittest.mock import patch
patch( "google.cloud.storage.Client" ).start()
patch( "google.cloud.video.transcoder_v1.TranscoderServiceClient" ).start()

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from transcoder.models import Stream , StreamStatus

MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 64

class UploadAPITest(TestCase):

    @patch( "transcoder.views.create_transcode_job" )
    @patch( "transcoder.views.gcs_service_instance" )
    @patch( "transcoder.views.s3_service_instance" )
    def test_new_video_is_uploaded_and_queued(self , s3 , gcs , task):
        s3.upload_file.return_value = "s3://bucket/videos/video.mp4"
        video = SimpleUploadedFile( "video.mp4" , MP4_BYTES , content_type = "video/mp4" )

        with self.captureOnCommitCallbacks( execute = True ):
            response = self.client.post( "/api/v1.0/stream-transcode/" , { "video_files" : video } )

        self.assertEqual( response.status_code , 202 )
        stream = Stream.objects.get( id = response.data["id"] )
        self.assertEqual( stream.status , StreamStatus.QUEUED )
        s3.upload_file.assert_called_once()
        gcs.upload_file.assert_called_once()
        task.delay.assert_called_once_with( str( stream.id ) )