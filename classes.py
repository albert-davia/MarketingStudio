import operator

## Davia setup
## supabase setup
from typing import Annotated, Literal

from langgraph.graph import MessagesState
from pydantic import BaseModel


class LinkedinPost(BaseModel):
    title: str
    post: str
    status: Literal["pending", "posted"] = "pending"
    post_date: str | None = None


class TwitterPost(BaseModel):
    post: str
    posted: bool = False
    post_date: str | None = None


class YouTubeDescription(BaseModel):
    title: str
    description: str
    video_url_drive: str
    posted: bool = False
    post_date: str | None = None


class State(MessagesState):
    linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    new_linkedin_posts: Annotated[list[LinkedinPost], operator.add]
    twitter_posts: Annotated[list[TwitterPost], operator.add]
    new_twitter_posts: Annotated[list[TwitterPost], operator.add]
    youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]
    new_youtube_descriptions: Annotated[list[YouTubeDescription], operator.add]
    html_week_ahead: str
