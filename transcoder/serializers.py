from rest_framework import serializers
from transcoder.models import Stream , StreamVariant
from transcoder.constants import MAX_FILE_SIZE , STREAM_READ_ONLY_FIELDS , MAX_DURATION_SECONDS
from transcoder.utils import  get_mp4_info

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
        if value.size > MAX_FILE_SIZE:
            raise serializers.ValidationError("File too large.")

        info = get_mp4_info(value)
        if info is None or info.brand == b"qt  " or b"vide" not in info.tracks:
            raise serializers.ValidationError("File is not a valid MP4 video.")
        if info.fragmented:
            raise serializers.ValidationError("Fragmented MP4 files are not supported yet.")
        if info.length <= 0:
            raise serializers.ValidationError("Video is empty or corrupt.")
        if info.length > MAX_DURATION_SECONDS:
            raise serializers.ValidationError(f"Video is longer than {MAX_DURATION_SECONDS // 60} minutes.")
        if b"soun" not in info.tracks:
            raise serializers.ValidationError("Videos without an audio track are not supported yet.")
        return value

    def create(self, validated_data):
        validated_data.pop("video_files", None) 
        return super().create(validated_data)
