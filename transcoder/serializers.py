from rest_framework import serializers
from transcoder.models import Stream , StreamVariant
from transcoder.constants import MAX_FILE_SIZE , STREAM_READ_ONLY_FIELDS
from transcoder.utils import get_file_type , has_audio_track

class StreamVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreamVariant
        fields = "__all__"

class StreamSerializer(serializers.ModelSerializer):
    video_files = serializers.FileField(write_only=True)
    variants = StreamVariantSerializer(many = True , read_only = True)

    class Meta:
        model = Stream
        fields = "__all__"
        read_only_fields = STREAM_READ_ONLY_FIELDS

    def validate_video_files(self, value):
        if not (value.content_type or "").startswith("video/"):
            raise serializers.ValidationError("Invalid content type")
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError("File too large.")

        file_type = get_file_type(value)
        if file_type is None or file_type.mime != "video/mp4":
            raise serializers.ValidationError("File content does not match a valid MP4 format")

        if not has_audio_track(value):
            raise serializers.ValidationError("Videos without an audio track are not supported yet.")
        return value

    def create(self, validated_data):
        validated_data.pop("video_files", None) 
        return super().create(validated_data)
