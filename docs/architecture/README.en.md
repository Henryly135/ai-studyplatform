# System Architecture

AI Study Platform uses a separated frontend/backend architecture with domain-oriented microservices. The frontend calls a unified nginx API gateway, and backend services are split across identity, learning, communication, and AI domains.

中文版本: [README.md](README.md)

## Overview

```text
Frontend -> nginx -> FastAPI services -> databases / queues / object storage / AI provider
```

Core services:

- `identity-service`: authentication, users, roles, permissions, and educator approval.
- `learning-service`: courses, modules, materials, learning progress, enrollment, quizzes, and analytics.
- `communication-service`: forums, comments, and in-app notifications.
- `ai-service`: AI chat, RAG, material indexing, learner profiles, and AI workflows.

## Data Layer

| Data | Technology | Notes |
| --- | --- | --- |
| Identity, courses, forums | MySQL | Structured business data |
| AI, RAG, profiles | PostgreSQL + pgvector | Vector retrieval, AI logs, profile assets |
| Async tasks | Redis | Celery broker/result backend |
| Quiz sessions | Redis | Quiz session state and locks |
| Learning materials | MinIO | S3-compatible file storage |

## Async Tasks

Celery workers keep expensive work outside the request path:

- Material indexing and embedding generation.
- Notification dispatch.
- Quiz session auto-submit.
- AI workflow background tasks.

## AI Workflows

AI capabilities are organized around three main flows:

- RAG: uploaded materials are indexed into chunks and embeddings, then retrieved by course/module scope for chat and quiz generation.
- Quiz Generation: load quiz context, retrieve materials, plan questions, generate candidates, validate structure, and persist results back to the learning service.
- Profile Update: extract learning signals from quizzes and chat, then update module profiles for recommendations and feedback.

Related diagrams:

- [RAG and Material Indexing Workflow](../diagrams/rag-workflow.en.md)
- [Learner Profile Update Workflow](../diagrams/profile-update-workflow.en.md)
- [AI Quiz Generation Workflow](../diagrams/quiz-generation-workflow.en.md)

## Backend Layering

Backend services follow this direction:

```text
api/controller -> service -> repository -> model
```

- `api/`: HTTP I/O, auth dependencies, parameter parsing.
- `services/`: business rules, repository coordination, transaction boundaries.
- `repositories/`: database queries and persistence.
- `models/`: SQLAlchemy table mappings and relationships.
- `schemas/`: Pydantic request/response models.
- `core/`: config, security, time helpers, Celery, shared dependencies.

## Interview Talking Points

- Why AI is a separate service: AI workflows, vector storage, task queues, and logs are decoupled from normal learning business logic.
- Why PostgreSQL + pgvector is used: course-material retrieval and RAG grounding need vector similarity search.
- Why Celery is used: embedding, file parsing, and notification work should not block API requests.
- Why nginx is used as a gateway: the frontend gets one API entry point while backend service paths can evolve independently.
