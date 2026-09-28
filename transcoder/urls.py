from django.urls import path
from transcoder.views import StreamAPIView

urlpatterns = [
    path("stream-transcode/", StreamAPIView.as_view(), name = "stream"),
]