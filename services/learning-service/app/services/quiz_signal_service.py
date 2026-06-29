from __future__ import annotations

from collections import Counter

from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.quiz_attempt_answer_repository import QuizAttemptAnswerRepository
from app.repositories.quiz_attempt_repository import QuizAttemptRepository
from app.repositories.quiz_repository import QuizRepository
from app.schemas.profile_update import (
    QuizSignalQuestionEvidenceRead,
    QuizSignalSummaryDetailRead,
    QuizSignalSummaryRequest,
    QuizSignalSummaryResponse,
    SignalTimeWindowRead,
)


class QuizSignalService:
    def __init__(self, session) -> None:
        self.session = session
        self.courses = CourseRepository(session)
        self.learning_paths = LearningPathRepository(session)
        self.modules = ModuleRepository(session)
        self.quizzes = QuizRepository(session)
        self.attempts = QuizAttemptRepository(session)
        self.attempt_answers = QuizAttemptAnswerRepository(session)

    def build_summary(self, *, payload: QuizSignalSummaryRequest) -> QuizSignalSummaryResponse:
        course = self.courses.get_by_id(payload.courseId)
        if course is None:
            return self._unavailable(reason="course_not_found")

        learning_path = self.learning_paths.get_by_course_id(course.course_id)
        if learning_path is None:
            return self._unavailable(reason="learning_path_not_found")

        module = self.modules.get_by_id(payload.moduleId)
        if module is None or module.learning_path_id != learning_path.learning_path_id:
            return self._unavailable(reason="module_not_found")

        quiz = self.quizzes.get_by_module_id(module.module_id)
        if quiz is None:
            return self._unavailable(reason="quiz_not_found")

        recent_attempts = self.attempts.list_by_quiz_and_learner(
            quiz_id=quiz.quiz_id,
            learner_id=payload.learnerId,
        )[: payload.maxAttempts]
        if not recent_attempts:
            return self._unavailable(reason="no_quiz_attempts")

        latest_attempt = recent_attempts[0]
        answers = self.attempt_answers.list_by_attempt(latest_attempt.quiz_attempt_id)
        question_evidence = [
            QuizSignalQuestionEvidenceRead(
                questionOrder=answer.question_order,
                questionText=answer.question_text_snapshot,
                explanationText=answer.explanation_text_snapshot,
                selectedOptionText=answer.selected_option_text_snapshot,
                correctOptionText=answer.correct_option_text_snapshot,
                isCorrect=answer.is_correct,
            )
            for answer in answers
        ]

        error_patterns = self._extract_repeated_error_patterns(question_evidence)
        recommended_focus = self._build_recommended_focus(question_evidence)
        avg_time = (
            float(latest_attempt.duration_seconds) / latest_attempt.question_count
            if latest_attempt.duration_seconds is not None and latest_attempt.question_count > 0
            else None
        )
        latest_score = float(latest_attempt.score_percent)
        previous_score = float(recent_attempts[1].score_percent) if len(recent_attempts) > 1 else None

        summary = QuizSignalSummaryDetailRead(
            quizAttemptId=latest_attempt.quiz_attempt_id,
            attemptNumber=latest_attempt.attempt_number,
            scorePercent=latest_score,
            questionCount=latest_attempt.question_count,
            correctCount=latest_attempt.correct_count,
            incorrectCount=max(0, latest_attempt.question_count - latest_attempt.correct_count),
            isPassed=latest_attempt.is_passed,
            isTimedOut=latest_attempt.is_timed_out,
            durationSeconds=latest_attempt.duration_seconds,
            avgTimePerQuestionSec=avg_time,
            changeSignificance=self._derive_change_significance(
                latest_score=latest_score,
                previous_score=previous_score,
                incorrect_count=max(0, latest_attempt.question_count - latest_attempt.correct_count),
            ),
            confidenceShiftHint=self._derive_confidence_shift_hint(
                latest_score=latest_score,
                previous_score=previous_score,
            ),
            supportNeedShiftHint=self._derive_support_need_shift_hint(
                latest_score=latest_score,
                timed_out=latest_attempt.is_timed_out,
            ),
            repeatedErrorPatterns=error_patterns,
            recommendedFocusCandidates=recommended_focus,
            recentTrendSummary=self._build_trend_summary(
                latest_score=latest_score,
                previous_score=previous_score,
            ),
            questionEvidence=question_evidence,
        )
        return QuizSignalSummaryResponse(
            signalStrength=self._derive_signal_strength(
                score_percent=latest_score,
                incorrect_count=summary.incorrectCount,
            ),
            evidenceCount=len(question_evidence),
            timeWindow=SignalTimeWindowRead(
                startAt=latest_attempt.started_at,
                endAt=latest_attempt.submitted_at,
            ),
            summary=summary,
        )

    def _unavailable(self, *, reason: str) -> QuizSignalSummaryResponse:
        return QuizSignalSummaryResponse(
            available=False,
            unavailableReason=reason,
            signalStrength="none",
            evidenceCount=0,
            timeWindow=None,
            summary=None,
        )

    def _extract_repeated_error_patterns(
        self,
        question_evidence: list[QuizSignalQuestionEvidenceRead],
    ) -> list[str]:
        incorrect_questions = [
            evidence.questionText.strip()
            for evidence in question_evidence
            if not evidence.isCorrect and evidence.questionText.strip()
        ]
        top_questions = Counter(incorrect_questions).most_common(3)
        patterns = [question for question, _ in top_questions]
        if patterns:
            return patterns
        return [evidence.questionText for evidence in question_evidence if not evidence.isCorrect][:3]

    def _build_recommended_focus(
        self,
        question_evidence: list[QuizSignalQuestionEvidenceRead],
    ) -> list[str]:
        focus_items: list[str] = []
        for evidence in question_evidence:
            if evidence.isCorrect:
                continue
            if evidence.explanationText:
                focus_items.append(evidence.explanationText.strip())
            else:
                focus_items.append(evidence.questionText.strip())
        unique_items: list[str] = []
        for item in focus_items:
            if item and item not in unique_items:
                unique_items.append(item)
        return unique_items[:3]

    def _build_trend_summary(self, *, latest_score: float, previous_score: float | None) -> str | None:
        if previous_score is None:
            return None
        delta = latest_score - previous_score
        if abs(delta) < 0.01:
            return "Performance is stable compared with the previous attempt."
        direction = "improved" if delta > 0 else "declined"
        return f"Performance {direction} by {abs(delta):.2f} percentage points compared with the previous attempt."

    def _derive_signal_strength(self, *, score_percent: float, incorrect_count: int) -> str:
        if incorrect_count == 0 and score_percent >= 90:
            return "low"
        if incorrect_count >= 3 or score_percent < 60:
            return "high"
        return "medium"

    def _derive_change_significance(
        self,
        *,
        latest_score: float,
        previous_score: float | None,
        incorrect_count: int,
    ) -> str:
        if previous_score is not None and abs(latest_score - previous_score) >= 20:
            return "major"
        if incorrect_count >= 3 or latest_score < 60:
            return "major"
        if incorrect_count >= 1:
            return "moderate"
        return "minor"

    def _derive_confidence_shift_hint(self, *, latest_score: float, previous_score: float | None) -> str:
        if previous_score is not None:
            if latest_score - previous_score >= 10:
                return "up"
            if previous_score - latest_score >= 10:
                return "down"
        if latest_score >= 85:
            return "up"
        if latest_score < 60:
            return "down"
        return "stable"

    def _derive_support_need_shift_hint(self, *, latest_score: float, timed_out: bool) -> str:
        if timed_out or latest_score < 60:
            return "up"
        if latest_score >= 85:
            return "down"
        return "stable"
