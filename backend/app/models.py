from datetime import datetime
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class PostStatus(str, Enum):
    draft = "DRAFT"
    ready = "READY"
    approved = "APPROVED"
    scheduled = "SCHEDULED"
    publishing = "PUBLISHING"
    published = "PUBLISHED"
    failed = "FAILED"
    retry = "RETRY"
    blocked = "BLOCKED"
    cancelled = "CANCELLED"


class Client(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SocialAccount(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True, foreign_key="client.id")
    platform: str = Field(index=True)
    external_account_id: str
    publisher_adapter: str = "postiz"
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContentItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(index=True, foreign_key="client.id")
    title: str
    body: str = ""
    format: str = "post"
    target: str = ""
    hook: str = ""
    cta: str = ""
    status: PostStatus = Field(default=PostStatus.draft, index=True)
    scheduled_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PublishAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content_item_id: int = Field(index=True, foreign_key="contentitem.id")
    platform: str = Field(index=True)
    adapter: str = "postiz"
    status: str = Field(default="PENDING", index=True)
    external_post_id: Optional[str] = None
    error_message: Optional[str] = None
    attempted_at: datetime = Field(default_factory=datetime.utcnow)


class AnalyticsSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content_item_id: int = Field(index=True, foreign_key="contentitem.id")
    platform: str = Field(index=True)
    reach: int = 0
    impressions: int = 0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    clicks: int = 0
    conversions: int = 0
    captured_at: datetime = Field(default_factory=datetime.utcnow, index=True)
