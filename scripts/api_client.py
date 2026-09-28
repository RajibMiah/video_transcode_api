import os
import requests

video_path = "/path/to/your/Desktop/sample.mp4" 

r = requests.post(
    "http://localhost:8000/api/v1.0/stream-transcode/",
    files={"video_files": (os.path.basename(video_path), open(video_path, "rb"), "video/mp4")},
)
print(r.status_code, r.json())