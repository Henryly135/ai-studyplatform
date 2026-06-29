from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import now_local
from app.models.educator_approval_request import EducatorApprovalRequest, RequestStatus


class ApprovalRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_request(
        self,
        *,
        user_id: int,
        supporting_info: str | None = None,
        supporting_file_url: str | None = None,
    ) -> EducatorApprovalRequest:
        """Used by educator registration services to submit a new approval request."""
        request = EducatorApprovalRequest(
            user_id=user_id,
            supporting_info=supporting_info,
            supporting_file_url=supporting_file_url,
        )
        self.session.add(request)
        self.session.flush()
        return request

    def get_by_id(self, request_id: int) -> EducatorApprovalRequest | None:
        """Used by approval workflow services to load a specific approval request."""
        return self.session.get(EducatorApprovalRequest, request_id)

    def get_pending_requests(self) -> list[EducatorApprovalRequest]:
        """Used by admin approval queue services to fetch requests waiting for review."""
        stmt = (
            select(EducatorApprovalRequest)
            .where(EducatorApprovalRequest.request_status == RequestStatus.PENDING)
            .order_by(EducatorApprovalRequest.submitted_at)
        )
        return list(self.session.scalars(stmt))

    def get_pending_request_by_user_id(self, user_id: int) -> EducatorApprovalRequest | None:
        stmt = (
            select(EducatorApprovalRequest)
            .where(
                EducatorApprovalRequest.user_id == user_id,
                EducatorApprovalRequest.request_status == RequestStatus.PENDING,
            )
            .order_by(EducatorApprovalRequest.submitted_at.desc())
        )
        return self.session.scalar(stmt)

    def get_reviewed_requests(
        self,
        *,
        request_status: RequestStatus | None = None,
    ) -> list[EducatorApprovalRequest]:
        """Used by admin approval history services to fetch reviewed approval requests."""
        stmt = select(EducatorApprovalRequest).where(
            EducatorApprovalRequest.request_status != RequestStatus.PENDING
        )
        if request_status is not None:
            stmt = stmt.where(EducatorApprovalRequest.request_status == request_status)
        stmt = stmt.order_by(
            EducatorApprovalRequest.reviewed_at.desc(),
            EducatorApprovalRequest.updated_at.desc(),
            EducatorApprovalRequest.request_id.desc(),
        )
        return list(self.session.scalars(stmt))

    def list_by_user(self, user_id: int) -> list[EducatorApprovalRequest]:
        """Used by profile and approval history services to fetch a user's submissions."""
        stmt = (
            select(EducatorApprovalRequest)
            .where(EducatorApprovalRequest.user_id == user_id)
            .order_by(EducatorApprovalRequest.submitted_at.desc())
        )
        return list(self.session.scalars(stmt))

    def update_status(
        self,
        request: EducatorApprovalRequest,
        *,
        request_status: RequestStatus,
        reviewed_by: int | None = None,
        review_comment: str | None = None,
        reviewed_at: datetime | None = None,
    ) -> EducatorApprovalRequest:
        """Used by admin approval services to persist a review decision and reviewer metadata."""
        request.request_status = request_status
        request.reviewed_by = reviewed_by
        request.review_comment = review_comment
        request.reviewed_at = reviewed_at or now_local()
        self.session.flush()
        return request
