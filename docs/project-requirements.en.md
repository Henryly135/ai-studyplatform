# Project Requirements

## Goal

AI Study Platform aims to be an extensible personalised learning platform. Students can receive AI-assisted study support around course materials, while educators can manage courses, inspect learning progress, and gradually use AI for quiz generation, content generation, and teaching analytics.

The current codebase already includes the base platform. Future personal-project development will focus on AI teaching workflows, learning analytics, additional assessment modes, and student-side personalised study planning.

中文版本: [project-requirements.md](project-requirements.md)

## Current Platform Scope

- Registration, login, email verification, and password reset.
- Role-based access for admins, educators, and learners.
- Courses, modules, learning materials, course publishing, and enrollment.
- Learning progress, module unlocking, quiz authoring, and quiz attempts.
- Forums, comments, and in-app notifications.
- AI chat, course-material RAG retrieval, material indexing, learner profile initialization, and learner profile updates.
- Local Docker Compose runtime.

## Future Feature Requirements

### 1. Platform Validation and Stabilisation

Core flows for authentication, courses, modules, materials, quizzes, AI chat, dashboards, and learning paths should be validated so the project can start and demo reliably from a clean environment.

Priority issues:

- Reliability of educator email verification.
- Student-side file type display and document preview inside courses.
- AI chat access should not be limited only to the enrolled-course list.

### 2. Educator AI Quiz Generation

Educators should be able to generate quiz drafts from uploaded materials, a topic, or contextual instructions. Generation parameters should include:

- Difficulty.
- Question types.
- Number of questions.
- Learning objectives.
- Selected module or material scope.
- Additional educator instructions.

AI-generated questions must be saved as drafts and reviewed by an educator before publication.

### 3. Additional Assessment Mode

At least one assessment format beyond multiple-choice quizzes should be added. The recommended MVP is short-answer assessment:

- Educators create prompts and rubrics.
- Learners submit short text answers.
- AI suggests scores and feedback based on the rubric and course materials.
- Educators can review and override AI suggestions.

### 4. Educator Learning Analytics

The educator dashboard should provide actionable insight, not only simple aggregate counts. Analytics should include:

- Class-level progress.
- Module completion and bottlenecks.
- Learner engagement and recency.
- Quiz scores, retry counts, and weak questions.
- Future short-answer rubric performance.
- Learner-profile and recommendation signals.

### 5. Educator AI Content Generation

Educators should be able to generate or refine teaching materials with AI, such as:

- Summaries.
- Learning objectives.
- Activity suggestions.
- Level-adapted explanations.
- Slide outlines.
- Illustration prompts.

Outputs should include source grounding, structured fields, and clear fallback behavior.

### 6. AI Module Expansion and Safety

Existing RAG, chat, profile update, and quiz generation capabilities should be expanded for educator workflows and strengthened with:

- Source grounding.
- Hallucination mitigation.
- Content filtering.
- Structured-output validation.
- Fallback behavior when confidence or source support is insufficient.

### 7. Profile-Based Recommendations and Feedback

The system should use learner profiles, course progress, module completion, quiz results, and learning behavior to recommend next study steps.

Recommendations should explain the rationale, including weak areas, completed content, goals, and preferences.

### 8. Student Personalised Study Planner

Students should be able to upload their own learning materials, enter goals, needs, and preferences, and receive an AI-generated personalised study direction.

Inputs include:

- Personal learning materials such as notes, PDFs, documents, links, or other resources.
- Learning goals such as exam preparation, topic understanding, or project completion.
- Learning needs such as weak areas, deadlines, target skills, or desired depth.
- Learning preferences such as pace, language, explanation style, available time, and difficulty.

Outputs include:

- A personalised study workflow.
- A staged study plan.
- Recommended learning order.
- Recommendation rationale and editable suggestions.

The recommended MVP is a standalone Study Planner page, with chat integration as a later extension.
