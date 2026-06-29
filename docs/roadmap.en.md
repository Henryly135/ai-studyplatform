# Development Roadmap

This roadmap is designed for continued personal-project development and interview explanation. It focuses on incremental features that can be implemented, demonstrated, and tested.

中文版本: [roadmap.md](roadmap.md)

## Phase 0: Baseline Stabilisation

Goal: make the project reliable from a clean environment.

Tasks:

- Create `.env` from `.env.example` and start the full Docker Compose stack.
- Verify nginx, frontend, four backend services, MySQL, PostgreSQL, Redis, and MinIO.
- Validate registration, login, email verification, password reset, course creation, module publishing, material upload, quiz attempts, forums, notifications, AI chat, and RAG.
- Fix known issues: educator email verification, student document preview, and AI chat entry restrictions.
- Record bugs, reproduction steps, fixes, and regression results.

Acceptance:

- A clean checkout can start by following README.
- All health checks pass.
- Fixes have tests or clear regression notes.

## Phase 1: GitHub CI/CD Test Gate

Goal: make GitHub run the complete test suite before new feature development continues.

Tasks:

- Use `.github/workflows/ci.yml` as the main quality gate.
- Cover frontend lint/build, `platform_common` tests, Docker Compose config, full backend pytest, and nginx gateway smoke tests.
- Generate a safe CI `.env` through `scripts/create-ci-env.sh`, without real Gemini, SMTP, or production secrets.
- Establish the new-feature testing convention: backend tests live in each service `tests/` directory, AI tests use mocked providers, and future frontend test commands are wired through `frontend/package.json`.

Acceptance:

- Pushes and pull requests trigger CI automatically.
- All four backend services run full `pytest tests -q`.
- Future test files are collected automatically by GitHub Actions.
- Docs explain local and CI testing entry points.

## Phase 2: AI Provider Adapter and Multi-Model Support

Goal: turn the current Gemini-specific implementation into a configurable AI provider layer that can later support OpenAI, DeepSeek, Claude, OpenRouter, and other model providers.

Implementation direction:

- Introduce provider interfaces in `ai-service` for chat, embeddings, structured generation, and error handling, while keeping Gemini as the default implementation.
- Add provider configuration such as `AI_CHAT_PROVIDER`, `AI_EMBEDDING_PROVIDER`, model names, base URLs, and provider-specific API keys; keep backward compatibility with `GEMINI_API_KEY`.
- The chat provider adapter now uses `AI_CHAT_*`, `DEEPSEEK_API_KEY`, and `GEMINI_API_KEY` compatibility paths; embedding providers remain separately configured and require a dedicated adapter plus material reindexing before switching.
- Prioritise OpenAI-compatible APIs first so DeepSeek, OpenRouter, and similar services can be integrated through one adapter; add Claude or other dedicated SDKs later if needed.
- Standardise token usage, quota/rate-limit handling, timeout handling, retries, logs, and prompt records.
- Add embedding dimension checks, index-version metadata, and reindexing guidance when switching embedding providers, so old and new embeddings are not mixed accidentally.
- Add provider mock tests for chat, RAG, quiz generation, learner profile updates, and material indexing.

Acceptance:

- `.env` can switch between Gemini and at least one OpenAI-compatible provider.
- AI chat, RAG, quiz generation, and material embeddings work with the new provider.
- Provider errors return consistent and explainable error responses.
- Documentation explains provider setup, limitations, and reindexing requirements.

## Phase 3: Educator AI Quiz Generation (Implemented)

Goal: educators can generate editable quiz drafts from module materials or prompts.

Current completed scope:

- Reuse the existing quiz generation workflow in `ai-service` and add an internal educator generation endpoint.
- Support difficulty, question types, question count, learning objectives, material scope, and educator instructions.
- Return generated results as a preview first; persist them to `learning-service` only after educator acceptance as an unpublished/draft quiz.
- Support replacing or appending to the existing question pool while preserving the existing quiz authoring/publish flow.
- Store per-question `sourceGrounding`, visible and adjustable in the frontend preview.
- Add question type controls plus generate preview, accept, discard, and regenerate flows to the course-management quiz page.

Acceptance:

- Educators can generate quiz drafts.
- Questions include options, answers, explanations, and source grounding.
- Questions cannot be published to learners without educator confirmation.

Future enhancements:

- Support richer question types and rubrics.
- Add short-lived server-side draft preview storage so unaccepted previews can be restored across devices.
- Link source grounding to finer-grained material citations.

## Phase 4: Short-Answer Assessment (Implemented)

Goal: add one assessment mode beyond multiple-choice quizzes.

Current completed scope:

