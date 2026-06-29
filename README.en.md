# AI Study Platform

AI Study Platform is a full-stack AI learning platform for course-based study workflows. It uses a React frontend and FastAPI microservices to support courses, modules, learning materials, quizzes, forums, notifications, AI chat, RAG retrieval, learner profiles, and personalised learning support.

This repository has been cleaned and reorganised as a personal project. Chinese documentation is the primary interview-facing entry point, while English documentation is kept as a corresponding technical version.

中文版本: [README.md](README.md)

## Highlights

- Microservice backend with separate identity, learning, communication, and AI services.
- AI features powered by Gemini, LangChain, and pgvector: RAG chat, material indexing, quiz generation, and learner profile updates.
- Learning platform core flows: authentication, email verification, RBAC, course management, modules, materials, progress, quizzes, forums, and notifications.
- Async processing with Redis and Celery for indexing, notifications, quiz sessions, and AI workflows.
- Reproducible local stack using Docker Compose with MySQL, PostgreSQL, Redis, MinIO, nginx, frontend, and backend services.
- Bilingual documentation: Chinese for interviews and English for technical review.

## Tech Stack

| Layer | Technologies |
| --- | --- |
| Frontend | React, Vite, TypeScript, Bootstrap |
| Backend | FastAPI, SQLAlchemy, Pydantic |
| AI | Gemini API, DeepSeek/OpenAI-compatible API, LangChain, LangGraph, pgvector |
| Databases | MySQL, PostgreSQL |
| Async tasks | Redis, Celery |
| File storage | MinIO |
| Gateway and deployment | nginx, Docker Compose, GitHub Actions |

## Quick Start

### 1. Prerequisites

Install:

- Docker Desktop
- Docker Compose v2
- Node.js 20+ if running the frontend outside Docker
- Python 3.11+ if running backend services outside Docker

Check:

```bash
docker --version
docker compose version
node --version
python --version
```

### 2. Create `.env`

```bash
cp .env.example .env
```

On Windows:

```bash
copy .env.example .env
```

Do not commit `.env`. Real secrets, SMTP passwords, Gemini API keys, DeepSeek/OpenAI-compatible API keys, and database passwords must stay in `.env` or deployment secrets.

The local demo admin account is included in `.env.example` so interviewers can try the admin console quickly:

```text
Email: admin@example.com
Password: DemoAdmin123!
```

This account is only for local admin login. Registration, email verification, password reset, and educator invite flows should be tested with real recipient email addresses through SMTP.

### 3. Update Required Values

Fields marked with `# Have to Change` must be replaced, for example:

```env
SMTP_USER=your_ses_smtp_username
SMTP_PASS=your_ses_smtp_password
SMTP_FROM=your_email@example.com
GEMINI_API_KEY=your_gemini_api_key
```

AI chat providers can be switched between Gemini and DeepSeek/OpenAI-compatible services through the unified adapter:

```env
AI_CHAT_PROVIDER=deepseek
AI_CHAT_BASE_URL=https://api.deepseek.com
AI_CHAT_MODEL=deepseek-chat
AI_CHAT_API_KEY=your_local_deepseek_key
DEEPSEEK_API_KEY=your_local_deepseek_key
```

Gemini remains the default provider and still supports `GEMINI_API_KEY`. DeepSeek/OpenRouter and other OpenAI-compatible chat providers use `AI_CHAT_PROVIDER`, `AI_CHAT_BASE_URL`, `AI_CHAT_MODEL`, and `AI_CHAT_API_KEY`; embeddings still use the separate Gemini embedding configuration, so changing embedding providers requires adding an embedding adapter and reindexing materials. CI uses empty keys or mocks and does not require real AI provider keys.

For public deployment, also change the default admin email, password, and name.

If local ports conflict, adjust external ports such as `MYSQL_PORT`, `AI_DB_EXTERNAL_PORT`, `FRONTEND_PORT`, and `NGINX_PORT`.

