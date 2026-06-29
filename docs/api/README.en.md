# API Overview

The backend is composed of four FastAPI services exposed to the frontend through nginx. Public APIs mostly use camelCase fields, while some AI chat history interfaces still use snake_case fields.

中文版本: [README.md](README.md)

## Service Entry Points

| Service | nginx Prefix | Code Directory | Responsibility |
| --- | --- | --- | --- |
| Identity | `/api` | `services/identity-service` | Registration, login, email verification, passwords, users, roles, permissions |
| Learning | `/api/learning` | `services/learning-service` | Courses, modules, materials, progress, enrollment, quizzes, analytics |
| Communication | `/api/communication` | `services/communication-service` | Forums, comments, in-app notifications |
| AI | `/api/ai` | `services/ai-service` | AI chat, RAG, material indexing, profiles, AI tasks |

## Identity API

Main capabilities:

- Registration, login, and current-user lookup.
- Email verification and resend verification email.
- Forgot password, reset password, and change password.
- Current-user permission lookup.
- Admin user listing, status updates, and role-related operations.
- Educator approval and educator invite links.
- Internal user directory lookup for other services.

Key files:

- `services/identity-service/app/api/auth.py`
- `services/identity-service/app/api/admin.py`
- `services/identity-service/app/api/internal.py`

## Learning API

Main capabilities:

- Course creation, update, publication, search, and detail lookup.
- Module creation, ordering, publication, prerequisites, and progress.
- Course enrollment, unenrollment, and invite links.
- Material upload, multipart upload, deletion, and public access.
- Manual quiz authoring, publication, and learner attempts.
- AI-generated quiz context lookup, generated-question persistence, and educator draft preview/acceptance.
- Short-answer assessment: educator rubrics, learner submissions, AI suggested feedback, and educator review.
- Learner Study Planner generation, lookup, adjustment, and regeneration.
- Educator course and quiz analytics.

Learner Study Planner:

- `POST /api/learning/study-plans`: learner creates a study plan. The request includes the learning goal, weekly availability, target date, preferences, and material summaries; `learning-service` saves plan metadata, inputs, and learner-visible content, then calls `ai-service` through an internal endpoint to generate the plan content.
- `GET /api/learning/study-plans`: learner lists their own study plans.
- `GET /api/learning/study-plans/{planUuid}`: learner reads one owned study plan; other users and non-owners cannot access it.
- `PATCH /api/learning/study-plans/{planUuid}`: learner adjusts the title, status, plan content, or notes for an owned plan.
- `POST /api/learning/study-plans/{planUuid}/regenerate`: learner regenerates plan content from the original input.

These endpoints are learner-only. `learning-service` owns persistence, while `ai-service` is called only through the internal `study-planner` endpoint to generate staged phases, topic order, review cadence, and rationale.

Educator AI Quiz Draft:

- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/quiz/management/ai-draft`: educator owner/admin generates an AI draft preview from module materials. The request includes title, question count, difficulty, question types, learning objectives, material scope, and educator instructions; `learning-service` calls internal `ai-service`, validates candidate counts, options, correct answers, and `sourceGrounding`, and does not write the question pool.
- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/quiz/management/ai-draft/accept`: educator accepts a reviewed preview into the existing quiz authoring draft. The request can replace or append questions; saved results remain unpublished/draft and continue through the existing edit and publish flow.

These endpoints are limited to educator owner/admin users with module update permission. `learning-service` persists quiz metadata, questions, options, and per-question source grounding; `ai-service` only generates candidate content.

Short-Answer Assessment:

- `PUT /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management`: educator owner/admin creates or updates the module short-answer assessment, including title, prompt, rubric, max score, and status.
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management`: educator reads the module short-answer assessment.
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management/submissions`: educator lists learner submissions, AI suggested scores, and feedback.
- `PATCH /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/management/submissions/{submissionUuid}/review`: educator reviews a submission and publishes final score and feedback.
- `GET /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer`: learner reads the published short-answer assessment and their latest submission.
- `POST /api/learning/courses/{courseUuid}/modules/{moduleUuid}/short-answer/submissions`: learner submits an answer; before persistence, `learning-service` calls internal `ai-service` for suggested score, feedback, strengths, and improvements.

Learner endpoints require learner identity, course enrollment, and module unlock. Educator management endpoints require module update permission. AI feedback is advisory until the educator review endpoint confirms final score and visible feedback.

Key files:

- `services/learning-service/app/api/course_management.py`
- `services/learning-service/app/api/course_catalog.py`
- `services/learning-service/app/api/module_management.py`
- `services/learning-service/app/api/module_content.py`
- `services/learning-service/app/api/quiz.py`
- `services/learning-service/app/api/short_answer.py`
- `services/learning-service/app/api/internal_quiz_generation.py`
- `services/learning-service/app/api/study_planner.py`

## Communication API

Main capabilities:

- Course forum post creation, listing, update, and deletion.
- Comments, replies, deletion, and pinning.
- System notification creation.
- User notification list, unread count, mark-read, hide, and restore.

Key files:

- `services/communication-service/app/api/forum.py`
- `services/communication-service/app/api/notifications.py`
- `services/communication-service/app/api/internal_notifications.py`

## AI API

Main capabilities:

- AI chat and session history.
- RAG retrieval over course materials with grounded responses.
- Material indexing job registration, status lookup, retry, and recovery.
- Learner profile initialization and module profile updates.
- AI quiz generation workflow.
- Internal educator AI quiz draft generation endpoint for `learning-service`.
- Internal short-answer evaluation endpoint for `learning-service`.
- Internal Study Planner generation endpoint for `learning-service`.
- Celery smoke tasks and task status lookup.

Key files:

- `services/ai-service/app/api/chat.py`
- `services/ai-service/app/api/tasks.py`
- `services/ai-service/app/api/internal_index_jobs.py`
- `services/ai-service/app/api/internal_profile_update.py`
- `services/ai-service/app/api/internal_quiz_generation.py`
- `services/ai-service/app/api/internal_study_planner.py`
- `services/ai-service/app/api/profiles.py`

Internal AI quiz endpoint:

- `POST /api/ai/internal/quiz-generation/educator-draft`: internal endpoint called only by `learning-service` with the internal token. It returns candidate questions, retrieval context, and the plan; each question includes `sourceGrounding`. nginx should not expose this endpoint directly to browsers.
- `POST /api/ai/internal/short-answer/evaluate`: internal endpoint called only by `learning-service` with the internal token. It accepts prompt, rubric, max score, and learner answer, then returns suggested score, feedback, strengths, and improvements. The current implementation is a mock-friendly local evaluator that can later be replaced by a provider-backed workflow.

## Authentication

- The frontend calls backend services with JWT Bearer Tokens.
- nginx exposes only public prefixes and blocks protected internal routes.
- Cross-service calls use internal HTTP clients and shared user context.
- Permission constants live under `packages/platform_common/platform_common/permissions/`.

## Error Handling

- Services return structured errors through shared error helpers.
- Public APIs should return clear business errors.
- Internal API failures should preserve logs without exposing sensitive details to the frontend.
