import datetime
import io

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]

# Authenticate
flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=8080)

# Build Drive and YouTube clients
drive_service = build("drive", "v3", credentials=creds)
youtube = build("youtube", "v3", credentials=creds)

# STEP 1 — Download video from Drive
file_id = "YOUR_DRIVE_FILE_ID"  # e.g. '1AbC2D3Ef...'
request = drive_service.files().get_media(fileId=file_id)
fh = io.FileIO("temp_video.mp4", "wb")
downloader = MediaIoBaseDownload(fh, request)

done = False
while not done:
    status, done = downloader.next_chunk()
    print(f"Download {int(status.progress() * 100)}%.")

# STEP 2 — Upload video to YouTube
publish_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

video_metadata = {
    "snippet": {
        "title": "Video from Google Drive",
        "description": "Uploaded via Drive + YouTube API",
        "tags": ["api", "drive", "youtube"],
        "categoryId": "22",
    },
    "status": {
        "privacyStatus": "private",
        "publishAt": publish_at.isoformat("T") + "Z",
        "selfDeclaredMadeForKids": False,
    },
}

media = MediaFileUpload("temp_video.mp4", chunksize=-1, resumable=True)

upload_request = youtube.videos().insert(
    part="snippet,status", body=video_metadata, media_body=media
)

response = None
while response is None:
    status, response = upload_request.next_chunk()
    if status:
        print(f"Uploaded {int(status.progress() * 100)}%")

print("Video uploaded and scheduled for:", publish_at.isoformat())
