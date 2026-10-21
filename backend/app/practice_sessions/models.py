"""Evidence-grounded practice-session contracts."""

from typing import Protocol
from uuid import uuid4

from app.assistant_tools.models import AssistantEvidenceReference, AssistantStudyMode
from pydantic import BaseModel, ConfigDict, Field


class PracticeQuestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    question_id: str = Field(
        default_factory=lambda: f"q-{uuid4().hex}",
        min_length=1,
        max_length=255,
    )
    question: str = Field(min_length=1, max_length=2000)
    generated: bool = True
    evidence: tuple[AssistantEvidenceReference, ...] = Field(default=(), max_length=20)


class PracticeSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str = Field(min_length=1, max_length=255)
    topic: str = Field(min_length=1, max_length=500)
    total_questions: int = Field(default=5, ge=1, le=20)
    study_mode: AssistantStudyMode = AssistantStudyMode.PRACTICE


class PracticeSessionView(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str
    course_id: str
    topic: str
    status: str
    question_index: int
    total_questions: int
    correct_answers: int
    question: PracticeQuestion | None
    progress: int = Field(ge=0, le=100)


class PracticeAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=4000)
    question_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Identity of the question being answered for retry protection.",
    )


class PracticeFeedback(BaseModel):
    model_config = ConfigDict(frozen=True)

    correct: bool
    feedback: str = Field(min_length=1, max_length=4000)
    hint: str | None = Field(default=None, max_length=2000)
    next_question: PracticeQuestion | None = None
    progress: int = Field(ge=0, le=100)


class PracticeHint(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: str = Field(min_length=1, max_length=255)
    hint: str = Field(min_length=1, max_length=2000)
    question: PracticeQuestion | None = None
    progress: int = Field(ge=0, le=100)


class PracticeGenerator(Protocol):
    def question(
        self, *, topic: str, evidence: tuple[AssistantEvidenceReference, ...]
    ) -> PracticeQuestion:
        ...

    def feedback(self, *, question: str, answer: str) -> PracticeFeedback:
        ...


class DeterministicPracticeGenerator:
    """Offline generator used until an injected model provider supplies content."""

    def question(
        self, *, topic: str, evidence: tuple[AssistantEvidenceReference, ...]
    ) -> PracticeQuestion:
        return PracticeQuestion(
            question=f"Explain one important idea about {topic} and how you would apply it.",
            generated=True,
            evidence=evidence,
        )

    def feedback(self, *, question: str, answer: str) -> PracticeFeedback:
        correct = len(answer.strip()) >= 20
        return PracticeFeedback(
            correct=correct,
            feedback=(
                "Your answer gives a substantive explanation."
                if correct
                else "Add a definition, a supporting detail, and an example."
            ),
            hint=None if correct else "Start by defining the central concept.",
            progress=0,
        )
