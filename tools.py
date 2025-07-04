# Import LinkedIn and YouTube functionality
import datetime

## Davia setup
## supabase setup
import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from supabase import Client, create_client

from classes import (
    LinkedinPost,
    State,
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
            title=post["title"],
            post=post["post"],
            status=post["status"],
            post_date=post.get("post_date"),
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
        )
    )
    post.status = "pending"  # type: ignore

    debug = (
        supabase.table("linkedin_posts")
        .insert(
            {
                "title": post.title,  # type: ignore
                "post": post.post,  # type: ignore
                "created_at": datetime.datetime.now().isoformat(),
                "post_date": post_date,
                "status": "pending",
            }
        )
        .execute()
    )

    return f"LinkedIn post written: {post.title} with id : {debug.data[0]['id']}"  # type: ignore


def write_twitter_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Write a Twitter post about a given topic"""
    post = model.with_structured_output(TwitterPost).invoke(
        post_generation_prompt.format(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            content_type=content_type,
            goal=goal,
            past_posts=state["twitter_posts"] + state["new_twitter_posts"],
        )
    )
    post.posted = False  # type: ignore
    return Command(
        update={
            "new_twitter_posts": [post],
            "messages": [
                ToolMessage(
                    f"Twitter post written: {post.post}",  # type: ignore
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


def write_youtube_description(
    topic: str,
    target_audience: str,
    video_summary: str,
    content_type: str,
    goal: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Write a YouTube video description about a given topic"""
    description = model.with_structured_output(YouTubeDescription).invoke(
        youtube_description_prompt.format(
            topic=topic,
            target_audience=target_audience,
            content_type=content_type,
            goal=goal,
            video_summary=video_summary,
            past_descriptions=state["youtube_descriptions"]
            + state["new_youtube_descriptions"],
        )
    )
    description.posted = False  # type: ignore
    return Command(
        update={
            "new_youtube_descriptions": [description],
            "messages": [
                ToolMessage(
                    f"YouTube description written: {description.title}",  # type: ignore
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


def post_to_linkedin(
    linkedin_post: LinkedinPost,
    tool_call_id: Annotated[str, InjectedToolCallId],
    visibility: str = "connections",
    schedule_time: str | None = None,
) -> Command:
    """Post content to LinkedIn using Selenium automation. Can schedule posts for later."""

    text = linkedin_post.post

    try:
        # Get LinkedIn credentials from environment
        email = os.getenv("LINKEDIN_EMAIL")
        password = os.getenv("LINKEDIN_PASSWORD")

        if not email or not password:
            return Command(
                update={
                    "messages": [
                        ToolMessage(
                            "LinkedIn credentials not found. Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables.",
                            tool_call_id=tool_call_id,
                        )
                    ],
                }
            )

        # Initialize LinkedIn poster
        poster = LinkedInSeleniumPoster(headless=False)

        try:
            # Login to LinkedIn
            if poster.login(email, password):
                # Parse schedule time if provided
                schedule_datetime = None
                if schedule_time:
                    try:
                        schedule_datetime = datetime.datetime.fromisoformat(
                            schedule_time.replace("Z", "+00:00")
                        )
                    except ValueError:
                        return Command(
                            update={
                                "messages": [
                                    ToolMessage(
                                        f"Invalid date format for schedule_time: {schedule_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
                                        tool_call_id=tool_call_id,
                                    )
                                ],
                            }
                        )

                # Use the new wrapper function to post content
                success = poster.post_linkedin_content(
                    text=text, schedule_time=schedule_datetime, visibility=visibility
                )

                if success:
                    if schedule_datetime:
                        result = f"Successfully scheduled LinkedIn post for {schedule_datetime.strftime('%Y-%m-%d %H:%M')} with {visibility} visibility"
                        # Save the scheduled post to state with original title and scheduled date
                        posted_linkedin_post = LinkedinPost(
                            title=linkedin_post.title,
                            post=linkedin_post.post,
                            status="pending",
                            post_date=schedule_datetime.isoformat(),
                        )
                        return Command(
                            update={
                                "new_linkedin_posts": [posted_linkedin_post],
                                "messages": [
                                    ToolMessage(
                                        f"LinkedIn post result: {result}",
                                        tool_call_id=tool_call_id,
                                    )
                                ],
                            }
                        )
                    else:
                        result = f"Successfully posted to LinkedIn with {visibility} visibility"
                        # Save the posted content to state with original title and current date
                        current_time = datetime.datetime.now()
                        posted_linkedin_post = LinkedinPost(
                            title=linkedin_post.title,
                            post=linkedin_post.post,
                            status="pending",
                            post_date=current_time.isoformat(),
                        )

                    return Command(
                        update={
                            "new_linkedin_posts": [posted_linkedin_post],
                            "messages": [
                                ToolMessage(
                                    f"LinkedIn post result: {result}",
                                    tool_call_id=tool_call_id,
                                )
                            ],
                        }
                    )
                else:
                    result = "Failed to post to LinkedIn"
            else:
                result = "Failed to login to LinkedIn"

        finally:
            poster.close()

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"LinkedIn post result: {result}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error posting to LinkedIn: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    channel: Literal["albertthebuilder", "davia"],
    tool_call_id: Annotated[str, InjectedToolCallId],
    publish_at: str | None = None,
    privacy_status: str = "private",
) -> Command:
    """Upload a video to YouTube with the given metadata, channel is the channel to upload to it must have been specified by the user before"""
    try:
        # Parse publish_at if provided
        publish_datetime = None
        if publish_at:
            try:
                publish_datetime = datetime.datetime.fromisoformat(
                    publish_at.replace("Z", "+00:00")
                )
            except ValueError:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                f"Invalid date format for publish_at: {publish_at}. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
                                tool_call_id=tool_call_id,
                            )
                        ],
                    }
                )

        # Upload the video
        video_id = upload_local_video(
            video_path=video_path,
            title=title,
            description=description,
            channel=channel,
            publish_at=publish_datetime,
            privacy_status="private",
            tags=["davia", "ai", "development", "automation"],
        )

        result = "successefuly uploaded" + video_id

        # Save the uploaded video description to state
        youtube_description = YouTubeDescription(
            title=title,
            description=description,
            video_url_drive=f"https://www.youtube.com/watch?v={video_id}",
            posted=True,
        )

        return Command(
            update={
                "new_youtube_descriptions": [youtube_description],
                "messages": [
                    ToolMessage(
                        f"YouTube upload result: {result}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except FileNotFoundError:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Video file not found: {video_path}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )
    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error uploading to YouTube: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )


def post_to_twitter(
    twitter_post: TwitterPost,
    tool_call_id: Annotated[str, InjectedToolCallId],
    schedule_time: str | None = None,
) -> Command:
    """Post content to Twitter using Selenium automation. Can schedule posts for later."""

    text = twitter_post.post

    try:
        # Parse schedule time if provided
        schedule_datetime = None
        if schedule_time:
            try:
                schedule_datetime = datetime.datetime.fromisoformat(
                    schedule_time.replace("Z", "+00:00")
                )
            except ValueError:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                f"Invalid date format for schedule_time: {schedule_time}. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
                                tool_call_id=tool_call_id,
                            )
                        ],
                    }
                )

        # Use the post_tweet function to post content
        post_tweet(text, schedule_datetime)

        if schedule_datetime:
            result = f"Successfully scheduled Twitter post for {schedule_datetime.strftime('%Y-%m-%d %H:%M')}"
            # Save the scheduled post to state
            posted_twitter_post = TwitterPost(
                post=twitter_post.post,
                posted=True,
            )
        else:
            result = "Successfully posted to Twitter"
            # Save the posted content to state
            posted_twitter_post = TwitterPost(
                post=twitter_post.post,
                posted=True,
            )

        return Command(
            update={
                "new_twitter_posts": [posted_twitter_post],
                "messages": [
                    ToolMessage(
                        f"Twitter post result: {result}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    except Exception as e:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Error posting to Twitter: {str(e)}",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )


if __name__ == "__main__":
    write_linkedin_post(
        topic="test",
        target_audience="test",
        platform="test",
        content_type="test",
        goal="test",
        post_date_str="2025-01-01T00:00:00Z",
    )
