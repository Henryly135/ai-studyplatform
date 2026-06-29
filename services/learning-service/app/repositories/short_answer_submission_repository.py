from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.short_answer_submissions import ShortAnswerSubmission, ShortAnswerSubmissionStatus

_UNSET = object()


class ShortAnswerSubmissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, submission_id: int) -> ShortAnswerSubmission | None:
        return self.session.get(ShortAnswerSubmission, submission_id)

    def get_by_uuid(self, submission_uuid: str) -> ShortAnswerSubmission | None:
        stmt = select(ShortAnswerSubmission).where(ShortAnswerSubmission.submission_uuid == submission_uuid)
        return self.session.scalar(stmt)

    def list_by_assessment(self, assessment_id: int) -> list[ShortAnswerSubmission]:
        stmt = (
            select(ShortAnswerSubmission)
            .where(ShortAnswerSubmission.assessment_id == assessment_id)
            .order_by(ShortAnswerSubmission.updated_at.desc(), ShortAnswerSubmission.short_answer_submission_id.desc())
        )
        return list(self.session.scalars(stmt))

    def aggregate_stats_by_assessment_ids(self, assessment_ids: list[int]) -> list[dict]:
        if not assessment_ids:
            return []
        stmt = (
            select(
                ShortAnswerSubmission.assessment_id,
                func.count(ShortAnswerSubmission.short_answer_submission_id).label("submission_count"),
                func.avg(ShortAnswerSubmission.ai_score_suggestion).label("avg_ai_score"),
                func.avg(ShortAnswerSubmission.final_score).label("avg_final_score"),
                func.count(
                    case(
                        (
                            ShortAnswerSubmission.status != ShortAnswerSubmissionStatus.REVIEWED,
                            ShortAnswerSubmission.short_answer_submission_id,
                        ),
                        else_=None,
                    )
                ).label("pending_review_count"),
            )
            .where(ShortAnswerSubmission.assessment_id.in_(assessment_ids))
            .group_by(ShortAnswerSubmission.assessment_id)
        )

        rows = self.session.execute(stmt).all()
        return [
            {
                "assessment_id": row.assessment_id,
                "submission_count": row.submission_count or 0,
                "avg_ai_score": float(row.avg_ai_score) if row.avg_ai_score is not None else None,
                "avg_final_score": float(row.avg_final_score) if row.avg_final_score is not None else None,
                "pending_review_count": row.pending_review_count or 0,
            }
            for row in rows
        ]

    def list_by_assessment_and_learner(self, assessment_id: int, learner_id: int) -> list[ShortAnswerSubmission]:
        stmt = (
            select(ShortAnswerSubmission)
            .where(
                ShortAnswerSubmission.assessment_id == assessment_id,
                ShortAnswerSubmission.learner_id == learner_id,
            )
            .order_by(ShortAnswerSubmission.updated_at.desc(), ShortAnswerSubmission.short_answer_submission_id.desc())
        )
        return list(self.session.scalars(stmt))

    def get_latest_by_assessment_and_learner(self, assessment_id: int, learner_id: int) -> ShortAnswerSubmission | None:
        rows = self.list_by_assessment_and_learner(assessment_id, learner_id)
        return rows[0] if rows else None

    def create(
        self,
        *,
        assessment_id: int,
        learner_id: int,
        answer_text: str,
        ai_score_suggestion: Decimal | None,
        ai_feedback_text: str | None,
        ai_strengths_json: list[str] | None,
        ai_improvements_json: list[str] | None,
        ai_provider_name: str | None,
        ai_provider_model: str | None,
        status: ShortAnswerSubmissionStatus,
    ) -> ShortAnswerSubmission:
        submission = ShortAnswerSubmission(
            assessment_id=assessment_id,
            learner_id=learner_id,
            answer_text=answer_text,
            ai_score_suggestion=ai_score_suggestion,
            ai_feedback_text=ai_feedback_text,
            ai_strengths_json=ai_strengths_json,
            ai_improvements_json=ai_improvements_json,
            ai_provider_name=ai_provider_name,
            ai_provider_model=ai_provider_model,
            status=status,
        )
        self.session.add(submission)
        self.session.flush()
        return submission

    def update_review(
        self,
        submission: ShortAnswerSubmission,
        *,
        final_score: Decimal,
        final_feedback_text: str,
        review_notes: str | None,
        reviewer_id: int,
        reviewed_at: datetime,
    ) -> ShortAnswerSubmission:
        submission.final_score = final_score
        submission.final_feedback_text = final_feedback_text
        submission.review_notes = review_notes
        submission.reviewer_id = reviewer_id
        submission.reviewed_at = reviewed_at
        submission.status = ShortAnswerSubmissionStatus.REVIEWED
        self.session.flush()
        return submission
