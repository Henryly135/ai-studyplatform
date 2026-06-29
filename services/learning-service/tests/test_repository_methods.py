from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from app.models.course_enrollment_audit_logs import EnrollmentAuditActionType, EnrollmentAuditActorRole
from app.models.course_enrollments import EnrollmentStatus
from app.models.courses import CourseStatus, DifficultyLevelStatus
from app.models.module_material_upload_sessions import MaterialUploadSessionStatus
from app.models.module_materials import MaterialType
from app.models.module_progress import ProgressStatus
from app.models.modules import ModuleStatus
from app.models.quizzes import QuizStatus
from app.models.short_answer_assessments import ShortAnswerAssessmentStatus
from app.models.short_answer_submissions import ShortAnswerSubmissionStatus
from app.repositories.course_enrollment_audit_log_repository import CourseEnrollmentAuditLogRepository
from app.repositories.course_enrollment_repository import CourseEnrollmentRepository
from app.repositories.course_invite_token_repository import CourseInviteTokenRepository
from app.repositories.course_repository import CourseRepository
from app.repositories.learning_path_repository import LearningPathRepository
from app.repositories.module_material_repository import ModuleMaterialRepository
from app.repositories.module_material_upload_session_repository import ModuleMaterialUploadSessionRepository
from app.repositories.module_prerequisite_repository import ModulePrerequisiteRepository
from app.repositories.module_progress_repository import ModuleProgressRepository
from app.repositories.module_repository import ModuleRepository
from app.repositories.quiz_attempt_answer_repository import QuizAttemptAnswerRepository
from app.repositories.quiz_attempt_repository import QuizAttemptRepository
from app.repositories.quiz_question_option_repository import QuizQuestionOptionRepository
from app.repositories.quiz_question_repository import QuizQuestionRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.short_answer_assessment_repository import ShortAnswerAssessmentRepository
from app.repositories.short_answer_submission_repository import ShortAnswerSubmissionRepository


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


def test_course_repository_queries_create_update_status_paginate_and_delete():
    # Tests course repository query helpers, pagination, create/update/status, touch, and delete.
    course = SimpleNamespace(
        course_id=1,
        title="Old",
        subtitle=None,
        description=None,
        cover_image_url=None,
        difficulty_level=None,
        estimated_minutes=None,
        category=None,
        language_code=None,
        is_public=False,
        published_at=None,
        status=CourseStatus.DRAFT,
        updated_at=datetime(2024, 1, 1),
    )
    session = FakeSession(scalar_result=2, scalars_result=[course], get_result=course)
    repo = CourseRepository(session)

    assert repo.get_by_id(1) is course
    assert repo.get_by_title("Old") == 2
    assert repo.list_all() == [course]
    assert repo.list_by_educator(7) == [course]
    assert repo.list_by_ids([]) == []
    assert repo.list_by_ids([1]) == [course]
    assert repo.list_public_courses() == [course]
    assert repo.search_by_title_or_subtitle(" old ") == [course]
    assert repo.list_by_status(CourseStatus.DRAFT) == [course]
    items, total, page, total_pages = repo.list_all_paginated(search="old", page=9, page_size=1)
    assert (items, total, page, total_pages) == ([course], 2, 2, 2)

    created = repo.create(
        educator_id=7,
        title="New",
        subtitle="Sub",
        description="Desc",
        cover_image_url="cover",
        status=CourseStatus.PUBLISHED,
        difficulty_level=DifficultyLevelStatus.BEGINNER,
        estimated_minutes=10,
        category="cat",
        language_code="en",
        is_public=True,
        published_at=datetime(2024, 1, 2),
    )
    repo.update(created, title="Updated", subtitle=None, description="D", is_public=False)
    repo.update_status(created, status=CourseStatus.ARCHIVED, is_public=False, published_at=None)
    repo.touch(created)
    repo.delete(created)

    assert session.added[0].title == "Updated"
    assert created.status == CourseStatus.ARCHIVED
    assert session.deleted == [created]


