"""Deterministic study-guide assembly from local truth and attributable evidence."""

from app.assistant_tools.models import AssistantEvidenceReference, SourceAuthority
from app.study_guides.models import StudyGuide, StudyGuideRequest


class StudyGuideService:
    def build(
        self,
        request: StudyGuideRequest,
        *,
        course_name: str | None = None,
        assignment_name: str | None = None,
        evidence: tuple[AssistantEvidenceReference, ...] = (),
    ) -> StudyGuide:
        scope = request.topic or assignment_name or "course material"
        uncertainties = (
            ("No professor material evidence was available; verify requirements in Canvas.",)
            if not evidence
            else ()
        )
        return StudyGuide(
            title=f"{course_name or request.course_id}: {scope} study guide",
            scope=scope,
            key_concepts=(scope,),
            explanations=(
                f"Review the central ideas in {scope} using the attributable material below.",
            ),
            evidence=tuple(
                item
                for item in evidence
                if item.authority is SourceAuthority.PROFESSOR_MATERIAL
            ),
            review_checklist=(
                "Define the main concept.",
                "Explain one relationship or process.",
                "Apply the idea to an example.",
            ),
            practice_prompts=(
                f"Explain {scope} in your own words.",
                f"Give an example that demonstrates {scope}.",
            ),
            uncertainties=uncertainties,
        )
