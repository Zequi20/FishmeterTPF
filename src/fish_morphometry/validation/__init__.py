"""Validación física de escala B con reglas o barras sumergidas."""

from .physical_b import (
    PhysicalValidationRecord,
    export_physical_validation,
    validate_known_segment_b,
)
from .c_validation import (
    CValidationRecord,
    CSensitivityPoint,
    apply_physical_validation_to_c_result,
    apply_physical_validations_to_c_result,
    export_c_validation,
    sensitivity_c,
    validate_known_segment_c,
)

__all__ = [
    "PhysicalValidationRecord",
    "CValidationRecord",
    "CSensitivityPoint",
    "apply_physical_validation_to_c_result",
    "apply_physical_validations_to_c_result",
    "export_c_validation",
    "sensitivity_c",
    "validate_known_segment_c",
    "export_physical_validation",
    "validate_known_segment_b",
]