def test_learning_path_module_material_and_prerequisite_repositories_cover_crud():
    # Tests learning path, module, material, upload session, and prerequisite repository CRUD paths.
    path = SimpleNamespace(learning_path_id=10, title="Path", description=None)
    module = SimpleNamespace(module_id=20, sort_order=1, title="Module", status=ModuleStatus.DRAFT)
    material = SimpleNamespace(material_id=30, sort_order=1, title="Material", material_type=MaterialType.PDF)
    upload = SimpleNamespace(session_uuid="sess", status=MaterialUploadSessionStatus.INITIATED, material_id=None, metadata_json=None)
    rule = SimpleNamespace(module_id=20, prerequisite_module_id=19)
    session = FakeSession(scalar_result=rule, scalars_result=[module], get_result=path)

    paths = LearningPathRepository(session)
    modules = ModuleRepository(session)
    materials = ModuleMaterialRepository(session)
    uploads = ModuleMaterialUploadSessionRepository(session)
    prerequisites = ModulePrerequisiteRepository(session)

    assert paths.get_by_id(10) is path
    assert paths.get_by_course_id(1) is rule
    assert paths.list_all() == [module]
    created_path = paths.create(course_id=1, title="Created", description="Desc")
    paths.update(created_path, title="Renamed", description=None)
    paths.delete(created_path)

    assert modules.get_by_id(20) is path
    assert modules.list_by_learning_path(10) == [module]
    assert modules.list_by_ids([]) == []
    assert modules.list_by_ids([20]) == [module]
    assert modules.list_published_by_learning_path(10) == [module]
    assert modules.get_by_learning_path_and_sort_order(10, 1) is rule
    assert modules.get_max_sort_order(10) == 1
    created_module = modules.create(learning_path_id=10, title="M", description=None, content=None, sort_order=2)
    modules.update(created_module, title="M2", status=ModuleStatus.PUBLISHED, visible_to_class_id="class")
    modules.delete(created_module)

    assert materials.get_by_id(30) is path
    assert materials.list_by_module(20) == [module]
    assert materials.get_by_module_and_sort_order(20, 1) is rule
    assert materials.get_max_sort_order(20) == 1
    assert materials.list_by_type(20, MaterialType.PDF) == [module]
    created_material = materials.create(module_id=20, title="Doc", material_type=MaterialType.PDF, resource_url="url", sort_order=1)
    materials.update(created_material, title="Doc2", metadata_json={"a": 1})
    materials.delete(created_material)

    assert uploads.get_by_session_uuid("sess") is rule
    assert uploads.list_active_by_module_and_sort_order(20, 1) == [module]
    assert uploads.get_active_by_module_and_sort_order(20, 1) == module
    created_upload = uploads.create(
        session_uuid="sess",
        module_id=20,
        created_by_user_id=7,
        title="Upload",
        material_type=MaterialType.PDF,
        sort_order=1,
        original_filename="a.pdf",
        content_type="application/pdf",
        size_bytes=100,
        storage_provider="minio",
        bucket="bucket",
        object_key="key",
        multipart_upload_id="upload",
    )
    uploads.update(created_upload, status=MaterialUploadSessionStatus.COMPLETED, material_id=30, metadata_json={"ok": True})

    assert prerequisites.get_by_module_id(20) is rule
    assert prerequisites.create(module_id=20, prerequisite_module_id=19).prerequisite_module_id == 19
    assert prerequisites.update(rule, prerequisite_module_id=18).prerequisite_module_id == 18
    assert prerequisites.upsert(module_id=20, prerequisite_module_id=17).prerequisite_module_id == 17
    prerequisites.delete(rule)


