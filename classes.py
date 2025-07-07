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
