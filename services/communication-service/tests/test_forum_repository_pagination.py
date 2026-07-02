from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.course_forum_comment import CourseForumComment, ForumCommentKind
from app.models.course_forum_post import CourseForumPost, ForumPostKind
from app.repositories.course_forum_comment_repository import CourseForumCommentRepository
from app.repositories.course_forum_post_repository import CourseForumPostRepository


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _post(post_id: int, *, course_id: int, title: str, created_at: datetime, pinned: bool = False) -> CourseForumPost:
    return CourseForumPost(
        post_id=post_id,
        course_id=course_id,
        author_user_id=7,
        author_email="author@example.com",
        author_name="Author",
        post_kind=ForumPostKind.USER,
        title=title,
        content=f"{title} body",
        is_pinned=pinned,
        pinned_at=created_at + timedelta(minutes=10) if pinned else None,
        created_at=created_at,
        updated_at=created_at,
    )


def _comment(
    comment_id: int,
    *,
    post_id: int,
    course_id: int,
    content: str,
    created_at: datetime,
    root_comment_id: int | None = None,
    reply_to_comment_id: int | None = None,
) -> CourseForumComment:
    return CourseForumComment(
        comment_id=comment_id,
        post_id=post_id,
        course_id=course_id,
        author_user_id=7,
        author_email="author@example.com",
        author_name=f"Author {comment_id}",
        root_comment_id=root_comment_id,
        reply_to_comment_id=reply_to_comment_id,
        comment_kind=ForumCommentKind.USER,
        content=content,
        is_deleted=False,
        created_at=created_at,
        updated_at=created_at,
    )


def test_forum_post_repository_paginates_searches_and_orders_pinned_posts() -> None:
    session = _session()
    base = datetime(2024, 1, 1, 12, 0, 0)
    session.add_all(
        [
            _post(1, course_id=10, title="Alpha notes", created_at=base),
            _post(2, course_id=10, title="Beta smoke", created_at=base + timedelta(minutes=1)),
            _post(3, course_id=10, title="Gamma smoke", created_at=base + timedelta(minutes=2), pinned=True),
            _post(4, course_id=11, title="Other course smoke", created_at=base + timedelta(minutes=3)),
        ]
    )
    session.commit()

    repo = CourseForumPostRepository(session)
    first_page, total, page, total_pages = repo.list_by_course(course_id=10, page=1, page_size=2)
    bounded_page, _, bounded_page_number, _ = repo.list_by_course(course_id=10, page=99, page_size=2)
    search_items, search_total, _, _ = repo.list_by_course(course_id=10, query="smoke", page=1, page_size=10)

    assert [item.post_id for item in first_page] == [3, 2]
    assert total == 3
    assert page == 1
    assert total_pages == 2
    assert [item.post_id for item in bounded_page] == [1]
    assert bounded_page_number == 2
    assert [item.post_id for item in search_items] == [3, 2]
    assert search_total == 2


def test_forum_comment_repository_paginates_top_level_comments_and_replies() -> None:
    session = _session()
    base = datetime(2024, 1, 1, 12, 0, 0)
    session.add(_post(1, course_id=10, title="Forum root", created_at=base))
    session.add_all(
        [
            _comment(1, post_id=1, course_id=10, content="Top 1", created_at=base),
            _comment(2, post_id=1, course_id=10, content="Top 2", created_at=base + timedelta(minutes=1)),
            _comment(3, post_id=1, course_id=10, content="Top 3", created_at=base + timedelta(minutes=2)),
            _comment(
                4,
                post_id=1,
                course_id=10,
                content="Reply 1",
                created_at=base + timedelta(minutes=3),
                root_comment_id=1,
                reply_to_comment_id=1,
            ),
            _comment(
                5,
                post_id=1,
                course_id=10,
                content="Reply 2",
                created_at=base + timedelta(minutes=4),
                root_comment_id=1,
                reply_to_comment_id=4,
            ),
        ]
    )
    session.commit()

    repo = CourseForumCommentRepository(session)
    top_level_page, top_level_total, top_level_page_number, top_level_pages = repo.list_top_level_by_post(
        post_id=1,
        page=2,
        page_size=2,
    )
    first_reply_page, reply_total, reply_page_number, reply_pages = repo.list_replies_by_root_comment(
        root_comment_id=1,
        page=1,
        page_size=1,
    )
    second_reply_page, _, second_reply_page_number, _ = repo.list_replies_by_root_comment(
        root_comment_id=1,
        page=2,
        page_size=1,
    )

    assert [item.comment_id for item in top_level_page] == [3]
    assert top_level_total == 3
    assert top_level_page_number == 2
    assert top_level_pages == 2
    assert [item.comment_id for item in first_reply_page] == [4]
    assert reply_total == 2
    assert reply_page_number == 1
    assert reply_pages == 2
    assert [item.comment_id for item in second_reply_page] == [5]
    assert second_reply_page_number == 2
