# Import LinkedIn and YouTube functionality
import datetime

## Davia setup
## supabase setup
import os
from typing import Literal

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from supabase import Client, create_client

from classes import (
    LinkedinPost,
    TwitterPost,
    YouTubeDescription,
)
from linkedin_selenium_poster import LinkedInSeleniumPoster
from promts import post_generation_prompt, youtube_description_prompt
from twitter_selenium_poster import post_tweet
from upload_youtube import upload_local_video

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])


load_dotenv()


def write_linkedin_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    post_date_str: str,
    description: str,
) -> str:
    """Write a LinkedIn post about a given topic"""

    try:
        post_date = datetime.datetime.fromisoformat(post_date_str)
    except ValueError:
        return f"Invalid date format for post_date: {post_date_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)"

    linkedin_posts_supabase = (
        supabase.table("linkedin_posts").select("*").execute().data
    )
    linkedin_posts_supabase = [
        LinkedinPost(
            title=post["title"] if post["title"] is not None else "Untitled Post",
            post=post["post"],
            status=post["status"],
            post_date=str(post.get("post_date")) if post.get("post_date") else None,
        )
        for post in linkedin_posts_supabase
    ]

    post = model.with_structured_output(LinkedinPost).invoke(
        post_generation_prompt.format(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            content_type=content_type,
            goal=goal,
            past_posts=linkedin_posts_supabase,
            description=description,
        )
    )
    post.status = "pending"  # type: ignore

    post_supabase = (
        supabase.table("linkedin_posts")
        .insert(
            {
                "title": post.title,  # type: ignore
                "post": post.post,  # type: ignore
                "created_at": datetime.datetime.now().isoformat(),
                "post_date": post_date.isoformat(),
                "status": "pending",
            }
        )
        .execute()
    )

    return (
        f"LinkedIn post written: {post.title} with id : {post_supabase.data[0]['id']}"  # type: ignore
    )


def write_twitter_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    post_date_str: str,
    description: str,
) -> str:
    """Write a Twitter post about a given topic"""

    try:
        post_date = datetime.datetime.fromisoformat(post_date_str)
    except ValueError:
        return f"Invalid date format for post_date: {post_date_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)"

    twitter_posts_supabase = supabase.table("twitter_posts").select("*").execute().data
    twitter_posts_supabase = [
        TwitterPost(
            post=post["post"],
            posted=post["posted"],
        )
        for post in twitter_posts_supabase
    ]

    post = model.with_structured_output(TwitterPost).invoke(
        post_generation_prompt.format(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            content_type=content_type,
            goal=goal,
            past_posts=twitter_posts_supabase,
            description=description,
        )
    )
    post.posted = False  # type: ignore

    post_supabase = (
        supabase.table("twitter_posts")
        .insert(
            {
                "post": post.post,  # type: ignore
                "created_at": datetime.datetime.now().isoformat(),
                "post_date": post_date.isoformat(),
                "posted": False,
            }
        )
        .execute()
    )

    return f"Twitter post written: {post.post} with id : {post_supabase.data[0]['id']}"  # type: ignore


def write_youtube_description(
    topic: str,
    target_audience: str,
    video_summary: str,
    content_type: str,
    goal: str,
    post_date_str: str,
) -> str:
    """Write a YouTube video description about a given topic"""

    try:
        post_date = datetime.datetime.fromisoformat(post_date_str)
    except ValueError:
        return f"Invalid date format for post_date: {post_date_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)"

    youtube_descriptions_supabase = (
        supabase.table("youtube_descriptions").select("*").execute().data
    )
    youtube_descriptions_supabase = [
        YouTubeDescription(
            title=description["title"]
            if description["title"] is not None
            else "Untitled Description",
            description=description["description"],
            video_url_drive=description.get("video_url_drive") or "",
        )
        for description in youtube_descriptions_supabase
    ]

    description = model.with_structured_output(YouTubeDescription).invoke(
        youtube_description_prompt.format(
            topic=topic,
            target_audience=target_audience,
            content_type=content_type,
            goal=goal,
            video_summary=video_summary,
            past_descriptions=youtube_descriptions_supabase,
        )
    )
    description.posted = False  # type: ignore

    description_supabase = (
        supabase.table("youtube_descriptions")
        .insert(
            {
                "title": description.title,  # type: ignore
                "description": description.description,  # type: ignore
                "video_url_drive": description.video_url_drive,  # type: ignore
                "created_at": datetime.datetime.now().isoformat(),
                "post_date": post_date.isoformat(),
            }
        )
        .execute()
    )

    return f"YouTube description written: {description.title} with id : {description_supabase.data[0]['id']}"  # type: ignore