### 4. Start the Stack

Run from the repository root:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down -v --remove-orphans
docker compose --env-file .env -f infra/docker-compose.yml up -d --build
docker compose --env-file .env -f infra/docker-compose.yml ps
```

Default app URL:

```text
http://localhost:8080
```

Health checks:

```bash
curl http://127.0.0.1:${NGINX_PORT}/api/health
curl http://127.0.0.1:${NGINX_PORT}/api/learning/health
curl http://127.0.0.1:${NGINX_PORT}/api/communication/health
curl http://127.0.0.1:${NGINX_PORT}/api/ai/health
```

## Project Structure

```text
.
├─ frontend/                       # React + Vite frontend
├─ services/
│  ├─ identity-service/            # Auth, users, roles, permissions
│  ├─ learning-service/            # Courses, modules, materials, quizzes, progress
│  ├─ communication-service/       # Forums, comments, notifications
│  └─ ai-service/                  # AI chat, RAG, indexing, learner profiles
├─ packages/platform_common/       # Shared backend utilities
├─ database/                       # Schemas, migrations, initialization, seed data
├─ infra/                          # Docker Compose and nginx
├─ scripts/                        # Test, deployment, and operations helpers
├─ docs/                           # Bilingual project documentation
└─ .github/workflows/              # CI/CD workflows
```

## Documentation

- [Documentation Index](docs/README.en.md)
- [Project Requirements](docs/project-requirements.en.md)
- [Roadmap](docs/roadmap.en.md)
- [Architecture](docs/architecture/README.en.md)
- [API Overview](docs/api/README.en.md)
- [Deployment and Configuration](docs/deployment/README.en.md)
- [Testing Guide](docs/testing/README.en.md)

## Interview Walkthrough

A clear interview walkthrough can use this order:

1. **Positioning**: AI Study Platform is an AI-powered personalised learning platform for learners, educators, and admins.
2. **Business loop**: educators create courses and modules, upload materials, and publish content; learners enroll, study materials, complete quizzes, and interact through forums; notifications and progress records connect the workflow.
3. **AI capability**: materials are indexed into PostgreSQL + pgvector; chat and quiz generation retrieve course context through RAG, then Gemini/LangChain generates grounded responses.
4. **Microservice architecture**: identity, learning, communication, and AI services are exposed through nginx and backed by MySQL, PostgreSQL, Redis, MinIO, and Celery.
5. **Quality and deployment**: Docker Compose reproduces the full runtime; GitHub Actions cover frontend build, backend tests, and infrastructure checks.
6. **Next development**: build the AI Provider Adapter and Student Study Planner first, then expand educator AI quiz drafts, short-answer assessment, and educator analytics.

Technical points worth highlighting:

- RAG indexing flow: file parsing, chunking, embedding, vector retrieval, and prompt grounding.
- Learner profile updates: extracting learning signals from quizzes and chat for feedback and recommendations.
- Permissions and gateway: JWT + RBAC + nginx route isolation for public and internal APIs.
- Async processing: Celery handles material indexing, notifications, AI workflows, and quiz sessions.

## Common Commands

Backend tests:

```bash
./scripts/run-backend-tests.sh
```

Backend coverage:

```bash
./scripts/backend-coverage.sh
```

Frontend:

```bash
cd frontend
npm ci
npm run lint
npm run build
```

Docker config validation:

```bash
docker compose --env-file .env.example -f infra/docker-compose.yml config
```

## Next Development Areas

- Educator-side AI quiz draft generation with human review.
- AI Provider Adapter for OpenAI-compatible providers beyond Gemini.
- Short-answer assessment beyond multiple-choice quizzes.
- Educator analytics dashboard.
- Student personalised Study Planner.
- Stronger AI grounding, source citation, and structured-output validation.

See [docs/roadmap.en.md](docs/roadmap.en.md) for details.
