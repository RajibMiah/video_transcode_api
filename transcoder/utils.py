import hashlib
import uuid
from transcoder.models import StreamStatus
from dataclasses import dataclass
from mutagen import MutagenError
from mutagen.mp4 import Atoms, MP4Info

def get_file_hash(file):
    sha256 = hashlib.sha256()
    for chunk in file.chunks(): 
        sha256.update(chunk)
    file.seek(0)
    return sha256.hexdigest()


def should_retry(stream):
    return stream.status == StreamStatus.FAILED

def get_stream_path():
    stream_id = str(uuid.uuid4()) 
    path = f"videos/{stream_id}/source.mp4"
    return stream_id, path

@dataclass
class Mp4Info:
    brand: bytes
    tracks: set
    length: float
    fragmented: bool


def get_mp4_info(file):
    try:
        file.seek(0)
        atoms = Atoms(file)
        moov = atoms[b"moov"]
        return Mp4Info(
            brand=atoms[b"ftyp"].read(file)[1][:4],
            tracks={t[b"mdia", b"hdlr"].read(file)[1][8:12] for t in moov.findall(b"trak")},
            length=MP4Info(atoms, file).length,
            fragmented=any(a.name == b"mvex" for a in moov.children),
        )
    except (MutagenError, KeyError):
        return None
    finally:
        file.seek(0)