def test_progress_enrollment_invite_and_audit_repositories_cover_workflows():
    # Tests progress, enrollment, invite token, and enrollment audit repository workflows.
    now = datetime(2024, 1, 1, 12, 0, 0)
    progress = SimpleNamespace(
        module_progress_id=1,
        progress_status=ProgressStatus.NOT_STARTED,
        progress_percent=Decimal("0.00"),
        time_spent_seconds=0,
        last_accessed_at=None,
    )
    enrollment = SimpleNamespace(
        enrollment_id=2,
        enrollment_status=EnrollmentStatus.ACTIVE,
        progress_percent=Decimal("0.00"),
        completed_module_count=0,
        total_module_count=0,
        last_accessed_at=None,
        completed_at=None,
    )
    row = SimpleNamespace(
        course_id=1,
        title="Course",
        status=CourseStatus.PUBLISHED,
        total_enrollments=2,
        active_enrollments=1,
        completed_enrollments=1,
        avg_progress_percent=Decimal("50.00"),
    )
    module_stats_row = SimpleNamespace(
        module_id=20,
        started_count=1,
        completed_count=1,
        avg_progress_percent=Decimal("75.00"),
    )
    session = FakeSession(scalar_result=enrollment, scalars_result=[progress], execute_result=[row], get_result=progress)
    progress_repo = ModuleProgressRepository(session)
    enrollment_repo = CourseEnrollmentRepository(session)
    invite_repo = CourseInviteTokenRepository(session)
    audit_repo = CourseEnrollmentAuditLogRepository(session)

    assert progress_repo.get_by_id(1) is progress
    assert progress_repo.get_by_module_and_learner(20, 7) is enrollment
    assert progress_repo.list_by_module(20) == [progress]
    assert progress_repo.list_by_module_ids([20]) == [progress]
    assert progress_repo.list_by_module_ids([]) == []
    assert progress_repo.list_by_learner(7) == [progress]
    assert progress_repo.list_completed_by_learner(7) == [progress]
    session.execute_result = [module_stats_row]
    assert progress_repo.aggregate_stats_by_module_ids([20])[0]["avg_progress_percent"] == 75.0
    assert progress_repo.aggregate_stats_by_module_ids([]) == []
    created_progress = progress_repo.create(module_id=20, learner_id=7)
    progress_repo.update_progress(
        created_progress,
        progress_status=ProgressStatus.COMPLETED,
        progress_percent=Decimal("100.00"),
        time_spent_seconds=60,
        last_accessed_at=now,
        completed_at=now,
    )
    progress_repo.touch_last_accessed(created_progress, now)
    progress_repo.delete(created_progress)

    assert enrollment_repo.get_by_id(2) is progress
    assert enrollment_repo.get_by_course_and_learner(1, 7) is enrollment
    assert enrollment_repo.list_by_course(1) == [progress]
    assert enrollment_repo.list_current_by_course(1) == [progress]
    assert enrollment_repo.list_by_learner(7) == [progress]
    assert enrollment_repo.list_active_by_learner(7) == [progress]
    created_enrollment = enrollment_repo.create(course_id=1, learner_id=7)
    enrollment_repo.update_progress(created_enrollment, progress_percent=Decimal("50.00"), completed_module_count=1, total_module_count=2)
    enrollment_repo.update_status(created_enrollment, enrollment_status=EnrollmentStatus.COMPLETED, completed_at=now)
    enrollment_repo.touch_last_accessed(created_enrollment, now)
    session.execute_result = [row]
    assert enrollment_repo.aggregate_stats_by_educator(educator_id=9)[0]["avg_progress_percent"] == 50.0
    enrollment_repo.delete(created_enrollment)

    invite = invite_repo.create(course_id=1, created_by=9, expires_at=datetime.now() + timedelta(days=1))
    session.scalar_result = invite
    assert invite.is_active is True
    assert invite_repo.get_valid_by_uuid(invite.invite_uuid) is invite
    assert invite_repo.get_by_uuid(invite.invite_uuid) is invite
    assert invite_repo.list_by_course(1) == [progress]
    invite_repo.deactivate(invite)
    assert invite.is_active is False

    audit = audit_repo.create(
        enrollment_id=2,
        course_id=1,
        learner_id=7,
        action_type=EnrollmentAuditActionType.ENROLLED,
        changed_by_role=EnrollmentAuditActorRole.LEARNER,
        new_status="active",
    )
    assert audit.new_status == "active"
    assert audit_repo.list_by_enrollment(2) == [progress]
    assert audit_repo.list_by_course(1) == [progress]
    assert audit_repo.list_by_learner(7) == [progress]


