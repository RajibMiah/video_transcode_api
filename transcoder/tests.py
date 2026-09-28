from unittest.mock import patch
patch( "google.cloud.storage.Client" ).start()
patch( "google.cloud.video.transcoder_v1.TranscoderServiceClient" ).start()

from django.test import override_settings
override_settings( CACHES = { "default" : { "BACKEND" : "django.core.cache.backends.locmem.LocMemCache" } } ).enable()

from django.core.cache import cache
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.throttling import ScopedRateThrottle
from transcoder.models import Stream , StreamStatus

URL = "/api/v1.0/stream-transcode/"
MP4_BYTES = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 64


class UploadAPITest(TestCase):

    def setUp(self):
        cache.clear()

    @patch( "transcoder.views.create_transcode_job" )
    @patch( "transcoder.views.gcs_service_instance" )
    @patch( "transcoder.views.s3_service_instance" )
    def test_new_video_is_uploaded_and_queued(self , s3 , gcs , task):
        s3.upload_file.return_value = "s3://bucket/videos/video.mp4"
        video = SimpleUploadedFile( "video.mp4" , MP4_BYTES , content_type = "video/mp4" )

        with self.captureOnCommitCallbacks( execute = True ):
            response = self.client.post( URL , { "video_files" : video } )

        self.assertEqual( response.status_code , 202 )
        stream = Stream.objects.get( id = response.data["id"] )
        self.assertEqual( stream.status , StreamStatus.QUEUED )
        s3.upload_file.assert_called_once()
        gcs.upload_file.assert_called_once()
        task.delay.assert_called_once_with( str( stream.id ) )

    @patch.object( ScopedRateThrottle , "THROTTLE_RATES" , { "uploads" : "2/hour" } )
    def test_upload_over_limit_returns_429(self):
        upload = lambda: self.client.post( URL , { "video_files" : SimpleUploadedFile( "t.mp4" , b"x" ) } )

        codes = [ upload().status_code for _ in range( 3 ) ]

        self.assertEqual( codes , [ 400 , 400 , 429 ] )
        self.assertIn( "Retry-After" , upload().headers )