# Testing Guide

Testing is organized into backend pytest, frontend lint/build, Docker Compose validation, and manual API flow checks.

中文版本: [README.md](README.md)

## Backend Tests

Run all backend tests:

```bash
./scripts/run-backend-tests.sh
```

Generate backend coverage:

```bash
./scripts/backend-coverage.sh
```

Single-service example:

```bash
cd services/identity-service
pytest tests -q
```

Important coverage areas:

- Registration, login, email verification, password reset.
- Admin and educator approval flows.
- Courses, modules, materials, and enrollment.
- Quiz authoring, attempts, and auto-submit.
- Forums, comments, notifications.
- AI chat, RAG, material indexing, profile updates, and quiz generation.

## Frontend Checks

```bash
cd frontend
npm ci
npm run lint
npm run build
```

The current frontend quality gate is lint/build. Page-level smoke tests and component tests can be added later.

## Docker and Integration Checks

Validate compose config:

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml config
```

Inspect services after startup:

```bash
docker compose --env-file .env -f infra/docker-compose.yml ps
```

Health checks:

```bash
curl http://127.0.0.1:${NGINX_PORT}/api/health
curl http://127.0.0.1:${NGINX_PORT}/api/learning/health
curl http://127.0.0.1:${NGINX_PORT}/api/communication/health
curl http://127.0.0.1:${NGINX_PORT}/api/ai/health
```

## Manual Validation Flow

Recommended full-system flow:

1. Register a learner and complete email verification.
2. Register an educator and activate the account through admin approval or invite link.
3. Create a course, modules, and upload materials as the educator.
4. Publish modules and the course.
5. Enroll as the learner, view materials, and update learning progress.
6. Create a quiz as the educator, attempt it as the learner, and inspect results.
7. Use AI chat inside the course.
8. Check material indexing jobs and RAG responses.
9. Create forum posts, comments, and notifications.
10. Inspect educator analytics.

## Regression Record Template

When fixing a bug, record:

- Problem description.
- Reproduction steps.
- Root cause.
- Changed files.
- Automated tests or manual verification results.
- Whether existing APIs or data are affected.
