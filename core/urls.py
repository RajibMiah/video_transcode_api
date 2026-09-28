from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("api/v1.0/", include("transcoder.urls")),
]
