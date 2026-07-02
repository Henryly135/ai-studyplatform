from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.uuid_codec import encode_comment_uuid, encode_user_uuid
from app.models.course_forum_comment import ForumCommentKind
from app.models.course_forum_post import ForumPostKind
from app.schemas.forum import CourseForumCommentCreateRequest, CourseForumCommentUpdateRequest, CourseForumPostCreateRequest, CourseForumPostUpdateRequest
from app.schemas.notification import NotificationCreateRequest, NotificationUpdateRequest
from app.services.forum_comment_service import ForumCommentService
from app.services.forum_service import ForumService
from app.services.notification_service import NotificationService


NOW = datetime(2024, 1, 1, 12, 0, 0)


class FakeSession:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def refresh(self, item):
        return None


def _notification(notification_id=1):
    return SimpleNamespace(
        notification_id=notification_id,
        actor_user_id=7,
        actor_email="actor@example.com",
        actor_name="Actor",
        notification_type="type",
        title="Title",
        body="Body",
        target_type="target",
        target_id="1",
        metadata_json={"a": 1},
        created_at=NOW,
        updated_at=NOW,
    )


def _recipient(notification=None):
    return SimpleNamespace(
        notification_id=1,
        recipient_user_id=8,
        recipient_email="recipient@example.com",
        recipient_name="Recipient",
        is_read=False,
        read_at=None,
        is_hidden=False,
        hidden_at=None,
        created_at=NOW,
        notification=notification or _notification(),
    )


