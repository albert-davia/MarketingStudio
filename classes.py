## Davia setup
## supabase setup
from typing import Literal

from pydantic import BaseModel


class LinkedinPost(BaseModel):
    title: str
    post: str
    status: Literal["pending", "posted"] = "pending"
    post_date: str | None = None


class TwitterPost(BaseModel):
    post: str
    status: Literal["pending", "posted"] = "pending"
    post_date: str | None = None


class YouTubeDescription(BaseModel):
    title: str
    description: str
    video_url_drive: str
    status: Literal["pending", "posted"] = "pending"
    post_date: str | None = None


class Schedule(BaseModel):
    topic_for_monday: str
    description_for_monday: str
    video_description_for_monday: str
    topic_for_wednesday: str
    description_for_wednesday: str
    video_description_for_wednesday: str
    topic_for_friday: str
    description_for_friday: str
    video_description_for_friday: str
