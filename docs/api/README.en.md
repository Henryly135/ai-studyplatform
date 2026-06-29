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
- AI-generated quiz context lookup and generated-question persistence.
- Educator course and quiz analytics.

Key files:

- `services/learning-service/app/api/course_management.py`
- `services/learning-service/app/api/course_catalog.py`
- `services/learning-service/app/api/module_management.py`
- `services/learning-service/app/api/module_content.py`
- `services/learning-service/app/api/quiz.py`
- `services/learning-service/app/api/internal_quiz_generation.py`

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
- Celery smoke tasks and task status lookup.

Key files:

- `services/ai-service/app/api/chat.py`
- `services/ai-service/app/api/tasks.py`
- `services/ai-service/app/api/internal_index_jobs.py`
- `services/ai-service/app/api/internal_profile_update.py`
- `services/ai-service/app/api/internal_quiz_generation.py`
- `services/ai-service/app/api/profiles.py`

## Authentication

- The frontend calls backend services with JWT Bearer Tokens.
- nginx exposes only public prefixes and blocks protected internal routes.
- Cross-service calls use internal HTTP clients and shared user context.
- Permission constants live under `packages/platform_common/platform_common/permissions/`.

## Error Handling

- Services return structured errors through shared error helpers.
- Public APIs should return clear business errors.
- Internal API failures should preserve logs without exposing sensitive details to the frontend.
