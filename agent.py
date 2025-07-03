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
from twitter_selenium_poster import post_tweet
from upload_youtube import upload_local_video

supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

## LLM

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

## Tools

post_generation_prompt = """You are a world-class copywriter and content strategist.
Your job is to write high-performing content for:
{topic}
Details:
Target audience: {target_audience}
Platform: {platform}
Content type: {content_type}
Goal: {goal}
Instructions:
1. Start with a scroll-stopping hook
2. Use clear, concise, natural language
3. Apply storytelling, persuasion, and value delivery
4. Follow proven frameworks (AIDA, PAS, Hook-Point-Action, etc.)
5. End with a strong CTA
Write like a human. No fluff. No cringe. Make it hit.

Use the past posts as a reference to write the new post.

Past posts:
{past_posts}
"""

youtube_description_prompt = """You are a world-class YouTube content strategist and SEO expert.
Your job is to write high-performing YouTube video descriptions for:
{topic}
Details:
Target audience: {target_audience}
Video type: {content_type}
Goal: {goal}
Instructions:
1. Start with a compelling hook that matches the video title
2. Include relevant keywords naturally throughout the description
3. Provide a brief overview of what viewers will learn
4. Add timestamps if applicable
5. Include relevant links and resources
6. Use proper YouTube description formatting
7. End with a call-to-action for engagement (like, subscribe, comment)
8. Keep it under 5000 characters (YouTube limit)
9. Make it searchable and engaging

this is the video summary: {video_summary}

Use the past descriptions as a reference to write the new description.

Past descriptions:
{past_descriptions}
"""

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


class State(MessagesState):
    linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    new_linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    twitter_posts: Annotated[list[TwitterPost], operator.add]
    new_twitter_posts: Annotated[list[TwitterPost], operator.add]
    youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]
    new_youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]


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
    post.posted = False
    return Command(
        update={
            "new_linkedin_posts": [post],
            "messages": [
                ToolMessage(
                    f"LinkedIn post written: {post.title}",
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
    post.posted = False
    return Command(
        update={
            "new_twitter_posts": [post],
            "messages": [
                ToolMessage(
                    f"Twitter post written: {post.post}",
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
    description.posted = False
    return Command(
        update={
            "new_youtube_descriptions": [description],
            "messages": [
                ToolMessage(
                    f"YouTube description written: {description.title}",
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


agent_prompt = f""" You are a world-class content strategist, you lead a team of copywrites.
You work for a company Davia that sells a product called "Davia". It is a tool that helps people build front end for their applications.
The goal of the company is to allow builders to build powerful AI applications without coding or using their existing python backend.
You need to maintain the company's social media presence and create content for the company's social media accounts.
Your goal is to post videos on Youtube, post on Linkedin and Twitter, at least once every two days.
You conduct weekly check-ins with the team to discuss posts for the next week.

Current date: {datetime.datetime.now().strftime("%Y-%m-%d")}

Use the following tools to help you:
- write_linkedin_post: Write LinkedIn post content (returns a LinkedinPost object)
- write_twitter_post: Write Twitter post content (returns a TwitterPost object)
- write_youtube_description: Write YouTube video descriptions
- post_to_linkedin: Actually post a LinkedinPost object to LinkedIn (can schedule posts for later, requires LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables)
- post_to_twitter: Actually post a TwitterPost object to Twitter (can schedule posts for later, requires TWITTER_EMAIL and TWITTER_PASSWORD environment variables)
- upload_to_youtube: Upload videos to YouTube (requires Google OAuth setup)

WORKFLOW: 
- For LinkedIn: First use write_linkedin_post to generate content, then pass the returned LinkedinPost object to post_to_linkedin.
- For Twitter: First use write_twitter_post to generate content, then pass the returned TwitterPost object to post_to_twitter.

For LinkedIn and Twitter scheduling, you can specify a schedule_time parameter in ISO format (YYYY-MM-DDTHH:MM:SS) to schedule posts for later.

IMPORTANT: When providing arguments to tools, do NOT use single quotes (') or double quotes (") around the values. Provide the raw text without any quotation marks.

Never use the tools if you don't have to.
Never try to do something yourself if you can use the tools.
"""

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
    return {"messages": [model_with_tools.invoke([agent_prompt] + state["messages"])]}


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
