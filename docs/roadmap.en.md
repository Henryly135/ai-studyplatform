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

## Phase 1: Testing and CI

Goal: create a maintainable quality baseline.

Tasks:

- Add backend tests for auth, courses, modules, materials, quizzes, forums, notifications, and AI workflows.
- Add frontend lint/build/smoke checks for critical pages.
- Extend GitHub Actions to cover frontend build, backend pytest, Docker Compose config, and basic health checks.
- Document local and CI testing commands.

Acceptance:

- CI runs for PRs and main.
- Backend service tests can be run independently.
- Docs explain how to inspect failed tests and service logs.

## Phase 2: Educator AI Quiz Generation

Goal: educators can generate editable quiz drafts from module materials or prompts.

Implementation direction:

- Reuse the existing quiz generation workflow in `ai-service` and add educator generation runs.
- Support difficulty, question types, question count, learning objectives, material scope, and educator instructions.
- Persist generated results into `learning-service` quiz drafts instead of publishing directly.
- Add generate, preview, edit, accept, discard, and regenerate flows to the course-management quiz page.

Acceptance:

- Educators can generate quiz drafts.
- Questions include options, answers, explanations, and source grounding.
- Questions cannot be published to learners without educator confirmation.

## Phase 3: Short-Answer Assessment

Goal: add one assessment mode beyond multiple-choice quizzes.

Implementation direction:

- Add data structures for short-answer definitions, rubrics, learner submissions, AI feedback, and educator review.
- After learners submit text answers, AI suggests scores and feedback using the rubric and material context.
- Educators can inspect submissions, adjust feedback, and confirm final results.
- Feed short-answer data into analytics later.

Acceptance:

- Educators can publish short-answer tasks.
- Learners can submit answers.
- Educators can review AI suggestions.

## Phase 4: Educator Analytics

Goal: turn the dashboard into a teaching decision tool.

Implementation direction:

- Add course, module, quiz, short-answer, engagement, and learner-profile dimensions.
- Show module bottlenecks, weak questions, at-risk learners, completion trends, and mastery signals.
- Support filters for course, module, time range, and learner status.
- Preserve educator/admin permission boundaries.

Acceptance:

- Educators can identify learners needing help and high-risk modules.
- Dashboard data matches backend aggregates.

## Phase 5: Educator AI Content Generation

Goal: help educators create teaching-material drafts faster.

Implementation direction:

- Support summaries, learning objectives, activity suggestions, level-adapted explanations, and slide outlines.
- Include structured fields and material grounding.
- Provide fallback and manual editing when AI confidence is low.

Acceptance:

- Educators can generate content drafts from materials.
- Generated outputs can be edited and saved.

## Phase 6: Student Study Planner

Goal: students can upload personal materials and receive personalised study plans.

Implementation direction:

- Add a standalone Study Planner page.
- Support material uploads, goals, needs, preferences, and available study time.
- Generate a study workflow, staged plan, topic order, and rationale.
- Later integrate with chat, recommendations, and learner profiles.

Acceptance:

- Students can generate a readable and adjustable study plan.
- The plan references student inputs and uploaded materials.

## Long-Term Direction

- Stronger AI source citation and structured-output validation.
- More assessment forms such as concept maps, peer review, and mini projects.
- More granular profile updates and recommendation explanations.
- Production deployment monitoring, log analysis, and recovery automation.
