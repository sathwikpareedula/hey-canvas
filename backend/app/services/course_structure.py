"""Deterministic local course-structure assembly."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Assignment, Course, CourseModule
from app.database.module_repository import ModuleRepository
from app.modules.models import (
    AssignmentReference,
    CourseModuleStructure,
    ModuleItemStructure,
)


class CourseStructureService:
    """Build ordered module trees and resolve optional local assignment references."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_modules(
        self,
        *,
        canvas_course_id: str | None = None,
    ) -> list[CourseModuleStructure]:
        modules = ModuleRepository(self._session).list_ordered(
            canvas_course_id=canvas_course_id
        )
        assignment_refs = self._assignment_references(modules)
        return [
            CourseModuleStructure(
                canvas_module_id=module.canvas_module_id,
                canvas_course_id=module.canvas_course_id,
                name=module.name,
                position=module.position,
                unlock_at=module.unlock_at,
                require_sequential_progress=module.require_sequential_progress,
                requirement_type=module.requirement_type,
                publish_final_grade=module.publish_final_grade,
                prerequisite_module_ids=module.prerequisite_module_ids,
                workflow_state=module.workflow_state,
                state=module.state,
                completed_at=module.completed_at,
                items_count=module.items_count,
                published=module.published,
                first_seen_at=module.first_seen_at,
                last_seen_at=module.last_seen_at,
                last_synced_at=module.last_synced_at,
                items=[
                    ModuleItemStructure(
                        canvas_module_item_id=item.canvas_module_item_id,
                        canvas_module_id=module.canvas_module_id,
                        canvas_course_id=module.canvas_course_id,
                        title=item.title,
                        position=item.position,
                        item_type=item.item_type,
                        content_id=item.content_id,
                        html_url=item.html_url,
                        api_url=item.api_url,
                        page_url=item.page_url,
                        external_url=item.external_url,
                        new_tab=item.new_tab,
                        completion_requirement=item.completion_requirement,
                        content_details=item.content_details,
                        indent=item.indent,
                        published=item.published,
                        assignment=assignment_refs.get(
                            (module.canvas_course_id, item.content_id)
                        )
                        if item.item_type == "Assignment" and item.content_id is not None
                        else None,
                        first_seen_at=item.first_seen_at,
                        last_seen_at=item.last_seen_at,
                        last_synced_at=item.last_synced_at,
                    )
                    for item in module.items
                ],
            )
            for module in modules
        ]

    def _assignment_references(
        self,
        modules: list[CourseModule],
    ) -> dict[tuple[str, str | None], AssignmentReference]:
        keys = {
            (module.course_id, item.content_id)
            for module in modules
            for item in module.items
            if item.item_type == "Assignment" and item.content_id is not None
        }
        if not keys:
            return {}
        course_ids = {course_id for course_id, _ in keys}
        assignment_ids = {content_id for _, content_id in keys if content_id is not None}
        statement = (
            select(Assignment, Course.canvas_course_id)
            .join(Course)
            .where(
                Assignment.course_id.in_(course_ids),
                Assignment.canvas_assignment_id.in_(assignment_ids),
            )
        )
        return {
            (canvas_course_id, assignment.canvas_assignment_id): AssignmentReference(
                canvas_assignment_id=assignment.canvas_assignment_id,
                name=assignment.name,
                due_at=assignment.due_at,
            )
            for assignment, canvas_course_id in self._session.execute(statement).all()
        }
