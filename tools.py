# Import LinkedIn and YouTube functionality
import datetime

## Davia setup
## supabase setup
import os
from typing import Literal

from davia import Davia
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from supabase import Client, create_client

from classes import (
    LinkedinPost,
    Schedule,
    TwitterPost,
    YouTubeDescription,
)
from linkedin_selenium_poster import LinkedInSeleniumPoster
from promts import post_generation_prompt, schedule_prompt, youtube_description_prompt
from twitter_selenium_poster import post_tweet
from upload_youtube import upload_local_video

load_dotenv()

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

app = Davia("MarketingStudio")


def write_linkedin_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    post_date_str: str,
    description: str,
) -> str:
    """
    Write a LinkedIn post about a given topic and store it in the database.

    This function generates a LinkedIn post using AI based on the provided parameters,
    stores it in the Supabase database with a 'pending' status, and returns a confirmation
    message with the post ID.

    Args:
        topic (str): The main topic or subject of the LinkedIn post
        target_audience (str): The intended audience for the post (e.g., "builders who don't want to code")
        platform (str): The social media platform (should be "linkedin")
        content_type (str): Type of content being created (e.g., "linkedin post")
        goal (str): The objective of the post (e.g., "get clicks on the post")
        post_date_str (str): Scheduled posting date in ISO format (YYYY-MM-DDTHH:MM:SS)
        description (str): Additional description or context for the post content

    Returns:
        str: Confirmation message with post title and database ID

    Raises:
        ValueError: If the post_date_str is not in valid ISO format

    Example:
        >>> write_linkedin_post(
        ...     topic="AI Automation",
        ...     target_audience="developers",
        ...     platform="linkedin",
        ...     content_type="linkedin post",
        ...     goal="generate leads",
        ...     post_date_str="2024-01-15T10:00:00",
        ...     description="How AI can automate repetitive tasks"
        ... )
        "LinkedIn post written: AI Automation Guide with id : 123"
    """

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
    """
    Write a Twitter post about a given topic and store it in the database.

    This function generates a Twitter post using AI based on the provided parameters,
    stores it in the Supabase database with a 'pending' status, and returns a confirmation
    message with the post ID. The function considers past Twitter posts to maintain
    content consistency and avoid repetition.

    Args:
        topic (str): The main topic or subject of the Twitter post
        target_audience (str): The intended audience for the post (e.g., "builders who don't want to code")
        platform (str): The social media platform (should be "twitter")
        content_type (str): Type of content being created (e.g., "twitter post")
        goal (str): The objective of the post (e.g., "get clicks on the post")
        post_date_str (str): Scheduled posting date in ISO format (YYYY-MM-DDTHH:MM:SS)
        description (str): Additional description or context for the post content

    Returns:
        str: Confirmation message with post content preview and database ID

    Raises:
        ValueError: If the post_date_str is not in valid ISO format

    Example:
        >>> write_twitter_post(
        ...     topic="No-Code Tools",
        ...     target_audience="entrepreneurs",
        ...     platform="twitter",
        ...     content_type="twitter post",
        ...     goal="drive engagement",
        ...     post_date_str="2024-01-15T14:30:00",
        ...     description="Top no-code platforms for 2024"
        ... )
        "Twitter post written: Discover the best no-code tools... with id : 456"
    """

    try:
        post_date = datetime.datetime.fromisoformat(post_date_str)
    except ValueError:
        return f"Invalid date format for post_date: {post_date_str}. Use ISO format (YYYY-MM-DDTHH:MM:SS)"

    twitter_posts_supabase = supabase.table("twitter_posts").select("*").execute().data
    twitter_posts_supabase = [
        TwitterPost(
            post=post["post"],
            status=post["status"],
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
        + "The post should have a maximum of 280 characters"
    )
    post.status = "pending"  # type: ignore

    post_supabase = (
        supabase.table("twitter_posts")
        .insert(
            {
                "post": post.post,  # type: ignore
                "created_at": datetime.datetime.now().isoformat(),
                "post_date": post_date.isoformat(),
                "status": "pending",
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
    """
    Write a YouTube video description about a given topic and store it in the database.

    This function generates a YouTube video description using AI based on the provided parameters,
    including a title and detailed description. It stores the metadata in the Supabase database
    with a 'pending' status and returns a confirmation message with the description ID.

    Args:
        topic (str): The main topic or subject of the YouTube video
        target_audience (str): The intended audience for the video (e.g., "builders who don't want to code")
        video_summary (str): A summary of the video content to help generate relevant description
        content_type (str): Type of content being created (e.g., "youtube description")
        goal (str): The objective of the video (e.g., "Get the most views on youtube")
        post_date_str (str): Scheduled publishing date in ISO format (YYYY-MM-DDTHH:MM:SS)

    Returns:
        str: Confirmation message with video title and database ID

    Raises:
        ValueError: If the post_date_str is not in valid ISO format

    Example:
        >>> write_youtube_description(
        ...     topic="Building SaaS with No-Code",
        ...     target_audience="startup founders",
        ...     video_summary="Complete tutorial on building a SaaS product using Bubble",
        ...     content_type="youtube description",
        ...     goal="maximize views and subscriptions",
        ...     post_date_str="2024-01-15T18:00:00"
        ... )
        "YouTube description written: How to Build a SaaS with No-Code with id : 789"
    """

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
    description.status = "pending"  # type: ignore

    description_supabase = (
        supabase.table("youtube_descriptions")
        .insert(
            {
                "title": description.title,  # type: ignore
                "description": description.description,  # type: ignore
                "video_url_drive": description.video_url_drive,  # type: ignore
                "created_at": datetime.datetime.now().isoformat(),
                "post_date": post_date.isoformat(),
                "status": "pending",
            }
        )
        .execute()
    )

    return f"YouTube description written: {description.title} with id : {description_supabase.data[0]['id']}"  # type: ignore


@app.task
def post_to_linkedin(
    linkedin_post_id: int,
    visibility: str = "connections",
) -> str:
    """
    Post content to LinkedIn using Selenium automation with optional scheduling.

    This function retrieves a LinkedIn post from the database by ID, logs into LinkedIn
    using Selenium automation, and either posts immediately or schedules the post for
    a later time. The post status is updated to 'posted' upon successful completion.

    Args:
        linkedin_post_id (int): The database ID of the LinkedIn post to publish
        visibility (str, optional): Post visibility setting. Defaults to "connections".
                                  Options: "connections", "public", "group"

    Returns:
        str: Status message indicating success or failure of the posting operation

    Raises:
        Exception: If there are issues with LinkedIn login, posting, or database operations

    Environment Variables:
        LINKEDIN_EMAIL: LinkedIn account email address
        LINKEDIN_PASSWORD: LinkedIn account password

    Example:
        >>> post_to_linkedin(linkedin_post_id=123, visibility="public")
        "LinkedIn post result: Successfully posted to LinkedIn with public visibility"

    Note:
        - Requires valid LinkedIn credentials in environment variables
        - Uses Selenium with headless=False for debugging purposes
        - Automatically updates post status in database upon successful posting
    """

    print(linkedin_post_id, visibility)

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
                    text=linkedin_post.post or "",
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


@app.task
def upload_to_youtube(
    video_id: int,
    channel: Literal["albertthebuilder", "davia"],
    privacy_status: str = "private",
) -> str:
    """
    Upload a video to YouTube with metadata from the database.

    This function retrieves video metadata (title, description, file path) from the database
    using the provided video_id, then uploads the video to the specified YouTube channel
    with the given privacy settings. The video status is updated to 'posted' upon successful upload.

    Args:
        video_id (int): The database ID of the video to upload
        channel (Literal["albertthebuilder", "davia"]): The YouTube channel to upload to.
                                                       Must be one of the specified channels.
        privacy_status (str, optional): Video privacy setting. Defaults to "private".
                                       Options: "private", "unlisted", "public"

    Returns:
        str: Status message indicating success or failure of the upload operation

    Raises:
        FileNotFoundError: If the video file specified in the database cannot be found
        Exception: If there are issues with YouTube upload or database operations

    Example:
        >>> upload_to_youtube(video_id=456, channel="davia", privacy_status="private")
        "Successfully uploaded video id: 456"

    Note:
        - Video file path must be accessible from the system
        - Automatically adds default tags: ["davia", "ai", "development", "automation"]
        - Updates video status in database upon successful upload
        - Supports scheduled publishing if post_date is set in the database
    """

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
            video_path=youtube_description.video_url_drive or "",
            title=youtube_description.title or "",
            description=youtube_description.description or "",
            channel=channel,
            publish_at=publish_datetime,
            privacy_status="private",
            tags=["davia", "ai", "development", "automation"],
        )

        # change the status of the video in supabase to posted
        supabase.table("youtube_descriptions").update({"status": "posted"}).eq(
            "id", video_id
        ).execute()

        return "Successfully uploaded video id: " + str(video_id)

    except FileNotFoundError:
        return "Video file not found"

    except Exception as e:
        return "Error uploading to YouTube: " + str(e)


@app.task
def post_to_twitter(
    twitter_post_id: int,
) -> str:
    """
    Post content to Twitter using Selenium automation with optional scheduling.

    This function retrieves a Twitter post from the database by ID and publishes it
    to Twitter either immediately or at a scheduled time. The post status is updated
    to 'posted' upon successful completion.

    Args:
        twitter_post_id (int): The database ID of the Twitter post to publish

    Returns:
        str: Status message indicating success or failure of the posting operation

    Raises:
        Exception: If there are issues with Twitter posting or database operations

    Example:
        >>> post_to_twitter(twitter_post_id=789)
        "Twitter post result: Successfully posted to Twitter"

    Note:
        - Uses the post_tweet function from twitter_selenium_poster module
        - Supports scheduled posting if post_date is set in the database
        - Automatically updates post status in database upon successful posting
        - Handles timezone conversion for scheduled posts
    """

    twitter_post_supabase = (
        supabase.table("twitter_posts").select("*").eq("id", twitter_post_id).execute()
    )
    twitter_post = TwitterPost(
        post=twitter_post_supabase.data[0]["post"],
        status=twitter_post_supabase.data[0]["status"],
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
        post_tweet(twitter_post.post or "", schedule_datetime)

        if schedule_datetime:
            result = f"Successfully scheduled Twitter post for {schedule_datetime.strftime('%Y-%m-%d %H:%M')}"
        else:
            result = "Successfully posted to Twitter"

        # change the status of the post in supabase to posted
        supabase.table("twitter_posts").update({"status": "posted"}).eq(
            "id", twitter_post_id
        ).execute()

        return "Twitter post result: " + result

    except Exception as e:
        return "Error posting to Twitter: " + str(e)


def visualise_week_ahead():
    """
    Display a comprehensive weekly content schedule for the next 7 days.

    This function retrieves all scheduled posts (LinkedIn, Twitter, YouTube) for the
    upcoming week and presents them in a formatted, easy-to-read schedule. It shows
    content organized by day of the week with status indicators and summary statistics.

    The visualization includes:
    - Daily breakdown with weekday names and dates
    - LinkedIn posts with titles and status
    - Twitter posts with status indicators
    - YouTube videos with titles and status
    - Summary statistics for the week

    Returns:
        None: Prints the schedule directly to console

    Example Output:
        ================================================================================
        📅 WEEK AHEAD CONTENT SCHEDULE
        ================================================================================

        📆 Monday (2024-01-15)
        --------------------------------------------------
        🔗 LinkedIn: ✅ AI Automation Guide
        🐦 Twitter: ⏳ No-Code Tools Thread
        📺 YouTube: ⏳ Building SaaS Tutorial

        📊 SUMMARY:
           LinkedIn posts: 3
           Twitter posts: 3
           YouTube videos: 2
        ================================================================================

    Note:
        - Shows content for exactly 7 days starting from today
        - Status indicators: ✅ for posted, ⏳ for pending
        - Handles cases where no content is scheduled for a particular day
        - Uses emojis and formatting for better readability
    """

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


@app.task
def get_all_posts_for_next_week() -> tuple[
    list[LinkedinPost], list[TwitterPost], list[YouTubeDescription]
]:
    """
    Retrieve all scheduled posts for the next 7 days from the database.

    This function queries the database for all LinkedIn posts, Twitter posts, and
    YouTube descriptions that are scheduled to be published within the next week
    (7 days from today). Returns the data as structured objects for programmatic use.

    Returns:
        tuple[list[LinkedinPost], list[TwitterPost], list[YouTubeDescription]]:
            A tuple containing three lists:
            - List of LinkedinPost objects for the next week
            - List of TwitterPost objects for the next week
            - List of YouTubeDescription objects for the next week

    Example:
        >>> linkedin_posts, twitter_posts, youtube_posts = get_all_posts_for_next_week()
        >>> print(f"Found {len(linkedin_posts)} LinkedIn posts for next week")
        "Found 3 LinkedIn posts for next week"

    Note:
        - Date range: from today (inclusive) to 7 days from today (exclusive)
        - Returns empty lists if no content is scheduled for the period
        - All returned objects are properly typed with their respective classes
        - Useful for programmatic content management and analysis
    """
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

    return (
        [LinkedinPost(**post) for post in linkedin_posts_supabase],
        [TwitterPost(**post) for post in twitter_posts_supabase],
        [YouTubeDescription(**post) for post in youtube_videos_supabase],
    )


@app.task
def get_all_posts():
    """
    Retrieve all posts from the database regardless of date.

    This function queries the database for all LinkedIn posts, Twitter posts, and
    YouTube descriptions that exist in the system, regardless of their scheduled
    date or current status. Returns the data as structured objects for analysis
    or management purposes.

    Returns:
        tuple[list[LinkedinPost], list[TwitterPost], list[YouTubeDescription]]:
            A tuple containing three lists:
            - List of all LinkedinPost objects in the database
            - List of all TwitterPost objects in the database
            - List of all YouTubeDescription objects in the database

    Example:
        >>> linkedin_posts, twitter_posts, youtube_posts = get_all_posts()
        >>> print(f"Total posts in system: {len(linkedin_posts) + len(twitter_posts) + len(youtube_posts)}")
        "Total posts in system: 45"

    Note:
        - Returns ALL posts in the database, not just recent or scheduled ones
        - Useful for content analysis, reporting, or bulk operations
        - All returned objects are properly typed with their respective classes
        - Can be resource-intensive for large datasets
    """
    linkedin_posts_supabase = (
        supabase.table("linkedin_posts").select("*").execute().data
    )
    twitter_posts_supabase = supabase.table("twitter_posts").select("*").execute().data
    youtube_videos_supabase = (
        supabase.table("youtube_descriptions").select("*").execute().data
    )

    return (
        [LinkedinPost(**post) for post in linkedin_posts_supabase],
        [TwitterPost(**post) for post in twitter_posts_supabase],
        [YouTubeDescription(**post) for post in youtube_videos_supabase],
    )


@app.task
def schedule_for_next_week(user_prompt: str):
    """
    Automatically generate and schedule content for the next week based on user input.

    This function uses AI to generate a content schedule for the upcoming week based on
    the user's prompt. It creates content for Monday, Wednesday, and Friday across all
    platforms (LinkedIn, Twitter, YouTube) and schedules them automatically. The AI
    generates topics, descriptions, and video summaries that align with the user's goals.

    Args:
        user_prompt (str): A description of the content theme, goals, or topics for the week.
                          This guides the AI in generating relevant content across all platforms.

    Returns:
        str: Confirmation message indicating successful scheduling

    Example:
        >>> schedule_for_next_week("Focus on no-code tools and automation for entrepreneurs")
        "Content scheduled for the next week"

    Generated Content:
        For each day (Monday, Wednesday, Friday), the function creates:
        - LinkedIn post with topic and description
        - Twitter post with the same topic and description
        - YouTube description with topic and video summary

    Target Audience:
        All content is automatically targeted to "builders who don't want to code"

    Goals:
        - LinkedIn/Twitter: "get clicks on the post"
        - YouTube: "Get the most views on youtube"

    Note:
        - Uses AI model to generate coherent content themes across the week
        - Automatically calculates the next Monday, Wednesday, and Friday dates
        - Creates content for all three platforms simultaneously
        - All posts are stored with 'pending' status for later review/posting
    """
    response = model.with_structured_output(Schedule).invoke(
        schedule_prompt.format(user_prompt=user_prompt)
    )

    today = datetime.datetime.now().date()
    day_of_week = today.weekday()
    monday = today + datetime.timedelta(days=abs(0 - day_of_week))
    wednesday = today + datetime.timedelta(days=abs(2 - day_of_week))
    friday = today + datetime.timedelta(days=abs(4 - day_of_week))

    topics = [
        (
            response.topic_for_monday,  # type: ignore
            response.description_for_monday,  # type: ignore
            response.video_description_for_monday,  # type: ignore
            monday,
        ),
        (
            response.topic_for_wednesday,  # type: ignore
            response.description_for_wednesday,  # type: ignore
            response.video_description_for_wednesday,  # type: ignore
            wednesday,
        ),
        (
            response.topic_for_friday,  # type: ignore
            response.description_for_friday,  # type: ignore
            response.video_description_for_friday,  # type: ignore
            friday,
        ),
    ]

    for topic, description, video_description, post_date in topics:
        write_linkedin_post(
            topic=topic,
            target_audience="builders who dont want to code",
            platform="linkedin",
            content_type="linkedin post",
            goal="get clicks on the post",
            post_date_str=post_date.isoformat(),
            description=description,
        )

        write_twitter_post(
            topic=topic,
            target_audience="builders who dont want to code",
            platform="twitter",
            content_type="twitter post",
            goal="get clicks on the post",
            post_date_str=post_date.isoformat(),
            description=description,
        )

        write_youtube_description(
            topic=topic,
            target_audience="builders who dont want to code",
            video_summary=video_description,
            content_type="youtube description",
            goal="Get the most views on youtube",
            post_date_str=post_date.isoformat(),
        )

    return "Content scheduled for the next week"


@app.task
def delete_post(
    post_id: int,
    table: Literal["linkedin_posts", "twitter_posts", "youtube_descriptions"],
) -> str:
    """
    Delete a post from the specified database table.

    This function permanently removes a post from the database based on its ID and
    the specified table. This is useful for removing unwanted or outdated content
    before it gets published.

    Args:
        post_id (int): The database ID of the post to delete
        table (Literal["linkedin_posts", "twitter_posts", "youtube_descriptions"]):
            The database table containing the post to delete. Must be one of the
            specified table names.

    Returns:
        str: Confirmation message indicating successful deletion

    Raises:
        Exception: If the post doesn't exist or database operation fails

    Example:
        >>> delete_post(post_id=123, table="linkedin_posts")
        "Post deleted"

    Note:
        - This operation is irreversible - deleted posts cannot be recovered
        - Works for posts in any status (pending, posted, etc.)
        - No validation is performed on post_id existence before deletion
        - Use with caution, especially for posts that have already been published
    """
    supabase.table(table).delete().eq("id", post_id).execute()

    return "Post deleted"


if __name__ == "__main__":
    app.run()
