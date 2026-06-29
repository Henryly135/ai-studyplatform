from datetime import datetime
from types import SimpleNamespace

from app.core.time import now_local
from app.core.uuid_codec import (
    decode_comment_uuid,
    decode_course_uuid,
    decode_forum_post_uuid,
    decode_notification_uuid,
    decode_user_uuid,
    encode_comment_uuid,
    encode_course_uuid,
    encode_forum_post_uuid,
    encode_notification_uuid,
    encode_user_uuid,
)
from app.models.course_forum_comment import ForumCommentKind
from app.models.course_forum_post import ForumPostKind
from app.repositories.course_forum_comment_repository import CourseForumCommentRepository
from app.repositories.course_forum_post_repository import CourseForumPostRepository
from app.repositories.notification_recipient_repository import NotificationRecipientRepository
from app.repositories.notification_repository import NotificationRepository


class FakeSession:
    def __init__(self, *, scalar_result=None, scalars_result=None, execute_result=None, get_result=None):
        self.scalar_result = scalar_result
        self.scalars_result = scalars_result or []
        self.execute_result = execute_result or []
        self.get_result = get_result
        self.added = []
        self.deleted = []
        self.flushed = 0
        self.executed = []

    def get(self, model, item_id):
        return self.get_result

    def scalar(self, stmt):
        return self.scalar_result

    def scalars(self, stmt):
        return list(self.scalars_result)

    def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(all=lambda: list(self.execute_result))

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        self.flushed += 1

    def delete(self, obj):
        self.deleted.append(obj)


def test_uuid_codecs_round_trip_all_communication_ids():
    # Tests that every communication public UUID codec recovers the original numeric id.
    pairs = [
        (encode_course_uuid, decode_course_uuid),
        (encode_user_uuid, decode_user_uuid),
        (encode_forum_post_uuid, decode_forum_post_uuid),
        (encode_comment_uuid, decode_comment_uuid),
        (encode_notification_uuid, decode_notification_uuid),
    ]

    for index, (encoder, decoder) in enumerate(pairs, start=1):
        assert decoder(encoder(index)) == index


def test_now_local_returns_datetime_value():
    # Tests that the communication time helper returns a datetime-like value.
    assert now_local().year >= 2024


def test_notification_repository_crud_and_pagination_paths():
    # Tests notification repository list pagination, create, update, get, and delete paths.
    notification = SimpleNamespace(
        notification_id=1,
        notification_type="type",
        title="Title",
        body="Body",
        actor_user_id=7,
        actor_email="actor@example.com",
        actor_name="Actor",
        target_type=None,
        target_id=None,
        metadata_json=None,
    )
    session = FakeSession(scalar_result=2, scalars_result=[notification], get_result=notification)
    repo = NotificationRepository(session)

    assert repo.get_by_id(1) is notification
    assert repo.list_paginated(notification_type="type", page=9, page_size=1) == ([notification], 2, 2, 2)
    created = repo.create(notification_type="new", title="New", body="Body", actor_user_id=7)
    updated = repo.update(created, title="Updated", body="Updated body", metadata_json={"a": 1})
    repo.delete(updated)

    assert session.added[0].title == "Updated"
    assert session.deleted == [updated]


def test_notification_recipient_repository_state_and_pagination_paths():
    # Tests recipient repository creation, lookup, listing, counts, state transitions, and bulk read.
    now = datetime(2024, 1, 1, 12, 0, 0)
    recipient = SimpleNamespace(
        notification_id=1,
        recipient_user_id=7,
        recipient_email="user@example.com",
        recipient_name="User",
        is_read=False,
        read_at=None,
        is_hidden=False,
        hidden_at=None,
    )
    session = FakeSession(scalar_result=3, scalars_result=[recipient], get_result=recipient)
    repo = NotificationRecipientRepository(session)

    rows = repo.create_many(
        notification_id=1,
        recipients=[{"recipient_user_id": 7, "recipient_email": "user@example.com", "recipient_name": "User"}],
    )
    assert rows[0].recipient_user_id == 7
    assert repo.get_by_notification_and_user(notification_id=1, recipient_user_id=7) == 3
    assert repo.list_by_user(recipient_user_id=7, include_hidden=False, unread_only=True, notification_type="type") == ([recipient], 3, 1, 1)
    assert repo.count_unread_by_user(recipient_user_id=7) == 3
    assert repo.mark_read(recipient, read_at=now).is_read is True
    assert repo.mark_unread(recipient).is_read is False
    assert repo.mark_all_read(recipient_user_id=7, read_at=now) == 1
    assert repo.hide(recipient, hidden_at=now).is_hidden is True
    assert repo.unhide(recipient).is_hidden is False


def test_forum_post_repository_crud_and_pagination_paths():
    # Tests forum post repository list pagination, create, update, get, and delete paths.
    post = SimpleNamespace(post_id=1, title="Post", content="Body", is_pinned=False)
    session = FakeSession(scalar_result=2, scalars_result=[post], get_result=post)
    repo = CourseForumPostRepository(session)

    assert repo.get_by_id(1) is post
    assert repo.list_by_course(course_id=10, query="post", page=3, page_size=1) == ([post], 2, 2, 2)
    created = repo.create(
        course_id=10,
        author_user_id=7,
        author_email="user@example.com",
        author_name="User",
        title="Title",
        content="Body",
        post_kind=ForumPostKind.USER,
    )
    repo.update(created, title="Updated", content="New body", is_pinned=True, pinned_at=datetime(2024, 1, 1), pinned_by_user_id=7)
    repo.delete(created)

    assert created.is_pinned is True
    assert session.deleted == [created]


def test_forum_comment_repository_grouping_counts_crud_and_pagination_paths():
    # Tests comment repository pagination, preview grouping, count maps, create, and update paths.
    comment = SimpleNamespace(comment_id=2, post_id=1, root_comment_id=None, content="Comment")
    reply = SimpleNamespace(comment_id=3, post_id=1, root_comment_id=2, content="Reply")
    session = FakeSession(
        scalar_result=2,
        scalars_result=[comment, reply],
        execute_result=[(1, 2), (2, 1)],
        get_result=comment,
    )
    repo = CourseForumCommentRepository(session)

    assert repo.get_by_id(2) is comment
    assert repo.list_top_level_by_post(post_id=1, page=1, page_size=1) == ([comment, reply], 2, 1, 2)
    assert repo.list_preview_top_level_by_post_ids(post_ids=[1], limit_per_post=1) == {1: [comment]}
    assert repo.list_preview_top_level_by_post_ids(post_ids=[]) == {}
    assert repo.list_replies_by_root_comment(root_comment_id=2, page=1, page_size=2) == ([comment, reply], 2, 1, 1)
    assert repo.count_by_post_ids(post_ids=[1]) == {1: 2, 2: 1}
    assert repo.count_by_post_ids(post_ids=[]) == {}
    assert repo.count_replies_by_root_comment_ids(root_comment_ids=[2]) == {1: 2, 2: 1}
    assert repo.count_replies_by_root_comment_ids(root_comment_ids=[]) == {}
    created = repo.create(
        post_id=1,
        course_id=10,
        author_user_id=7,
        author_email="user@example.com",
        author_name="User",
        content="Comment",
        comment_kind=ForumCommentKind.USER,
    )
    repo.update(created, content="Updated", metadata_json={"a": 1}, is_deleted=True, deleted_at=datetime(2024, 1, 1))

    assert created.content == "Updated"
    assert created.is_deleted is True
