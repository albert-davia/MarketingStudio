import datetime

## Davia setup
## supabase setup
import os

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from supabase import Client, create_client

from classes import LinkedinPost, State, TwitterPost, YouTubeDescription

# Import LinkedIn and YouTube functionality
from promts import agent_prompt
from tools import (
    post_to_linkedin,
    post_to_twitter,
    upload_to_youtube,
    write_linkedin_post,
    write_twitter_post,
    write_youtube_description,
)
from utils import custom_tools_condition

supabase: Client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

## LLM

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)


goals = ["engagement", "clicks", "conversions", "leads"]

content_types = ["viral thread", "sales page", "cold email", "newsletter"]

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
                    status=post["status"],  # All existing data is considered posted
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
        posted_linkedin_posts = [
            p for p in state["new_linkedin_posts"] if p.status == "posted"
        ]
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
