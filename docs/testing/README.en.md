# Testing Guide

Testing is organized into backend pytest, frontend lint/build, Docker Compose validation, GitHub Actions CI, and manual API flow checks.

中文版本: [README.md](README.md)

## GitHub CI/CD Gate

`.github/workflows/ci.yml` is the current quality gate. It runs on pushes to `main`, `feature/**`, `fix/**`, and `refactor/**`, and on pull requests targeting `main`.

CI always runs:

- Frontend `npm ci`, `npm run lint`, and `npm run build`.
- `packages/platform_common/tests`.
- Docker Compose config validation.
- Full Docker Compose startup plus nginx gateway smoke tests.
- Full `pytest tests -q` for all backend services: identity, communication, learning, and ai.

CI uses safe placeholder configuration and does not require real Gemini, SMTP, or production secrets:

```bash
./scripts/create-ci-env.sh .env.ci
docker compose --env-file .env.ci -f infra/docker-compose.yml config --quiet
```

## New Feature Test Convention

Every new feature should add tests with the feature change:

- Put backend tests in the relevant service `tests/` directory; CI collects them automatically.
- AI feature tests must mock providers and must not depend on real external API keys.
- Permission, error-handling, and cross-service flows should cover success and failure paths.
- Frontend changes must at least pass lint/build; once Vitest or Playwright is introduced, put the test command in `frontend/package.json` and wire it into CI.

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

Validate with the CI environment:

```bash
./scripts/create-ci-env.sh .env.ci
docker compose --env-file .env.ci -f infra/docker-compose.yml config --quiet
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
