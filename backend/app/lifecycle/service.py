"""Non-destructive-by-default lifecycle operations."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import (
    AcademicDocument,
    AcademicWorkspace,
    CanvasFile,
    CourseMaterialReference,
    PracticeSessionRecord,
    StudySessionRecord,
)
from app.lifecycle.models import LifecycleResult, LifecycleScope


class LifecycleService:
    def __init__(self, session: Session, *, user_key: str = "local-user") -> None:
        self._session = session
        self._user_key = user_key

    def clear(self, scope: LifecycleScope) -> LifecycleResult:
        if scope.workspace_key is None and scope.course_id is None:
            raise ValueError("an explicit workspace_key or course_id is required")
        workspace_deleted = False
        if scope.workspace_key is not None:
            workspace = self._session.scalar(
                select(AcademicWorkspace).where(
                    AcademicWorkspace.user_key == self._user_key,
                    AcademicWorkspace.workspace_key == scope.workspace_key,
                )
            )
            if workspace is not None:
                self._session.delete(workspace)
                workspace_deleted = True
        study_deleted = practice_deleted = 0
        if scope.include_study_state and scope.course_id is not None:
            study_ids = tuple(
                self._session.scalars(
                    select(StudySessionRecord.id).where(
                        StudySessionRecord.course_id == scope.course_id
                    )
                )
            )
            practice_ids = tuple(
                self._session.scalars(
                    select(PracticeSessionRecord.id).where(
                        PracticeSessionRecord.course_id == scope.course_id
                    )
                )
            )
            study_deleted = len(study_ids)
            practice_deleted = len(practice_ids)
            if study_ids:
                self._session.execute(
                    delete(StudySessionRecord).where(StudySessionRecord.id.in_(study_ids))
                )
            if practice_ids:
                self._session.execute(
                    delete(PracticeSessionRecord).where(
                        PracticeSessionRecord.id.in_(practice_ids)
                    )
                )
        # File records are globally keyed in the current schema and do not yet carry
        # a course FK; never clear unrelated courses as a lifecycle side effect.
        materials = 0
        if scope.include_materials and scope.course_id is not None:
            references = tuple(
                self._session.scalars(
                    select(CourseMaterialReference).where(
                        CourseMaterialReference.course_id == scope.course_id
                    )
                )
            )
            file_ids = tuple(item.canvas_file_id for item in references)
            if references:
                self._session.execute(
                    delete(CourseMaterialReference).where(
                        CourseMaterialReference.course_id == scope.course_id
                    )
                )
            remaining_ids = {
                item.canvas_file_id
                for item in self._session.scalars(
                    select(CourseMaterialReference).where(
                        CourseMaterialReference.canvas_file_id.in_(file_ids)
                    )
                )
            }
            removable_ids = tuple(item for item in file_ids if item not in remaining_ids)
            for file_id in removable_ids:
                file = self._session.scalar(
                    select(CanvasFile).where(CanvasFile.canvas_file_id == file_id)
                )
                if file is None:
                    continue
                _remove_derivative(file.local_relative_path)
                self._session.execute(
                    delete(AcademicDocument).where(
                        AcademicDocument.canvas_file_id == file_id
                    )
                )
                self._session.delete(file)
                materials += 1
        self._session.commit()
        return LifecycleResult(
            workspace_deleted=workspace_deleted,
            study_sessions_deleted=study_deleted,
            practice_sessions_deleted=practice_deleted,
            materials_marked_for_removal=materials,
        )


def _remove_derivative(relative_path: str | None) -> None:
    if not relative_path:
        return
    root = get_settings().academic_files_root.resolve()
    candidate = (root / relative_path).resolve()
    if candidate == root or root not in candidate.parents:
        raise ValueError("stored material path is outside the configured files root")
    if candidate.is_file():
        candidate.unlink()
