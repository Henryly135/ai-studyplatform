from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CourseForumCommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    commentKind: str = Field(default="user", min_length=1, max_length=20)
    replyToCommentUuid: str | None = None
    metadataJson: dict[str, Any] | None = None


class CourseForumCommentUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    metadataJson: dict[str, Any] | None = None


class CourseForumCommentRead(BaseModel):
    commentId: int
    commentUuid: str
    postId: int
    postUuid: str
    courseId: int
    courseUuid: str
    authorUserId: int
    authorUserUuid: str
    authorEmail: str
    authorName: str
    rootCommentId: int | None
    rootCommentUuid: str | None
    replyToCommentId: int | None
    replyToCommentUuid: str | None
    replyToAuthorName: str | None
    content: str
    commentKind: str
    metadataJson: dict[str, Any] | None
    isDeleted: bool
    deletedAt: datetime | None
    replyCount: int
    createdAt: datetime
    updatedAt: datetime


class PaginatedCourseForumCommentResponse(BaseModel):
    items: list[CourseForumCommentRead]
    page: int
    pageSize: int
    total: int
    totalPages: int


class CourseForumPostCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str = Field(..., min_length=1)
    postKind: str = Field(default="user", min_length=1, max_length=20)
    metadataJson: dict[str, Any] | None = None


class CourseForumPostUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    metadataJson: dict[str, Any] | None = None


class CourseForumPostRead(BaseModel):
    postId: int
    postUuid: str
    courseId: int
    courseUuid: str
    authorUserId: int
    authorUserUuid: str
    authorEmail: str
    authorName: str
    title: str | None
    content: str
    postKind: str
    metadataJson: dict[str, Any] | None
    isPinned: bool
    pinnedAt: datetime | None
    commentCount: int
    previewComments: list[CourseForumCommentRead]
    createdAt: datetime
    updatedAt: datetime


class PaginatedCourseForumPostResponse(BaseModel):
    items: list[CourseForumPostRead]
    page: int
    pageSize: int
    total: int
    totalPages: int
