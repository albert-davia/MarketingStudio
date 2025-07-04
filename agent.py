import datetime
import operator

## Davia setup
## supabase setup
import os
from typing import Annotated, Any, Literal

from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import InjectedToolCallId
from langchain_openai import ChatOpenAI
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import InjectedState, ToolNode
from langgraph.types import Command
from pydantic import BaseModel
from supabase import Client, create_client

# Import LinkedIn and YouTube functionality
from linkedin_selenium_poster import LinkedInSeleniumPoster
from promts import agent_prompt, post_generation_prompt, youtube_description_prompt
from twitter_selenium_poster import post_tweet
from upload_youtube import upload_local_video

supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

## LLM

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def custom_reducer(list1: list[Any], list2: list[Any]) -> list[Any]:
    for item2 in list2:
        if isinstance(item2, DeleteTask):
            list1 = [item for item in list1 if item.id != item2.id]
        else:
            list1.append(item2)
    return list1


goals = ["engagement", "clicks", "conversions", "leads"]

content_types = ["viral thread", "sales page", "cold email", "newsletter"]


class LinkedinPost(BaseModel):
    title: str
    post: str
    posted: bool = False
    post_date: str | None = None


class TwitterPost(BaseModel):
    post: str
    posted: bool = False


class YouTubeDescription(BaseModel):
    title: str
    description: str
    video_url_drive: str
    posted: bool = False


class DeleteTask(BaseModel):
    id: int


class Task(BaseModel):
    id: int | None = None
    created_at: datetime.datetime | None = None
    time: datetime.datetime | None = None
    description: str | None = None
    status: Literal["pending", "posted"] = "pending"
    content_type: Literal["youtube", "linkedin", "twitter"] = "youtube"


class State(MessagesState):
    linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    new_linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    twitter_posts: Annotated[list[TwitterPost], operator.add]
    new_twitter_posts: Annotated[list[TwitterPost], operator.add]
    youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]
    new_youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]
    tasks: Annotated[list[Task], custom_reducer]
    html_week_ahead: str


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


# Create tools list with conditional inclusion based on availability
tools = [
    write_linkedin_post,
    write_twitter_post,
    write_youtube_description,
    post_to_linkedin,
    post_to_twitter,
    upload_to_youtube,
]

model_with_tools = model.bind_tools(tools)


def agent(state: State):
    return {
        "messages": [
            model_with_tools.invoke(
                [
                    agent_prompt.format(
                        current_date=datetime.datetime.now().strftime("%Y-%m-%d")
                    )
                ]
                + state["messages"]
            )
        ]
    }


def load_state(state: State):
    # Load data from Supabase and filter out invalid records
    linkedin_data = supabase.table("linkedin_posts").select("*").execute().data
    twitter_data = supabase.table("twitter_posts").select("*").execute().data
    youtube_data = supabase.table("youtube_descriptions").select("*").execute().data

    # Filter out records with None values for required fields
    valid_linkedin_posts = []
    for post in linkedin_data:
        if post.get("title") is not None and post.get("post") is not None:
            valid_linkedin_posts.append(
                LinkedinPost(
                    title=post["title"],
                    post=post["post"],
                    posted=True,  # All existing data is considered posted
                    post_date=post.get(
                        "post_date"
                    ),  # Load existing post_date if available
                )
            )

    valid_twitter_posts = []
    for post in twitter_data:
        if post.get("post") is not None:
            valid_twitter_posts.append(
                TwitterPost(
                    post=post["post"],
                    posted=True,  # All existing data is considered posted
                )
            )

    valid_youtube_descriptions = []
    for desc in youtube_data:
        if (
            desc.get("title") is not None
            and desc.get("description") is not None
            and desc.get("video_url_drive") is not None
        ):
            valid_youtube_descriptions.append(
                YouTubeDescription(
                    title=desc["title"],
                    description=desc["description"],
                    video_url_drive=desc["video_url_drive"],
                    posted=True,  # All existing data is considered posted
                )
            )

    return {
        "linkedin_posts": valid_linkedin_posts,
        "twitter_posts": valid_twitter_posts,
        "youtube_descriptions": valid_youtube_descriptions,
    }


