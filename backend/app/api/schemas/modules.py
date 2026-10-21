"""Stable public aliases for local course-structure schemas."""

from app.modules.models import (
    AssignmentReference,
    CourseModuleStructure,
    ModuleItemStructure,
)

CourseModuleResponse = CourseModuleStructure
ModuleItemResponse = ModuleItemStructure

__all__ = ["AssignmentReference", "CourseModuleResponse", "ModuleItemResponse"]
