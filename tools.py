import datetime

## Davia setup
## supabase setup
import os
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.types import Command

from agent import (
    DeleteTask,
    LinkedinPost,
    State,
    Task,
    TwitterPost,
    YouTubeDescription,
    model,
)

# Import LinkedIn and YouTube functionality
from linkedin_selenium_poster import LinkedInSeleniumPoster
from promts import post_generation_prompt, youtube_description_prompt
from twitter_selenium_poster import post_tweet
from upload_youtube import upload_local_video


def write_linkedin_post(
    topic: str,
    target_audience: str,
    platform: str,
    content_type: str,
    goal: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Write a LinkedIn post about a given topic"""
    post = model.with_structured_output(LinkedinPost).invoke(
        post_generation_prompt.format(
            topic=topic,
            target_audience=target_audience,
            platform=platform,
            content_type=content_type,
            goal=goal,
            past_posts=state["linkedin_posts"] + state["new_linkedin_posts"],
        )
    )
    post.posted = False  # type: ignore
    return Command(
        update={
            "new_linkedin_posts": [post],
            "messages": [
                ToolMessage(
                    f"LinkedIn post written: {post.title}",  # type: ignore
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )


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
                            posted=True,
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
                            posted=True,
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


def add_task(
    description: str,
    time: datetime.datetime,
    content_type: Literal["youtube", "linkedin", "twitter"],
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Add a task to the state"""
    task = Task(
        created_at=datetime.datetime.now(),
        description=description,
        time=time,
        status="pending",
        content_type=content_type,
    )
    return Command(update={"tasks": [task]})


def delete_task(
    id: int,
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Delete a task from the state"""
    return Command(update={"tasks": [DeleteTask(id=id)]})


def visualize_tasks(
    tool_call_id: Annotated[str, InjectedToolCallId],
    state: Annotated[State, InjectedState],
) -> Command:
    """Visualize the week ahead with tasks using matplotlib"""
    import base64
    import io
    from datetime import datetime, timedelta

    import matplotlib.pyplot as plt

    # Get current date and calculate week range (Sunday to Sunday)
    today = datetime.now()
    # Find the most recent Sunday
    days_since_sunday = (
        today.weekday() + 1
    )  # Monday=0, so Sunday=6, but we want days since Sunday
    if days_since_sunday == 7:  # If today is Sunday
        days_since_sunday = 0
    start_of_week = today - timedelta(days=days_since_sunday)
    end_of_week = start_of_week + timedelta(days=6)

    # Get tasks from state
    tasks = state.get("tasks", [])

    # Filter tasks for this week
    week_tasks = []
    for task in tasks:
        if task.time and start_of_week <= task.time <= end_of_week:
            week_tasks.append(task)

    # Create the figure and axis
    fig, ax = plt.subplots(figsize=(12, 8))

    # Set up the calendar grid
    days = [
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
    ]
    hours = list(range(24))

    # Create a grid for the week
    for i, day in enumerate(days):
        day_date = start_of_week + timedelta(days=i)
        ax.text(
            i + 0.5,
            23.5,
            f"{day}\n{day_date.strftime('%m/%d')}",
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
        )

        # Draw day boundaries
        ax.axvline(x=i, color="gray", alpha=0.3)
        ax.axvline(x=i + 1, color="gray", alpha=0.3)

    # Draw hour lines
    for hour in hours:
        ax.axhline(y=hour, color="lightgray", alpha=0.3)

    # Plot tasks
    colors = {"youtube": "red", "linkedin": "blue", "twitter": "green"}
    task_height = 0.8

    for task in week_tasks:
        if task.time:
            # Calculate position
            day_index = (
                task.time.weekday() + 1
            )  # Convert to 0-6 range, then add 1 for Sunday=0
            if day_index == 7:  # Sunday
                day_index = 0
            hour = task.time.hour + task.time.minute / 60

            # Create rectangle for task
            rect = plt.Rectangle(
                (day_index, hour - task_height / 2),
                1,
                task_height,
                facecolor=colors.get(task.content_type, "gray"),
                alpha=0.7,
                edgecolor="black",
                linewidth=1,
            )
            ax.add_patch(rect)

            # Add task text
            ax.text(
                day_index + 0.5,
                hour,
                f"{task.time.strftime('%H:%M')}\n{task.description[:20]}...",
                ha="center",
                va="center",
                fontsize=8,
                fontweight="bold",
                color="white",
            )

    # Set up the plot
    ax.set_xlim(0, 7)
    ax.set_ylim(0, 24)
    ax.set_xticks(range(7))
    ax.set_xticklabels(days)
    ax.set_yticks(range(0, 25, 2))
    ax.set_yticklabels([f"{h:02d}:00" for h in range(0, 25, 2)])
    ax.set_ylabel("Time")
    ax.set_title(
        f"Week Ahead Schedule ({start_of_week.strftime('%m/%d')} - {end_of_week.strftime('%m/%d')})"
    )

    # Add legend
    legend_elements = [
        plt.Rectangle(
            (0, 0), 1, 1, facecolor=color, alpha=0.7, label=content_type.title()
        )
        for content_type, color in colors.items()
    ]
    ax.legend(handles=legend_elements, loc="upper right")

    # Rotate x-axis labels for better readability
    plt.xticks(rotation=45)

    # Adjust layout
    plt.tight_layout()

    # Save to bytes buffer
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)

    # Convert to base64 for display
    img_base64 = base64.b64encode(buf.getvalue()).decode()

    # Close the plot to free memory
    plt.close()

    # Create HTML to display the image
    html_content = f"""
    <div style="text-align: center;">
        <h3>Week Ahead Schedule</h3>
        <img src="data:image/png;base64,{img_base64}" style="max-width: 100%; height: auto;">
        <p><strong>Total Tasks:</strong> {len(week_tasks)}</p>
        <p><strong>Period:</strong> {start_of_week.strftime("%B %d, %Y")} - {end_of_week.strftime("%B %d, %Y")}</p>
    </div>
    """

    return Command(
        update={
            "html_week_ahead": html_content,
            "messages": [
                ToolMessage(
                    f"Week ahead visualization created with {len(week_tasks)} tasks",
                    tool_call_id=tool_call_id,
                )
            ],
        }
    )