def save_state(state: State):
    if state.get("new_linkedin_posts"):
        # Only save LinkedIn posts that were actually posted
        posted_linkedin_posts = [p for p in state["new_linkedin_posts"] if p.posted]
        if posted_linkedin_posts:
            # Create data with post_date, but handle potential column missing
            data = []
            for p in posted_linkedin_posts:
                post_data = {"title": p.title, "post": p.post}
                if p.post_date is not None:
                    post_data["post_date"] = p.post_date
                data.append(post_data)

            try:
                supabase.table("linkedin_posts").insert(data).execute()
                print(f"✅ Saved {len(data)} LinkedIn posts to database")
            except Exception as e:
                print(f"⚠️  Error saving LinkedIn posts: {e}")
                # Try without post_date if column doesn't exist
                try:
                    fallback_data = [
                        {"title": p.title, "post": p.post}
                        for p in posted_linkedin_posts
                    ]
                    supabase.table("linkedin_posts").insert(fallback_data).execute()
                    print(
                        f"✅ Saved {len(fallback_data)} LinkedIn posts without post_date"
                    )
                except Exception as e2:
                    print(f"❌ Failed to save LinkedIn posts: {e2}")

    if state.get("new_twitter_posts"):
        # Only save Twitter posts that were actually posted
        posted_twitter_posts = [p for p in state["new_twitter_posts"] if p.posted]
        if posted_twitter_posts:
            # Exclude the 'posted' field since it doesn't exist in the database
            data = [{"post": p.post} for p in posted_twitter_posts]
            supabase.table("twitter_posts").insert(data).execute()

    if state.get("new_youtube_descriptions"):
        # Only save YouTube descriptions that were actually uploaded
        posted_youtube_descriptions = [
            p for p in state["new_youtube_descriptions"] if p.posted
        ]
        if posted_youtube_descriptions:
            # Exclude the 'posted' field since it doesn't exist in the database
            data = [
                {
                    "title": p.title,
                    "description": p.description,
                    "video_url_drive": p.video_url_drive,
                }
                for p in posted_youtube_descriptions
            ]
            supabase.table("youtube_descriptions").insert(data).execute()


def custom_tools_condition(
    state: list[AnyMessage] | dict[str, Any] | BaseModel,
    messages_key: str = "messages",
) -> Literal["tools", "save_state"]:
    """Use in the conditional_edge to route to the ToolNode if the last message

    has tool calls. Otherwise, route to the end.

    Args:
        state (Union[list[AnyMessage], dict[str, Any], BaseModel]): The state to check for
            tool calls. Must have a list of messages (MessageGraph) or have the
            "messages" key (StateGraph).

    Returns:
        The next node to route to.


    Examples:
        Create a custom ReAct-style agent with tools.

        ```pycon
        >>> from langchain_anthropic import ChatAnthropic
        >>> from langchain_core.tools import tool
        ...
        >>> from langgraph.graph import StateGraph
        >>> from langgraph.prebuilt import ToolNode, tools_condition
        >>> from langgraph.graph.message import add_messages
        ...
        >>> from typing import Annotated
        >>> from typing_extensions import TypedDict
        ...
        >>> @tool
        >>> def divide(a: float, b: float) -> int:
        ...     \"\"\"Return a / b.\"\"\"
        ...     return a / b
        ...
        >>> llm = ChatAnthropic(model="claude-3-haiku-20240307")
        >>> tools = [divide]
        ...
        >>> class State(TypedDict):
        ...     messages: Annotated[list, add_messages]
        >>>
        >>> graph_builder = StateGraph(State)
        >>> graph_builder.add_node("tools", ToolNode(tools))
        >>> graph_builder.add_node("chatbot", lambda state: {"messages":llm.bind_tools(tools).invoke(state['messages'])})
        >>> graph_builder.add_edge("tools", "chatbot")
        >>> graph_builder.add_conditional_edges(
        ...     "chatbot", tools_condition
        ... )
        >>> graph_builder.set_entry_point("chatbot")
        >>> graph = graph_builder.compile()
        >>> graph.invoke({"messages": {"role": "user", "content": "What's 329993 divided by 13662?"}})
        ```
    """
    if isinstance(state, list):
        ai_message = state[-1]
    elif isinstance(state, dict) and (messages := state.get(messages_key, [])):
        ai_message = messages[-1]
    elif messages := getattr(state, messages_key, []):
        ai_message = messages[-1]
    else:
        raise ValueError(f"No messages found in input state to tool_edge: {state}")
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:  # type: ignore
        return "tools"
    return "save_state"


graph = StateGraph(State)

graph.add_node("agent", agent)

graph.add_node("load_state", load_state)

graph.add_node("tools", ToolNode(tools=tools))

graph.add_node("save_state", save_state)

graph.add_edge("__start__", "load_state")

graph.add_edge("load_state", "agent")

graph.add_edge("tools", "agent")

graph.add_edge("save_state", "__end__")

graph.add_conditional_edges("agent", custom_tools_condition)

graph.compile()
