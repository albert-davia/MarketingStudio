import datetime
import io
import os
import pickle
import re

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/youtube.upload",
]


def get_authenticated_creds():
    """Get authenticated credentials, trying multiple methods."""
    creds = None

    # Try to load existing credentials from token.pickle
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Try different ports for OAuth
            ports = [8080, 8081, 8082, 8083, 8084]

            for port in ports:
                try:
                    print(f"Trying authentication on port {port}...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        "client_secret.json", SCOPES
                    )
                    creds = flow.run_local_server(port=port, prompt="consent")
                    break
                except Exception as e:
                    print(f"Port {port} failed: {str(e)[:100]}...")
                    continue
            else:
                raise Exception(
                    "Could not authenticate on any port. Please check your OAuth configuration."
                )

        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return creds


def extract_drive_file_id(drive_url: str) -> str:
    """Extract the file ID from a Google Drive URL."""
    # Pattern for Google Drive file URLs
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",  # Standard file URL
        r"id=([a-zA-Z0-9_-]+)",  # URL with id parameter
        r"([a-zA-Z0-9_-]{25,})",  # Fallback: any 25+ char alphanumeric string
    ]

    for pattern in patterns:
        match = re.search(pattern, drive_url)
        if match:
            return match.group(1)

    raise ValueError(f"Could not extract file ID from URL: {drive_url}")


def upload_video_from_drive(
    drive_file_id: str,
    title: str,
    description: str,
    publish_at: datetime.datetime | None = None,
    tags: list[str] | None = None,
    category_id: str = "22",
    privacy_status: str = "private",
    temp_filename: str = "temp_video.mp4",
) -> str:
    """
    Downloads a video from Google Drive and uploads it to YouTube.
    Returns the YouTube video ID.

    Args:
        drive_file_id: Either a Google Drive file ID or a full Google Drive URL
        title: The YouTube video title
        description: The YouTube video description
        publish_at: A datetime object for the scheduled release (optional)
        tags: List of tags for the video (optional)
        category_id: YouTube category ID (default: "22" for People & Blogs)
        privacy_status: Privacy status ("private", "unlisted", "public")
        temp_filename: Temporary filename for the downloaded video
    """
    # Extract file ID if a full URL was provided
    if drive_file_id.startswith("http"):
        drive_file_id = extract_drive_file_id(drive_file_id)

    # Authenticate
    creds = get_authenticated_creds()

    # Build Drive and YouTube clients
    drive_service = build("drive", "v3", credentials=creds)
    youtube = build("youtube", "v3", credentials=creds)

    # Download video from Drive
    request = drive_service.files().get_media(fileId=drive_file_id)
    fh = io.FileIO(temp_filename, "wb")
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"Download {int(status.progress() * 100)}%.")

    # Prepare publish time
    if publish_at is None:
        publish_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
            minutes=10
        )
    publish_at_str = publish_at.isoformat("T") + "Z"

    # Prepare video metadata
    video_metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or ["api", "drive", "youtube"],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "publishAt": publish_at_str,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(temp_filename, chunksize=-1, resumable=True)
    upload_request = youtube.videos().insert(
        part="snippet,status", body=video_metadata, media_body=media
    )

    response = None
    while response is None:
        status, response = upload_request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    print("Video uploaded and scheduled for:", publish_at_str)
    return response["id"]


if __name__ == "__main__":
    try:
        print("Starting YouTube upload process...")
        print("A browser window will open for Google authentication.")
        print("Please complete the authentication and don't close this terminal.")

        video_id = upload_video_from_drive(
            drive_file_id="https://drive.google.com/file/d/1J2kNo7YpUvUMJiWyS4_FDaETlGjWtRy3/view?usp=drive_link",
            title="test",
            description="test",
            publish_at=datetime.datetime.now(datetime.UTC)
            + datetime.timedelta(minutes=100),
        )
        print("YouTube Video ID:", video_id)

    except KeyboardInterrupt:
        print("\n❌ Upload cancelled by user.")
        print(
            "To complete the upload, run the script again and complete the authentication."
        )
    except Exception as e:
        print(f"\n❌ Error during upload: {e}")
        print("Please check your credentials and try again.")
