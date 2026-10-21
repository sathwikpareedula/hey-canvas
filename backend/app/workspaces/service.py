"""Workspace persistence and deterministic entity continuity."""

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AcademicWorkspace, Course
from app.workspaces.models import WorkspaceUpdate, WorkspaceView


class WorkspaceService:
    def __init__(self, session: Session, *, user_key: str = "local-user") -> None:
        if not user_key or len(user_key) > 100:
            raise ValueError("user_key is invalid")
        self._session = session
        self._user_key = user_key

    def list(self, *, course_id: str | None = None) -> tuple[WorkspaceView, ...]:
        query = select(AcademicWorkspace).where(AcademicWorkspace.user_key == self._user_key)
        if course_id is not None:
            query = query.where(AcademicWorkspace.course_id == course_id)
        records = self._session.scalars(query.order_by(AcademicWorkspace.workspace_key))
        return tuple(self._view(record) for record in records)

    def get_or_create(
        self,
        workspace_key: str,
        *,
        course_id: str | None = None,
        display_name: str | None = None,
    ) -> WorkspaceView:
        self._validate_key(workspace_key)
        record = self._session.scalar(
            select(AcademicWorkspace).where(
                AcademicWorkspace.user_key == self._user_key,
                AcademicWorkspace.workspace_key == workspace_key,
            )
        )
        if record is None:
            if course_id is not None and self._session.scalar(
                select(Course).where(Course.canvas_course_id == course_id)
            ) is None:
                raise LookupError("course was not found locally")
            record = AcademicWorkspace(
                user_key=self._user_key,
                workspace_key=workspace_key,
                course_id=course_id,
                display_name=display_name or workspace_key,
                recent_entities=[],
                recent_intent=None,
                updated_at=datetime.now(UTC),
            )
            self._session.add(record)
            self._session.commit()
        return self._view(record)

    def update(self, workspace_key: str, request: WorkspaceUpdate) -> WorkspaceView:
        record = self._session.scalar(
            select(AcademicWorkspace).where(
                AcademicWorkspace.user_key == self._user_key,
                AcademicWorkspace.workspace_key == workspace_key,
            )
        )
        if record is None:
            raise LookupError("workspace was not found")
        if request.display_name is not None:
            record.display_name = request.display_name
        if request.recent_entities is not None:
            record.recent_entities = [dict(item) for item in request.recent_entities]
        if request.recent_intent is not None:
            record.recent_intent = request.recent_intent
        record.updated_at = datetime.now(UTC)
        self._session.commit()
        return self._view(record)

    def resolve_assignment(
        self,
        workspace_key: str,
        query: str,
        *,
        course_id: str | None = None,
    ) -> str | None:
        """Resolve one recent assignment without crossing a course boundary."""
        if not query.strip():
            return None
        record = self._session.scalar(
            select(AcademicWorkspace).where(
                AcademicWorkspace.user_key == self._user_key,
                AcademicWorkspace.workspace_key == workspace_key,
            )
        )
        if record is None:
            return None
        normalized = " ".join(query.casefold().split())
        is_pronoun_ref = (
            normalized in {
                "it",
                "that assignment",
                "that one",
                "the first one",
                "this quiz",
                "this assignment",
                "that quiz",
            }
            or bool(
                re.search(
                    r"\b(?:this|that|the)\s+(?:quiz|assignment|homework|exam|project|lab)\b",
                    normalized,
                )
            )
            or bool(
                re.search(
                    r"\b(?:is\s+it\s+due|points?\s+is\s+it\s+worth|how\s+many\s+points|"
                    r"how\s+much\s+is\s+it\s+worth|due\s+date\s+for\s+it|about\s+it|"
                    r"study\s+for\s+it|prepare\s+for\s+it)\b",
                    normalized,
                )
            )
            or bool(re.search(r"\b(?:when|what|how)\b.*\b(?:it|this|that|those)\b", normalized))
        )
        candidates = [
            item.get("id")
            for item in (record.recent_entities or [])
            if item.get("kind") == "assignment"
            and (course_id is None or item.get("course_id") == course_id)
        ]
        if candidates and is_pronoun_ref:
            return candidates[0]
        matches = [
            cid
            for cid in candidates
            if any(
                normalized in " ".join(item.get("label", "").casefold().split())
                for item in (record.recent_entities or [])
                if item.get("id") == cid
            )
        ]
        return matches[0] if len(matches) == 1 else None

    def resolve_document(
        self,
        workspace_key: str,
        query: str,
        *,
        course_id: str | None = None,
    ) -> str | None:
        """Resolve one recent document without crossing an explicit course boundary."""

        normalized = " ".join(query.casefold().split())
        if not normalized:
            return None
        record = self._session.scalar(
            select(AcademicWorkspace).where(
                AcademicWorkspace.user_key == self._user_key,
                AcademicWorkspace.workspace_key == workspace_key,
            )
        )
        if record is None:
            return None
        follow_up = normalized in {
            "it",
            "that",
            "that document",
            "that lecture",
            "this document",
            "this lecture",
            "quiz me on it",
            "make it harder",
            "give me an example",
            "what did the professor say about this",
        }
        matches = [
            item.get("id")
            for item in (record.recent_entities or [])
            if item.get("kind") == "document"
            and (course_id is None or item.get("course_id") == course_id)
            and (
                normalized in " ".join(item.get("label", "").casefold().split())
                or follow_up
            )
        ]
        return matches[0] if len(matches) == 1 else None

    def remember_entity(
        self,
        workspace_key: str,
        *,
        kind: str,
        entity_id: str,
        label: str,
        course_id: str,
        intent: str,
    ) -> WorkspaceView:
        """Keep bounded entity continuity without persisting conversation text."""

        if kind not in {"assignment", "document"}:
            raise ValueError("workspace entity kind is invalid")
        view = self.get_or_create(workspace_key, course_id=course_id)
        entity = {
            "kind": kind,
            "id": entity_id,
            "label": label,
            "course_id": course_id,
        }
        existing = [
            item
            for item in view.recent_entities
            if not (item.get("kind") == kind and item.get("id") == entity_id)
        ]
        return self.update(
            workspace_key,
            WorkspaceUpdate(
                recent_entities=tuple([entity, *existing][:20]),
                recent_intent=intent,
            ),
        )

    @staticmethod
    def _validate_key(workspace_key: str) -> None:
        if not workspace_key or len(workspace_key) > 255:
            raise ValueError("workspace key is invalid")

    @staticmethod
    def _view(record: AcademicWorkspace) -> WorkspaceView:
        return WorkspaceView(
            workspace_key=record.workspace_key,
            course_id=record.course_id,
            display_name=record.display_name,
            recent_entities=tuple(record.recent_entities or []),
            recent_intent=record.recent_intent,
            updated_at=record.updated_at,
        )