def post_to_linkedin(
    linkedin_post_id: int,
    visibility: str = "connections",
) -> str:
    """Post content to LinkedIn using Selenium automation. Can schedule posts for later."""

    linkedin_post_supabase = (
        supabase.table("linkedin_posts")
        .select("*")
        .eq("id", linkedin_post_id)
        .execute()
    )
    linkedin_post = LinkedinPost(
        title=linkedin_post_supabase.data[0]["title"],
        post=linkedin_post_supabase.data[0]["post"],
        post_date=str(linkedin_post_supabase.data[0]["post_date"]),
    )

    try:
        # Get LinkedIn credentials from environment
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")

        if not email or not password:
            return "LinkedIn credentials not found. Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables."

        # Initialize LinkedIn poster
        poster = LinkedInSeleniumPoster(headless=False)

        try:
            # Login to LinkedIn
            if poster.login(email, password):
                # Parse schedule time if provided
                schedule_datetime = None
                if linkedin_post.post_date:
                    try:
                        schedule_datetime = datetime.datetime.fromisoformat(
                            linkedin_post.post_date.replace("Z", "+00:00")
                        )
                    except ValueError:
                        return "Invalid date format for schedule_time"

                # Use the new wrapper function to post content
                success = poster.post_linkedin_content(
                    text=linkedin_post.post,
                    schedule_time=schedule_datetime,
                    visibility=visibility,
                )

                if success:
                    if schedule_datetime:
                        result = f"Successfully scheduled LinkedIn post for {schedule_datetime.strftime('%Y-%m-%d %H:%M')} with {visibility} visibility"
                    else:
                        result = f"Successfully posted to LinkedIn with {visibility} visibility"

                    # change the status of the post in supabase to posted
                    supabase.table("linkedin_posts").update({"status": "posted"}).eq(
                        "id", linkedin_post_id
                    ).execute()

                    return "LinkedIn post result: " + result
                else:
                    result = "Failed to post to LinkedIn"
            else:
                result = "Failed to login to LinkedIn"

        finally:
            poster.close()

        return "LinkedIn post result: " + result

    except Exception as e:
        return "Error posting to LinkedIn: " + str(e)


def upload_to_youtube(
    video_id: int,
    channel: Literal["albertthebuilder", "davia"],
    privacy_status: str = "private",
) -> str:
    """Upload a video to YouTube with the given metadata, channel is the channel to upload to it must have been specified by the user before"""

    description_supabase = (
        supabase.table("youtube_videos").select("*").eq("id", video_id).execute()
    )
    youtube_description = YouTubeDescription(
        title=description_supabase.data[0]["title"],
        description=description_supabase.data[0]["description"],
        video_url_drive=description_supabase.data[0]["video_url_drive"],
        post_date=description_supabase.data[0]["post_date"],
    )

    try:
        # Parse publish_at if provided
        publish_datetime = None
        if youtube_description.post_date:
            try:
                publish_datetime = datetime.datetime.fromisoformat(
                    youtube_description.post_date.replace("Z", "+00:00")
                )
            except ValueError:
                return "Invalid date format for publish_at"
        # get the video from supabase

        # Upload the video
        upload_local_video(
            video_path=youtube_description.video_url_drive,
            title=youtube_description.title,
            description=youtube_description.description,
            channel=channel,
            publish_at=publish_datetime,
            privacy_status="private",
            tags=["davia", "ai", "development", "automation"],
        )

        # change the status of the video in supabase to posted
        supabase.table("youtube_videos").update({"status": "posted"}).eq(
            "id", video_id
        ).execute()

        return "Successfully uploaded video id: " + str(video_id)

    except FileNotFoundError:
        return "Video file not found"

    except Exception as e:
        return "Error uploading to YouTube: " + str(e)