def _post(author_user_id=7):
    return SimpleNamespace(
        post_id=1,
        course_id=10,
        author_user_id=author_user_id,
        author_email="author@example.com",
        author_name="Author",
        title="Post",
        content="Body",
        post_kind=ForumPostKind.USER,
        metadata_json=None,
        is_pinned=False,
        pinned_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _comment(comment_id=2, author_user_id=7, root_comment_id=None, reply_to_comment_id=None):
    return SimpleNamespace(
        comment_id=comment_id,
        post_id=1,
        course_id=10,
        author_user_id=author_user_id,
        author_email="author@example.com",
        author_name=f"Author {comment_id}",
        root_comment_id=root_comment_id,
        reply_to_comment_id=reply_to_comment_id,
        content="Comment",
        comment_kind=ForumCommentKind.USER,
        metadata_json=None,
        is_deleted=False,
        deleted_at=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _allow_forum_access():
    return SimpleNamespace(assert_forum_access=lambda **_kwargs: None)


def test_notification_service_create_list_update_delete_and_state_transitions():
    # Tests notification service create/list/update/delete and recipient read/hidden state transitions.
    session = FakeSession()
    service = NotificationService(session)
    notification = _notification()
    recipient = _recipient(notification)

    service.notifications = SimpleNamespace(
        create=lambda **kwargs: notification,
        list_paginated=lambda **kwargs: ([notification], 1, 1, 1),
        get_by_id=lambda notification_id: notification,
        update=lambda item, **kwargs: item,
        delete=lambda item: None,
    )
    service.recipients = SimpleNamespace(
        create_many=lambda **kwargs: [recipient],
        list_by_user=lambda **kwargs: ([recipient], 1, 1, 1),
        get_by_notification_and_user=lambda **kwargs: recipient,
        count_unread_by_user=lambda **kwargs: 3,
        mark_read=lambda item, read_at: setattr(item, "is_read", True) or setattr(item, "read_at", read_at) or item,
        mark_unread=lambda item: setattr(item, "is_read", False) or setattr(item, "read_at", None) or item,
        mark_all_read=lambda **kwargs: 2,
        hide=lambda item, hidden_at: setattr(item, "is_hidden", True) or setattr(item, "hidden_at", hidden_at) or item,
        unhide=lambda item: setattr(item, "is_hidden", False) or setattr(item, "hidden_at", None) or item,
    )

    create_payload = NotificationCreateRequest(
        notificationType=" type ",
        title=" Title ",
        body=" Body ",
        recipients=[
            {
                "recipientUserUuid": encode_user_uuid(8),
                "recipientEmail": " recipient@example.com ",
                "recipientName": " Recipient ",
            }
        ],
    )

    assert service.create_notification(payload=create_payload, current_user={"id": 7, "email": "a@example.com", "userName": "Actor"}).notificationId == 1
    assert service.list_all_notifications(notification_type=" type ").total == 1
    assert service.list_notifications(recipient_user_id=8).items[0].recipientUserId == 8
    assert service.get_notification(notification_id=1).notificationId == 1
    assert service.update_notification(notification_id=1, payload=NotificationUpdateRequest(title="Updated")).notificationId == 1
    assert service.get_recipient_notification(notification_id=1, recipient_user_id=8).recipientUserId == 8
    assert service.count_unread_notifications(recipient_user_id=8).unreadCount == 3
    assert service.mark_notification_read(notification_id=1, recipient_user_id=8, read_at=NOW).isRead is True
    assert service.mark_notification_unread(notification_id=1, recipient_user_id=8).isRead is False
    assert service.mark_all_notifications_read(recipient_user_id=8, read_at=NOW).updatedCount == 2
    assert service.hide_notification(notification_id=1, recipient_user_id=8, hidden_at=NOW).isHidden is True
    assert service.unhide_notification(notification_id=1, recipient_user_id=8).isHidden is False
    service.delete_notification(notification_id=1)

    assert session.committed is True


def test_notification_service_validation_and_not_found_errors():
    # Tests notification service validation errors and missing notification/recipient branches.
    service = NotificationService(FakeSession())
    service.notifications = SimpleNamespace(get_by_id=lambda notification_id: None, create=lambda **kwargs: _notification())
    service.recipients = SimpleNamespace(get_by_notification_and_user=lambda **kwargs: None)

    with pytest.raises(HTTPException):
        service.create_notification(
            payload=NotificationCreateRequest(
                notificationType="type",
                title="Title",
                body="Body",
                recipients=[{"recipientUserUuid": encode_user_uuid(8), "recipientEmail": "e", "recipientName": "n"}],
            ),
            current_user={"id": "bad"},
        )
    with pytest.raises(HTTPException):
        service.get_notification(notification_id=404)
    with pytest.raises(HTTPException):
        service.get_recipient_notification(notification_id=1, recipient_user_id=8)
    with pytest.raises(HTTPException):
        service.update_notification(notification_id=1, payload=NotificationUpdateRequest())


def test_forum_service_create_list_get_update_delete_and_pin_paths():
    # Tests forum post service create/list/get/update/delete plus admin and educator pin paths.
    session = FakeSession()
    service = ForumService(session)
    post = _post()
    preview = _comment()
    service.posts = SimpleNamespace(
        create=lambda **kwargs: post,
        list_by_course=lambda **kwargs: ([post], 1, 1, 1),
        get_by_id=lambda post_id: post,
        update=lambda item, **kwargs: [setattr(item, key, value) for key, value in kwargs.items() if value.__class__.__name__ != "object"] and item,
        delete=lambda item: None,
    )
    service.comments = SimpleNamespace(
        count_by_post_ids=lambda post_ids: {1: 2},
        list_preview_top_level_by_post_ids=lambda **kwargs: {1: [preview]},
        count_replies_by_root_comment_ids=lambda root_comment_ids: {2: 1},
    )
    service.course_access = _allow_forum_access()
    service.course_management = SimpleNamespace(assert_pin_access=lambda **kwargs: None)

    current_user = {"id": 7, "email": "user@example.com", "userName": "User", "identity": "Educator"}
    assert service.create_post(course_id=10, payload=CourseForumPostCreateRequest(title="T", content="Body"), current_user=current_user).postId == 1
    assert service.list_posts(course_id=10, current_user=current_user).total == 1
    assert service.get_post(post_id=1, current_user=current_user).commentCount == 2
    assert service.update_post(post_id=1, payload=CourseForumPostUpdateRequest(content="Updated"), current_user=current_user).postId == 1
    assert service.pin_post(post_id=1, current_user=current_user, token="tok").isPinned is True
    assert service.unpin_post(post_id=1, current_user={"id": 9, "identity": "Admin"}, token="tok").isPinned is False
    service.delete_post(post_id=1, current_user=current_user)

    assert session.committed is True


def test_forum_service_rejects_invalid_post_kind_empty_update_and_forbidden_access():
    # Tests forum post service invalid kind, empty update, and write/pin forbidden branches.
    service = ForumService(FakeSession())
    post = _post(author_user_id=1)
    service.posts = SimpleNamespace(get_by_id=lambda post_id: post, create=lambda **kwargs: post)
    service.course_access = _allow_forum_access()

    with pytest.raises(HTTPException):
        service.create_post(course_id=10, payload=CourseForumPostCreateRequest(content="Body", postKind="bad"), current_user={"id": 7, "email": "e", "userName": "n"})
    with pytest.raises(HTTPException):
        service.update_post(post_id=1, payload=CourseForumPostUpdateRequest(), current_user={"id": 1})
    with pytest.raises(HTTPException):
        service.delete_post(post_id=1, current_user={"id": 2, "identity": "Learner"})
    with pytest.raises(HTTPException):
        service.pin_post(post_id=1, current_user={"id": 2, "identity": "Learner"}, token="tok")


def test_forum_service_rejects_course_space_access_before_read_or_write():
    # Tests forum posts cannot be listed or created without learning-service course access.
    service = ForumService(FakeSession())
    post = _post()
    list_calls = []
    create_calls = []
    forbidden = HTTPException(
        status_code=403,
        detail={"code": "COURSE_ENROLLMENT_REQUIRED", "message": "Enrollment required"},
    )
    service.posts = SimpleNamespace(
        list_by_course=lambda **kwargs: list_calls.append(kwargs) or ([post], 1, 1, 1),
        create=lambda **kwargs: create_calls.append(kwargs) or post,
    )
    service.course_access = SimpleNamespace(
        assert_forum_access=lambda **_kwargs: (_ for _ in ()).throw(forbidden)
    )

    with pytest.raises(HTTPException) as list_error:
        service.list_posts(course_id=10, current_user={"id": 7, "identity": "Learner"})
    with pytest.raises(HTTPException) as create_error:
        service.create_post(
            course_id=10,
            payload=CourseForumPostCreateRequest(title="T", content="Body"),
            current_user={"id": 7, "email": "e", "userName": "n", "identity": "Learner"},
        )

    assert list_error.value.status_code == 403
    assert create_error.value.status_code == 403
    assert list_calls == []
    assert create_calls == []


def test_forum_comment_service_create_list_replies_update_delete_paths():
    # Tests forum comment service create/list/replies/get/update/delete with reply metadata.
    session = FakeSession()
    service = ForumCommentService(session)
    post = _post()
    root = _comment(comment_id=2)
    reply = _comment(comment_id=3, root_comment_id=2, reply_to_comment_id=2)
    service.posts = SimpleNamespace(get_by_id=lambda post_id: post)
    service.comments = SimpleNamespace(
        get_by_id=lambda comment_id: root if comment_id == 2 else reply,
        create=lambda **kwargs: reply,
        list_top_level_by_post=lambda **kwargs: ([root], 1, 1, 1),
        list_replies_by_root_comment=lambda **kwargs: ([reply], 1, 1, 1),
        count_replies_by_root_comment_ids=lambda root_comment_ids: {2: 1},
        update=lambda item, **kwargs: [setattr(item, key, value) for key, value in kwargs.items() if value.__class__.__name__ != "object"] and item,
    )
    service.course_access = _allow_forum_access()
    current_user = {"id": 7, "email": "user@example.com", "userName": "User", "identity": "Learner"}

    assert service.create_comment(post_id=1, payload=CourseForumCommentCreateRequest(content="Reply", replyToCommentUuid=encode_comment_uuid(2)), current_user=current_user).replyToAuthorName == "Author 2"
    assert service.list_post_comments(post_id=1, current_user=current_user).total == 1
    assert service.list_comment_replies(comment_id=2, current_user=current_user).items[0].replyToAuthorName == "Author 2"
    assert service.get_comment(comment_id=2, current_user=current_user).replyCount == 1
    assert service.update_comment(comment_id=2, payload=CourseForumCommentUpdateRequest(content="Updated"), current_user=current_user).commentId == 2
    assert service.delete_comment(comment_id=2, deleted_at=NOW, current_user=current_user).isDeleted is True

    assert session.committed is True


def test_forum_comment_service_rejects_invalid_reply_update_and_forbidden_access():
    # Tests forum comment service missing post, cross-post reply, deleted edit, and write forbidden branches.
    service = ForumCommentService(FakeSession())
    post = _post()
    comment = _comment(author_user_id=1)
    deleted_comment = _comment(author_user_id=7)
    deleted_comment.is_deleted = True
    deleted_comment.root_comment_id = 2
    service.posts = SimpleNamespace(get_by_id=lambda post_id: post if post_id == 1 else None)
    service.comments = SimpleNamespace(
        get_by_id=lambda comment_id: comment if comment_id == 2 else deleted_comment,
        update=lambda item, **kwargs: item,
    )
    service.course_access = _allow_forum_access()

    with pytest.raises(HTTPException):
        service.create_comment(post_id=404, payload=CourseForumCommentCreateRequest(content="C"), current_user={"id": 7, "email": "e", "userName": "n"})
    with pytest.raises(HTTPException):
        service.update_comment(comment_id=3, payload=CourseForumCommentUpdateRequest(content="C"), current_user={"id": 7})
    with pytest.raises(HTTPException):
        service.update_comment(comment_id=2, payload=CourseForumCommentUpdateRequest(content="C"), current_user={"id": 9, "identity": "Learner"})
    with pytest.raises(HTTPException):
        service.list_comment_replies(comment_id=3, current_user={"id": 7, "identity": "Learner"})


def test_forum_comment_service_rejects_course_space_access_before_comment_payloads():
    # Tests comment payloads are not returned when the caller cannot enter the course forum.
    service = ForumCommentService(FakeSession())
    post = _post()
    comment = _comment()
    list_calls = []
    forbidden = HTTPException(
        status_code=403,
        detail={"code": "COURSE_ENROLLMENT_REQUIRED", "message": "Enrollment required"},
    )
    service.posts = SimpleNamespace(get_by_id=lambda post_id: post)
    service.comments = SimpleNamespace(
        get_by_id=lambda comment_id: comment,
        list_top_level_by_post=lambda **kwargs: list_calls.append(kwargs) or ([comment], 1, 1, 1),
    )
    service.course_access = SimpleNamespace(
        assert_forum_access=lambda **_kwargs: (_ for _ in ()).throw(forbidden)
    )

    with pytest.raises(HTTPException) as list_error:
        service.list_post_comments(post_id=1, current_user={"id": 7, "identity": "Learner"})
    with pytest.raises(HTTPException) as get_error:
        service.get_comment(comment_id=2, current_user={"id": 7, "identity": "Learner"})

    assert list_error.value.status_code == 403
    assert get_error.value.status_code == 403
    assert list_calls == []