def test_quiz_repositories_cover_authoring_attempt_and_answer_paths():
    # Tests quiz, question, option, attempt, and attempt-answer repository paths.
    now = datetime(2024, 1, 1, 12, 0, 0)
    quiz = SimpleNamespace(quiz_id=1, module_id=20, title="Quiz", status=QuizStatus.DRAFT)
    question = SimpleNamespace(quiz_question_id=2, question_text="Q", explanation_text=None, sort_order=1, is_active=True)
    option = SimpleNamespace(quiz_question_option_id=3, option_text="A", sort_order=1, is_correct=True)
    stats_row = SimpleNamespace(
        course_id=1,
        course_title="Course",
        module_id=20,
        module_title="Module",
        quiz_title="Quiz",
        total_attempts=1,
        unique_learners=1,
        avg_score_percent=Decimal("100.00"),
        pass_rate=1.0,
        avg_duration_seconds=30,
    )
    session = FakeSession(scalar_result=1, scalars_result=[question], execute_result=[stats_row], get_result=quiz)
    quizzes = QuizRepository(session)
    questions = QuizQuestionRepository(session)
    options = QuizQuestionOptionRepository(session)
    attempts = QuizAttemptRepository(session)
    answers = QuizAttemptAnswerRepository(session)

    assert quizzes.get_by_id(1) is quiz
    assert quizzes.get_by_module_id(20) == 1
    created_quiz = quizzes.create(
        module_id=20,
        title="Quiz",
        description=None,
        status=QuizStatus.DRAFT,
        time_limit_seconds=60,
        question_count_per_attempt=2,
        shuffle_questions=True,
        shuffle_options=False,
    )
    quizzes.update(created_quiz, title="Quiz 2", status=QuizStatus.PUBLISHED, published_at=now)
    quizzes.delete(created_quiz)

    assert questions.list_by_quiz(1) == [question]
    assert questions.list_by_quiz_page(1, page=1, page_size=10, query="q") == ([question], 1)
    assert questions.count_by_quiz(1, active_only=True) == 1
    assert questions.list_active_by_quiz(1) == [question]
    assert questions.list_by_ids([]) == []
    assert questions.list_by_ids([2]) == [question]
    assert questions.get_by_id(2) is quiz
    created_question = questions.create(quiz_id=1, question_text="Q", explanation_text=None, sort_order=1, is_active=True)
    questions.update(created_question, question_text="Q2", explanation_text="E", sort_order=2, is_active=False)
    questions.delete_by_quiz(1)

    assert options.list_by_question(2) == [question]
    assert options.get_by_id(3) is quiz
    created_option = options.create(quiz_question_id=2, option_label="A", option_text="Answer", sort_order=1, is_correct=True)
    assert created_option.option_text == "Answer"
    options.delete_by_question(2)

    assert attempts.get_by_id(4) is quiz
    assert attempts.list_by_quiz_and_learner(quiz_id=1, learner_id=7) == [question]
    assert attempts.has_passed_quiz(quiz_id=1, learner_id=7) is True
    assert attempts.get_max_attempt_number(quiz_id=1, learner_id=7) == 1
    assert attempts.count_by_quiz(quiz_id=1) == 1
    assert attempts.aggregate_stats_by_educator(educator_id=9)[0]["pass_rate"] == 1.0
    created_attempt = attempts.create(
        quiz_id=1,
        module_id=20,
        learner_id=7,
        attempt_number=1,
        question_count=1,
        correct_count=1,
        score_percent=Decimal("100.00"),
        is_passed=True,
        is_timed_out=False,
        time_limit_seconds_snapshot=60,
        started_at=now,
        submitted_at=now,
        duration_seconds=30,
    )
    assert created_attempt.is_passed is True

    assert answers.list_by_attempt(4) == [question]
    assert answers.count_by_question(2) == 1
    created_answer = answers.create(
        quiz_attempt_id=4,
        quiz_question_id=2,
        selected_option_id=3,
        is_correct=True,
        question_order=1,
        question_text_snapshot="Q",
        explanation_text_snapshot=None,
        selected_option_text_snapshot="A",
        correct_option_id_snapshot=3,
        correct_option_text_snapshot="A",
        option_order_snapshot_json=[3],
        option_texts_snapshot_json=[{"id": 3, "text": "A"}],
    )
    assert created_answer.correct_option_id_snapshot == 3


