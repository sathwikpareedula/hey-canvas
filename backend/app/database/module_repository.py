"""Persistence and ordered local queries for modules and module items."""

from datetime import datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session, selectinload

from app.database.change_repository import ChangeRecorder
from app.database.models import Course, CourseModule, ModuleItem
from app.modules.models import ModuleCourseSyncCounts, ModuleItemSnapshot, ModuleSnapshot

MODULE_METADATA_FIELDS = (
    "name",
    "position",
    "unlock_at",
    "require_sequential_progress",
    "requirement_type",
    "publish_final_grade",
    "workflow_state",
    "state",
    "completed_at",
    "items_count",
    "published",
)

ITEM_METADATA_FIELDS = (
    "title",
    "position",
    "item_type",
    "content_id",
    "html_url",
    "api_url",
    "page_url",
    "external_url",
    "new_tab",
    "completion_requirement",
    "content_details",
    "indent",
    "published",
)


class ModuleRepository:
    """Upsert a complete course structure inside a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def synchronize_course(
        self,
        course: Course,
        snapshots: list[ModuleSnapshot],
        *,
        synced_at: datetime,
    ) -> ModuleCourseSyncCounts:
        if synced_at.tzinfo is None or synced_at.utcoffset() is None:
            raise ValueError("synced_at must be timezone-aware")

        modules_by_id = self._deduplicate_modules(course, snapshots)
        existing_modules = self._find_modules(course.id, list(modules_by_id))
        all_existing_modules = self._find_all_modules(course.id)
        all_existing_items = self._find_all_items(course.id)
        recorder = ChangeRecorder(self._session, observed_at=synced_at, source="canvas_sync")
        modules_created = modules_updated = modules_unchanged = 0

        for module_canvas_id, module_snapshot in modules_by_id.items():
            module = existing_modules.get(module_canvas_id)
            if module is None:
                module = CourseModule(
                    course=course,
                    canvas_module_id=module_canvas_id,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                    prerequisite_module_ids=list(module_snapshot.prerequisite_module_ids),
                )
                self._apply_module(module, module_snapshot)
                self._session.add(module)
                existing_modules[module_canvas_id] = module
                recorder.created("module", module_canvas_id, course.canvas_course_id)
                modules_created += 1
                continue

            changed = self._module_changed(module, module_snapshot)
            self._record_module_changes(recorder, course.canvas_course_id, module, module_snapshot)
            self._apply_module(module, module_snapshot)
            module.last_seen_at = synced_at
            module.last_synced_at = synced_at
            if changed:
                modules_updated += 1
            else:
                modules_unchanged += 1

        self._session.flush()

        item_snapshots = [item for module in snapshots for item in module.items]
        items_by_id = self._deduplicate_items(course, item_snapshots, modules_by_id)
        existing_items = self._find_items(course.id, list(items_by_id))
        items_created = items_updated = items_unchanged = 0

        for item_canvas_id, item_snapshot in items_by_id.items():
            parent = existing_modules[item_snapshot.canvas_module_id]
            item = existing_items.get(item_canvas_id)
            if item is None:
                item = ModuleItem(
                    course=course,
                    module=parent,
                    canvas_module_item_id=item_canvas_id,
                    first_seen_at=synced_at,
                    last_seen_at=synced_at,
                    last_synced_at=synced_at,
                )
                self._apply_item(item, item_snapshot, parent=parent)
                self._session.add(item)
                recorder.created("module_item", item_canvas_id, course.canvas_course_id)
                items_created += 1
                recorder.observe_status(
                    key=f"module_item:{course.canvas_course_id}:{item_canvas_id}",
                    entity_type="module_item",
                    external_id=item_canvas_id,
                    course_id=course.canvas_course_id,
                    status="present",
                    transition_event="reference_added",
                )
                continue

            changed = item.module_id != parent.id or self._item_changed(item, item_snapshot)
            self._record_item_changes(
                recorder, course.canvas_course_id, item, item_snapshot, parent
            )
            self._apply_item(item, item_snapshot, parent=parent)
            item.last_seen_at = synced_at
            item.last_synced_at = synced_at
            if changed:
                items_updated += 1
            else:
                items_unchanged += 1
            recorder.observe_status(
                key=f"module_item:{course.canvas_course_id}:{item_canvas_id}",
                entity_type="module_item",
                external_id=item_canvas_id,
                course_id=course.canvas_course_id,
                status="present",
                transition_event="reference_added",
            )

        observed_item_ids = set(items_by_id)
        for item in all_existing_items:
            if item.canvas_module_item_id not in observed_item_ids:
                recorder.observe_status(
                    key=f"module_item:{course.canvas_course_id}:{item.canvas_module_item_id}",
                    entity_type="module_item",
                    external_id=item.canvas_module_item_id,
                    course_id=course.canvas_course_id,
                    status="absent",
                    transition_event="reference_removed",
                    details={"canvas_module_id": item.module.canvas_module_id},
                )
        observed_module_ids = set(modules_by_id)
        for module_canvas_id in observed_module_ids:
            recorder.observe_status(
                key=f"module:{course.canvas_course_id}:{module_canvas_id}",
                entity_type="module",
                external_id=module_canvas_id,
                course_id=course.canvas_course_id,
                status="present",
                transition_event="reference_added",
            )
        for module in all_existing_modules:
            if module.canvas_module_id in observed_module_ids:
                continue
            recorder.observe_status(
                key=f"module:{course.canvas_course_id}:{module.canvas_module_id}",
                entity_type="module",
                external_id=module.canvas_module_id,
                course_id=course.canvas_course_id,
                status="absent",
                transition_event="reference_removed",
            )

        return ModuleCourseSyncCounts(
            modules_received=len(snapshots),
            modules_created=modules_created,
            modules_updated=modules_updated,
            modules_unchanged=modules_unchanged,
            items_received=len(item_snapshots),
            items_created=items_created,
            items_updated=items_updated,
            items_unchanged=items_unchanged,
        )

    def list_ordered(self, *, canvas_course_id: str | None = None) -> list[CourseModule]:
        """Load ordered modules and their items in two queries, not one query per module."""

        statement = (
            select(CourseModule)
            .join(Course)
            .options(selectinload(CourseModule.course), selectinload(CourseModule.items))
        )
        if canvas_course_id is not None:
            statement = statement.where(Course.canvas_course_id == canvas_course_id)
        statement = statement.order_by(
            Course.canvas_course_id,
            case((CourseModule.position.is_(None), 1), else_=0),
            CourseModule.position,
            CourseModule.canvas_module_id,
            CourseModule.id,
        )
        modules = list(self._session.scalars(statement))
        for module in modules:
            module.items.sort(key=_item_sort_key)
        return modules

    def _find_modules(self, course_id: int, ids: list[str]) -> dict[str, CourseModule]:
        if not ids:
            return {}
        statement = select(CourseModule).where(
            CourseModule.course_id == course_id,
            CourseModule.canvas_module_id.in_(ids),
        )
        return {module.canvas_module_id: module for module in self._session.scalars(statement)}

    def _find_items(self, course_id: int, ids: list[str]) -> dict[str, ModuleItem]:
        if not ids:
            return {}
        statement = select(ModuleItem).where(
            ModuleItem.course_id == course_id,
            ModuleItem.canvas_module_item_id.in_(ids),
        )
        return {item.canvas_module_item_id: item for item in self._session.scalars(statement)}

    def _find_all_modules(self, course_id: int) -> list[CourseModule]:
        statement = select(CourseModule).where(CourseModule.course_id == course_id)
        return list(self._session.scalars(statement))

    def _find_all_items(self, course_id: int) -> list[ModuleItem]:
        statement = (
            select(ModuleItem)
            .where(ModuleItem.course_id == course_id)
            .options(selectinload(ModuleItem.module))
        )
        return list(self._session.scalars(statement))

    @staticmethod
    def _deduplicate_modules(
        course: Course,
        snapshots: list[ModuleSnapshot],
    ) -> dict[str, ModuleSnapshot]:
        by_id: dict[str, ModuleSnapshot] = {}
        for snapshot in snapshots:
            if snapshot.canvas_course_id != course.canvas_course_id:
                raise ValueError("module snapshot course does not match database course")
            previous = by_id.get(snapshot.canvas_module_id)
            if previous is not None and previous != snapshot:
                raise ValueError("conflicting snapshots for one Canvas module")
            by_id[snapshot.canvas_module_id] = snapshot
        return by_id

    @staticmethod
    def _deduplicate_items(
        course: Course,
        snapshots: list[ModuleItemSnapshot],
        modules_by_id: dict[str, ModuleSnapshot],
    ) -> dict[str, ModuleItemSnapshot]:
        by_id: dict[str, ModuleItemSnapshot] = {}
        for snapshot in snapshots:
            if snapshot.canvas_course_id != course.canvas_course_id:
                raise ValueError("module item course does not match database course")
            if snapshot.canvas_module_id not in modules_by_id:
                raise ValueError("module item references a module outside the fetched structure")
            previous = by_id.get(snapshot.canvas_module_item_id)
            if previous is not None and previous != snapshot:
                raise ValueError("conflicting snapshots for one Canvas module item")
            by_id[snapshot.canvas_module_item_id] = snapshot
        return by_id

    @staticmethod
    def _module_changed(module: CourseModule, snapshot: ModuleSnapshot) -> bool:
        return any(
            getattr(module, field) != getattr(snapshot, field) for field in MODULE_METADATA_FIELDS
        ) or module.prerequisite_module_ids != list(snapshot.prerequisite_module_ids)

    @staticmethod
    def _apply_module(module: CourseModule, snapshot: ModuleSnapshot) -> None:
        for field in MODULE_METADATA_FIELDS:
            setattr(module, field, getattr(snapshot, field))
        module.prerequisite_module_ids = list(snapshot.prerequisite_module_ids)

    @staticmethod
    def _record_module_changes(
        recorder: ChangeRecorder,
        course_id: str,
        module: CourseModule,
        snapshot: ModuleSnapshot,
    ) -> None:
        for field in (
            "name",
            "position",
            "unlock_at",
            "require_sequential_progress",
            "requirement_type",
            "publish_final_grade",
            "workflow_state",
            "state",
            "published",
        ):
            recorder.changed(
                entity_type="module",
                external_id=module.canvas_module_id,
                course_id=course_id,
                field_name=field,
                old_value=getattr(module, field),
                new_value=getattr(snapshot, field),
            )

    @staticmethod
    def _item_changed(item: ModuleItem, snapshot: ModuleItemSnapshot) -> bool:
        return any(
            getattr(item, field) != getattr(snapshot, field) for field in ITEM_METADATA_FIELDS
        )

    @staticmethod
    def _apply_item(
        item: ModuleItem,
        snapshot: ModuleItemSnapshot,
        *,
        parent: CourseModule,
    ) -> None:
        item.module = parent
        for field in ITEM_METADATA_FIELDS:
            setattr(item, field, getattr(snapshot, field))

    @staticmethod
    def _record_item_changes(
        recorder: ChangeRecorder,
        course_id: str,
        item: ModuleItem,
        snapshot: ModuleItemSnapshot,
        parent: CourseModule,
    ) -> None:
        recorder.changed(
            entity_type="module_item",
            external_id=item.canvas_module_item_id,
            course_id=course_id,
            field_name="canvas_module_id",
            old_value=item.module.canvas_module_id,
            new_value=parent.canvas_module_id,
        )
        for field in ("title", "position", "indent", "item_type", "content_id", "published"):
            recorder.changed(
                entity_type="module_item",
                external_id=item.canvas_module_item_id,
                course_id=course_id,
                field_name=field,
                old_value=getattr(item, field),
                new_value=getattr(snapshot, field),
            )


def _item_sort_key(item: ModuleItem) -> tuple[bool, int, str, int]:
    return (
        item.position is None,
        item.position if item.position is not None else 0,
        item.canvas_module_item_id,
        item.id,
    )