- Add module-level short-answer definitions, rubrics, learner submissions, AI suggested feedback, and educator review data structures.
- Educators can create/update short-answer assessments from module management and set draft/published/archived status.
- Learners can read published short-answer tasks, submit answers, and view AI suggested feedback.
- `ai-service` exposes an internal short-answer evaluation endpoint returning suggested score, feedback, strengths, and improvements; the current implementation is a mock-friendly local evaluator.
- Educators can inspect submissions and override final score and feedback; final learner-visible feedback is published through educator review.

Acceptance:

- Educators can publish short-answer tasks.
- Learners can submit answers.
- Educators can review AI suggestions.

Future enhancements:

- Add retrieval-grounded citations from real module materials.
- Feed short-answer data into analytics and learner profiles.
- Support multi-question short-answer assignments, rubric-dimension scoring, and batch review.

## Phase 5: Educator Analytics (Implemented)

Goal: turn the dashboard into a teaching decision tool.

Current completed scope:

- Existing educator endpoints provide course enrollment aggregates and quiz module statistics.
- Added a `teaching-insights` aggregate endpoint scoped to courses owned by the current educator, covering module bottlenecks, at-risk learners, completion trends, and assessment signals.
- Module bottlenecks are derived from enrollment count, started/completed count, completion rate, and average progress, with low-completion and no-activity signals.
- At-risk learners are flagged from low progress, stale access, and many incomplete modules.
- Assessment signals combine low quiz pass rate/average score with short-answer AI/final average score and pending review counts.
- The frontend Analytics page now shows course overview, quiz performance, at-risk learners, module bottlenecks, assessment signals, and completion trends.
- Aggregation uses existing `learning-service` enrollment, module progress, quiz attempt, and short-answer submission tables, without calling AI.

Acceptance:

- Educators can identify learners needing help and high-risk modules.
- Dashboard data matches backend aggregates.

Future enhancements:

- Add filters for course, module, time range, and learner status.
- Add finer-grained weak-question, rubric-dimension, and learner-profile mastery signals.
- Add trend charts, export, and proactive alerts.

## Phase 6: Educator AI Content Generation (Implemented)

Goal: help educators create teaching-material drafts faster.

Current completed scope:

- Educators can generate AI content drafts from the module detail page, covering summaries, learning objectives, activity suggestions, differentiated explanations, and slide outlines.
- `learning-service` persists draft title, educator prompt, material scope, structured content, source grounding, confidence, and provider/fallback metadata.
- `ai-service` exposes an internal content-generation endpoint that uses the current `AI_CHAT_*` provider adapter first; missing provider configuration, quota/timeout, invalid JSON, or low confidence falls back to a deterministic editable draft.
- Drafts remain educator-management records only. They are not automatically published to learners and do not automatically overwrite module body content.
- The frontend supports selecting saved drafts, editing structured content and source grounding, saving changes, and manually copying a draft into the module content editor.
- The implementation includes a database migration, backend mock-provider/fallback tests, and permission/save-path tests.

Acceptance:

- Educators can generate content drafts from materials.
- Generated outputs can be edited and saved.

Future enhancements:

- Add finer-grained material chunk citations rather than only material titles/summaries.
- Support version history, draft archiving, and a confirmed one-click apply flow into module body content.
- Add content-type-specific frontend editors instead of the generic structured text editor.

## Phase 7: Student Study Planner (Implemented)

Goal: students can enter goals, material summaries, preferences, and available time, then receive personalised study plans.

Current completed scope:

- Add a standalone Study Planner page.
- Support learning goals, target date, preferences, weekly availability, and material-summary input.
- `learning-service` persists plan metadata, original input, generated content, status, and adjustment notes.
- `ai-service` generates staged phases, topic order, review cadence, and rationale through an internal endpoint, with fallback when the provider fails.
- Learners can view, adjust, archive/restore, and regenerate their own plans.
- Coverage includes learner permissions, input validation, provider-mock success path, provider-failure fallback, plan save/read, and frontend lint/build.

Future enhancements:

- Support real material uploads and material content extraction instead of material summaries only.
- Integrate with AI chat, recommendations, and learner profiles.
- Add finer-grained source citation, learning-progress sync, and calendar views.

Acceptance:

- Students can generate a readable and adjustable study plan.
- The plan references student inputs and material summaries.

## Long-Term Direction

- Stronger AI source citation and structured-output validation.
- Pluggable AI providers, cost controls, and model-quality evaluation.
- More assessment forms such as concept maps, peer review, and mini projects.
- More granular profile updates and recommendation explanations.
- Production deployment monitoring, log analysis, and recovery automation.