def test_short_answer_repositories_cover_assessment_and_submission_analytics():
    # Tests short-answer repository helpers used by educator teaching insights.
    now = datetime(2024, 1, 1, 12, 0, 0)
    assessment = SimpleNamespace(
        short_answer_assessment_id=10,
        assessment_uuid="assessment-uuid",
        module_id=20,
        title="Short answer",
        prompt_text="Explain it.",
        rubric_text="Clear rubric.",
        max_score=Decimal("10.00"),
        status=ShortAnswerAssessmentStatus.DRAFT,
        published_at=None,
    )
    aggregate_row = SimpleNamespace(
        assessment_id=10,
        submission_count=2,
        avg_ai_score=Decimal("6.50"),
        avg_final_score=Decimal("8.00"),
        pending_review_count=1,
    )
    session = FakeSession(
        scalar_result=assessment,
        scalars_result=[assessment],
        execute_result=[aggregate_row],
        get_result=assessment,
    )
    assessments = ShortAnswerAssessmentRepository(session)
    submissions = ShortAnswerSubmissionRepository(session)

    assert assessments.get_by_id(10) is assessment
    assert assessments.get_by_uuid("assessment-uuid") is assessment
    assert assessments.get_by_module_id(20) is assessment
    assert assessments.list_by_module_ids([20]) == [assessment]
    assert assessments.list_by_module_ids([]) == []
    created_assessment = assessments.create(
        module_id=20,
        title="Created",
        prompt_text="Prompt",
        rubric_text="Rubric",
        max_score=Decimal("10.00"),
        status=ShortAnswerAssessmentStatus.DRAFT,
        created_by=9,
        updated_by=9,
        published_at=None,
    )
    assessments.update(created_assessment, status=ShortAnswerAssessmentStatus.PUBLISHED, published_at=now)

    assert submissions.get_by_id(11) is assessment
    assert submissions.get_by_uuid("submission-uuid") is assessment
    assert submissions.list_by_assessment(10) == [assessment]
    assert submissions.list_by_assessment_and_learner(10, 7) == [assessment]
    assert submissions.get_latest_by_assessment_and_learner(10, 7) is assessment
    assert submissions.aggregate_stats_by_assessment_ids([10])[0]["pending_review_count"] == 1
    assert submissions.aggregate_stats_by_assessment_ids([]) == []
    created_submission = submissions.create(
        assessment_id=10,
        learner_id=7,
        answer_text="Answer",
        ai_score_suggestion=Decimal("6.00"),
        ai_feedback_text="Feedback",
        ai_strengths_json=["Clear"],
        ai_improvements_json=["More detail"],
        ai_provider_name="test",
        ai_provider_model="stub",
        status=ShortAnswerSubmissionStatus.AI_SUGGESTED,
    )
    submissions.update_review(
        created_submission,
        final_score=Decimal("7.00"),
        final_feedback_text="Final",
        review_notes=None,
        reviewer_id=9,
        reviewed_at=now,
    )

    assert created_assessment.status == ShortAnswerAssessmentStatus.PUBLISHED
    assert created_submission.status == ShortAnswerSubmissionStatus.REVIEWED
