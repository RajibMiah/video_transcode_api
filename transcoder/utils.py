import hashlib
import uuid
import filetype
from transcoder.models import StreamStatus

def get_file_hash(file):
    sha256 = hashlib.sha256()
    for chunk in file.chunks(): 
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()

def get_file_type(file):
    head = file.read(262)
    file.seek(0)
    return filetype.guess(head)

def should_retry(stream):
    return stream.status == StreamStatus.FAILED

def get_stream_path():
    stream_id = str(uuid.uuid4()) 
    path = f"videos/{stream_id}.mp4"
    return stream_id, path