def post_to_twitter(
    twitter_post_id: int,
) -> str:
    """Post content to Twitter using Selenium automation. Can schedule posts for later."""

    twitter_post_supabase = (
        supabase.table("twitter_posts").select("*").eq("id", twitter_post_id).execute()
    )
    twitter_post = TwitterPost(
        post=twitter_post_supabase.data[0]["post"],
        posted=twitter_post_supabase.data[0]["posted"],
        post_date=str(twitter_post_supabase.data[0]["post_date"]),
    )

    try:
        # Parse schedule time if provided
        schedule_datetime = None
        if twitter_post.post_date:
            try:
                schedule_datetime = datetime.datetime.fromisoformat(
                    twitter_post.post_date.replace("Z", "+00:00")
                )
            except ValueError:
                return "Invalid date format for schedule_time"

        # Use the post_tweet function to post content
        post_tweet(twitter_post.post, schedule_datetime)

        if schedule_datetime:
            result = f"Successfully scheduled Twitter post for {schedule_datetime.strftime('%Y-%m-%d %H:%M')}"
        else:
            result = "Successfully posted to Twitter"

        # change the status of the post in supabase to posted
        supabase.table("twitter_posts").update({"posted": True}).eq(
            "id", twitter_post_id
        ).execute()

        return "Twitter post result: " + result

    except Exception as e:
        return "Error posting to Twitter: " + str(e)


if __name__ == "__main__":
    print(
        write_youtube_description(
            topic="test, this is only a test write a verrrryyy short post",
            target_audience="no one",
            video_summary="test",
            content_type="test",
            goal="test",
            post_date_str="2025-01-01T00:00:00Z",
        )
    )


def visualise_week_ahead():
    # get all posts from supabase for the next 8 days

    # Calculate date range for next 8 days
    today = datetime.datetime.now().date()
    end_date = today + datetime.timedelta(days=7)

    linkedin_posts_supabase = (
        supabase.table("linkedin_posts")
        .select("*")
        .gte("post_date", today.isoformat())
        .lt("post_date", end_date.isoformat())
        .execute()
        .data
    )
    twitter_posts_supabase = (
        supabase.table("twitter_posts")
        .select("*")
        .gte("post_date", today.isoformat())
        .lt("post_date", end_date.isoformat())
        .execute()
        .data
    )
    youtube_videos_supabase = (
        supabase.table("youtube_descriptions")
        .select("*")
        .gte("post_date", today.isoformat())
        .lt("post_date", end_date.isoformat())
        .execute()
        .data
    )

    # Create a structured visualization with better formatting
    weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]

    print("=" * 80)
    print("📅 WEEK AHEAD CONTENT SCHEDULE")
    print("=" * 80)

    for day in range(7):
        current_date = today + datetime.timedelta(days=day)
        weekday_name = weekdays[current_date.weekday()]

        print(f"\n📆 {weekday_name} ({current_date.strftime('%Y-%m-%d')})")
        print("-" * 50)

        # LinkedIn posts
        linkedin_count = 0
        for post in linkedin_posts_supabase:
            if (
                post["post_date"]
                and datetime.datetime.fromisoformat(post["post_date"]).weekday() == day
            ):
                if linkedin_count == 0:
                    print("🔗 LinkedIn:")
                linkedin_count += 1
                status_emoji = "✅" if post.get("status") == "posted" else "⏳"
                print(f"   {status_emoji} {post['title']}")

        if linkedin_count == 0:
            print("🔗 LinkedIn: No posts scheduled")

        # Twitter posts
        twitter_count = 0
        for post in twitter_posts_supabase:
            if (
                post["post_date"]
                and datetime.datetime.fromisoformat(post["post_date"]).weekday() == day
            ):
                if twitter_count == 0:
                    print("🐦 Twitter:")
                twitter_count += 1
                status_emoji = "✅" if post.get("posted") else "⏳"
                print(f"   {status_emoji} {post.get('title', 'Untitled Tweet')}")

        if twitter_count == 0:
            print("🐦 Twitter: No posts scheduled")

        # YouTube videos
        youtube_count = 0
        for post in youtube_videos_supabase:
            if (
                post["post_date"]
                and datetime.datetime.fromisoformat(post["post_date"]).weekday() == day
            ):
                if youtube_count == 0:
                    print("📺 YouTube:")
                youtube_count += 1
                status_emoji = "✅" if post.get("posted") else "⏳"
                print(f"   {status_emoji} {post['title']}")

        if youtube_count == 0:
            print("📺 YouTube: No videos scheduled")

    print("\n" + "=" * 80)
    print("📊 SUMMARY:")
    print(f"   LinkedIn posts: {len(linkedin_posts_supabase)}")
    print(f"   Twitter posts: {len(twitter_posts_supabase)}")
    print(f"   YouTube videos: {len(youtube_videos_supabase)}")
    print("=" * 80)
