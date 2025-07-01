import datetime
import os
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes
SCOPES = [
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


def upload_local_video(
    video_path: str,
    title: str,
    description: str,
    publish_at: datetime.datetime | None = None,
    tags: list[str] | None = None,
    category_id: str = "22",
    privacy_status: str = "private",
) -> str:
    """
    Uploads a local video file to YouTube.
    Returns the YouTube video ID.

    Args:
        video_path: Path to the local video file
        title: The YouTube video title
        description: The YouTube video description
        publish_at: A datetime object for the scheduled release (optional)
        tags: List of tags for the video (optional)
        category_id: YouTube category ID (default: "22" for People & Blogs)
        privacy_status: Privacy status ("private", "unlisted", "public")
    """
    # Check if video file exists
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Authenticate
    creds = get_authenticated_creds()

    # Build YouTube client
    youtube = build("youtube", "v3", credentials=creds)

    # Prepare video metadata
    video_metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or ["api", "youtube"],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    # Only set publishAt if scheduling is requested (i.e., publish_at is not None)
    if publish_at is not None:
        # Remove microseconds and ensure RFC3339 format
        publish_at_str = publish_at.replace(microsecond=0).isoformat("T")
        if publish_at_str.endswith("+00:00"):
            publish_at_str = publish_at_str[:-6] + "Z"
        print(f"Setting publish time to: {publish_at_str}")
        video_metadata["status"]["publishAt"] = publish_at_str

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    upload_request = youtube.videos().insert(
        part="snippet,status", body=video_metadata, media_body=media
    )

    response = None
    while response is None:
        status, response = upload_request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    if publish_at is not None:
        print("Video uploaded and scheduled for:", publish_at_str)
    else:
        print("Video uploaded as private (not scheduled)")
    return response["id"]


if __name__ == "__main__":
    try:
        print("Starting YouTube upload process...")
        print("A browser window will open for Google authentication.")
        print("Please complete the authentication and don't close this terminal.")

        # Example usage - replace with your actual video path
        video_path = "/Users/davia/Desktop/experimental.mov"  # Change this to your video file path

        # Set this to True if you want to schedule, False for immediate private upload
        schedule_video = False

        if schedule_video:
            video_id = upload_local_video(
                video_path=video_path,
                title="Test Upload - Local Video",
                description="This is a test upload from a local video file.",
                publish_at=datetime.datetime.now(datetime.UTC)
                + datetime.timedelta(minutes=30),
                privacy_status="private",  # Set to private for testing
            )
        else:
            video_id = upload_local_video(
                video_path=video_path,
                title="Test Upload - Local Video",
                description="This is a test upload from a local video file.",
                publish_at=None,
                privacy_status="private",  # Set to private for testing
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
