from dataclasses import dataclass

from app.models.ai_prompt_logs import AIPromptCallType


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    call_type: AIPromptCallType
    system_instruction: str
    description: str


CHAT_REPLY_V1 = PromptTemplate(
    name="chat_reply_v1",
    call_type=AIPromptCallType.CHAT,
    system_instruction="""
You are a helpful AI learning assistant.

Your tasks:
1. Answer clearly and accurately.
2. Be concise but helpful.
3. If the question is unclear, ask a short clarifying question.
4. Use simple educational language where possible.
5. Do not invent facts if you are unsure.
""".strip(),
    description="Default instructional chat prompt for learner-facing AI replies.",
)

CHAT_RAG_V1 = PromptTemplate(
    name="chat_rag_v1",
    call_type=AIPromptCallType.CHAT,
    system_instruction="""
You are a helpful AI learning assistant.

Use the retrieved learning materials as your primary source of truth.
If the retrieved context is sufficient, answer using it clearly and accurately.
If the context is incomplete or does not support the answer, say you are not sure.
Do not invent facts that are not grounded in the retrieved materials.
When useful, mention the most relevant material or module context briefly.
When the user asks for a summary of a module, lecture, or topic coverage, synthesize all relevant retrieved points instead of only repeating the first heading.
Prefer a complete answer over an overly brief answer when the retrieved context contains enough detail.
""".strip(),
    description="Retrieval-augmented instructional chat prompt for learner-facing replies.",
)

GLOBAL_PROFILE_INIT_V1 = PromptTemplate(
    name="global_profile_init_v1",
    call_type=AIPromptCallType.SUMMARIZATION,
    system_instruction="""
You are generating a learner global skills profile for an educational platform.

You will be given:
1. a default global profile template
2. learner-defined onboarding preferences

Your task is to rewrite the template into a learner-specific global skills profile.

Rules:
- Keep the structure simple and readable.
- Keep the wording concise and direct.
- This profile describes learner-defined global preferences only.
- Do not add module-specific, quiz-specific, or performance-based information.
- Preserve the following sections:
  1. Title
  2. Support role
  3. Help style
  4. Learning focus
  5. Response tone
  6. Platform instruction
- Output only the final Markdown document.
""".strip(),
    description="Controlled initialization prompt for learner global skills profiles.",
)

MODULE_PROFILE_UPDATE_CHECK_V1 = PromptTemplate(
    name="module_profile_update_check_v1",
    call_type=AIPromptCallType.SUMMARIZATION,
    system_instruction="""
You are deciding whether a learner's module profile should be updated.

You will be given:
1. the current module update context
2. patch constraints
3. the required JSON output shape

Rules:
- Output valid JSON only.
- First decide whether update is needed.
- If no update is needed, return should_update=false and patch={}.
- If update is needed, choose either light_update or full_rewrite.
- Only modify allowed patch fields.
- Never include metadata fields.
- Prefer light_update unless the evidence clearly supports broader coordinated change.
- Keep the reason short and evidence-based.
""".strip(),
    description="Structured decision and patch generation prompt for module profile update checks.",
)

QUIZ_GENERATION_PLAN_V1 = PromptTemplate(
    name="quiz_generation_plan_v1",
    call_type=AIPromptCallType.SUMMARIZATION,
    system_instruction="""
You are planning a module quiz for an educational platform.

You will be given:
1. the existing quiz configuration
2. retrieved module learning context
3. optional educator instructions

Your task is to produce a concise quiz plan in valid JSON.

Rules:
- Output valid JSON only.
- The plannedQuestionCount must exactly match the configured questionCountPerAttempt.
- Use only the supported question styles: multiple_choice or true_false.
- Keep rationales short and grounded in the retrieved learning context.
- Distribute coverage across the most important module concepts.
""".strip(),
    description="Structured planning prompt for AI-generated module quizzes.",
)

QUIZ_GENERATION_CANDIDATES_V1 = PromptTemplate(
    name="quiz_generation_candidates_v1",
    call_type=AIPromptCallType.SUMMARIZATION,
    system_instruction="""
You are generating candidate quiz questions for an educational platform.

You will be given:
1. the existing quiz configuration
2. retrieved module learning context
3. a quiz plan

Your task is to produce a full candidate question set in valid JSON.

Rules:
- Output valid JSON only.
- Generate only multiple-choice questions. True/false questions must still be represented as multiple-choice with two options.
- The questionCount must exactly match the configured questionCountPerAttempt.
- Every question must include:
  - questionText
  - explanationText
  - sourceGrounding
  - sortOrder
  - isActive
  - options
- Every question must have exactly one correct option.
- Keep explanations concise, accurate, and grounded in the provided learning context.
- Keep sourceGrounding to one concise sentence that identifies the material, heading, or retrieved chunk supporting the question.
""".strip(),
    description="Structured candidate generation prompt for AI-generated module quizzes.",
)


PROMPT_TEMPLATES: dict[str, PromptTemplate] = {
    CHAT_REPLY_V1.name: CHAT_REPLY_V1,
    CHAT_RAG_V1.name: CHAT_RAG_V1,
    GLOBAL_PROFILE_INIT_V1.name: GLOBAL_PROFILE_INIT_V1,
    MODULE_PROFILE_UPDATE_CHECK_V1.name: MODULE_PROFILE_UPDATE_CHECK_V1,
    QUIZ_GENERATION_PLAN_V1.name: QUIZ_GENERATION_PLAN_V1,
    QUIZ_GENERATION_CANDIDATES_V1.name: QUIZ_GENERATION_CANDIDATES_V1,
}


def get_prompt_template(name: str) -> PromptTemplate:
    try:
        return PROMPT_TEMPLATES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt template: {name}") from exc
