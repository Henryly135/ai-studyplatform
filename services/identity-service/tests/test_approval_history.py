from types import SimpleNamespace

import pytest
from datetime import datetime

from app.models.educator_approval_request import RequestStatus
from app.models.user import AccountStatus
from app.schemas.admin import EducatorApprovalHistoryQuery
from app.services.approval_service import ApprovalService, InvalidApprovalHistoryStatusError


def test_educator_approval_history_query_validates_status():
    # Tests that approval history query status is normalized.
    query = EducatorApprovalHistoryQuery(status=" approved ")
    assert query.status == "approved"


def test_educator_approval_history_query_rejects_invalid_status():
    # Tests that unsupported approval history status values fail validation.
    with pytest.raises(ValueError):
        EducatorApprovalHistoryQuery(status="pending")


def test_list_reviewed_requests_uses_requested_status(monkeypatch):
    # Tests that reviewed approval listing passes the requested status filter to the repository.
    service = ApprovalService(session=None)
    captured = {}

    monkeypatch.setattr(
        service.approvals,
        "get_reviewed_requests",
        lambda *, request_status=None: captured.update({"request_status": request_status}) or [],
    )

    result = service.list_reviewed_requests(status="rejected")

    assert result.requests == []
    assert captured["request_status"] == RequestStatus.REJECTED


def test_list_reviewed_requests_rejects_invalid_status():
    # Tests that service-level approval history rejects unsupported status filters.
    service = ApprovalService(session=None)

    with pytest.raises(InvalidApprovalHistoryStatusError):
        service.list_reviewed_requests(status="pending")


def test_review_request_sends_result_email_when_approved(monkeypatch):
    # Tests that approving an educator request sends an approval result email.
    session = SimpleNamespace(commit=lambda: None, refresh=lambda obj: None)
    service = ApprovalService(session=session)
    now = datetime.now()
    request = SimpleNamespace(
        request_id=3,
        user_id=7,
        request_status=RequestStatus.PENDING,
        reviewed_by=99,
        reviewed_at=now,
        review_comment=None,
        submitted_at=now,
        updated_at=now,
        supporting_info=None,
        supporting_file_url=None,
    )
    user = SimpleNamespace(
        user_id=7,
        email="educator@example.com",
        full_name="Educator User",
        email_verified=True,
        account_status=AccountStatus.PENDING,
    )
    educator_role = SimpleNamespace(role_id=2, role_code="educator")
    sent = {"value": False}

    monkeypatch.setattr(service.approvals, "get_by_id", lambda request_id: request)
    monkeypatch.setattr(
        service.users,
        "get_by_id",
        lambda user_id: user if user_id == 7 else SimpleNamespace(
            user_id=99,
            email="admin@example.com",
            full_name="Admin Reviewer",
        ),
    )
    monkeypatch.setattr(service.roles, "get_by_code", lambda role_code: educator_role)
    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [educator_role])
    monkeypatch.setattr(
        service.approvals,
        "update_status",
        lambda request_obj, **kwargs: request_obj,
    )
    monkeypatch.setattr(service.users, "update_account_status", lambda user_obj, status: user_obj)
    monkeypatch.setattr(service.audit_logs, "create_user_role_audit_log", lambda **kwargs: None)
    monkeypatch.setattr(service.session, "commit", lambda: None)
    monkeypatch.setattr(service.session, "refresh", lambda obj: None)
    monkeypatch.setattr(
        "app.services.approval_service.send_educator_approval_result_email",
        lambda email, user_name, result, review_comment: sent.update(
            {
                "value": True,
                "email": email,
                "user_name": user_name,
                "result": result,
                "review_comment": review_comment,
            }
        ),
    )

    service.review_request(
        request_id=3,
        action="approve",
        review_comment=None,
        reviewed_by_user_id=99,
    )

    assert sent["value"] is True
    assert sent["email"] == "educator@example.com"
    assert sent["result"] == "approved"


def test_review_request_sends_result_email_when_rejected(monkeypatch):
    # Tests that rejecting an educator request sends a rejection result email with the comment.
    session = SimpleNamespace(commit=lambda: None, refresh=lambda obj: None)
    service = ApprovalService(session=session)
    now = datetime.now()
    request = SimpleNamespace(
        request_id=3,
        user_id=7,
        request_status=RequestStatus.PENDING,
        reviewed_by=99,
        reviewed_at=now,
        review_comment="Insufficient verification details",
        submitted_at=now,
        updated_at=now,
        supporting_info=None,
        supporting_file_url=None,
    )
    user = SimpleNamespace(
        user_id=7,
        email="educator@example.com",
        full_name="Educator User",
        email_verified=True,
        account_status=AccountStatus.PENDING,
    )
    educator_role = SimpleNamespace(role_id=2, role_code="educator")
    sent = {"value": False}

    monkeypatch.setattr(service.approvals, "get_by_id", lambda request_id: request)
    monkeypatch.setattr(
        service.users,
        "get_by_id",
        lambda user_id: user if user_id == 7 else SimpleNamespace(
            user_id=99,
            email="admin@example.com",
            full_name="Admin Reviewer",
        ),
    )
    monkeypatch.setattr(service.roles, "get_by_code", lambda role_code: educator_role)
    monkeypatch.setattr(service.roles, "list_user_roles", lambda user_id: [educator_role])
    monkeypatch.setattr(
        service.approvals,
        "update_status",
        lambda request_obj, **kwargs: request_obj,
    )
    monkeypatch.setattr(service.users, "update_account_status", lambda user_obj, status: user_obj)
    monkeypatch.setattr(service.audit_logs, "create_user_role_audit_log", lambda **kwargs: None)
    monkeypatch.setattr(service.session, "commit", lambda: None)
    monkeypatch.setattr(service.session, "refresh", lambda obj: None)
    monkeypatch.setattr(
        "app.services.approval_service.send_educator_approval_result_email",
        lambda email, user_name, result, review_comment: sent.update(
            {
                "value": True,
                "email": email,
                "user_name": user_name,
                "result": result,
                "review_comment": review_comment,
            }
        ),
    )

    service.review_request(
        request_id=3,
        action="reject",
        review_comment="Insufficient verification details",
        reviewed_by_user_id=99,
    )

    assert sent["value"] is True
    assert sent["email"] == "educator@example.com"
    assert sent["result"] == "rejected"
    assert sent["review_comment"] == "Insufficient verification details"
