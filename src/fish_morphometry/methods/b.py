"""Método B: medición pinhole efectiva calibrada a través del vidrio."""

from __future__ import annotations

from collections.abc import Mapping
import math

from ..calibration.b_calibration import BCalibrationProfile, validate_b_calibration_profile
from ..domain.models import BMeasurementResult, Point, QualityReport
from ..geometry.rail_plane import (
    RailGeometryError,
    RailPlaneReference,
    build_measurement_plane,
    validate_rail_reference,
)
from ..geometry.ray_plane import intersect_image_points_with_plane
from ..geometry.ray_plane import image_axis_to_plane_direction
from ..measurements.morphometry import measure_projected_morphometry_3d, normalize_axis
from ..measurements.quality import MeasurementError, validate_points


def _quality_warnings(
    profile: BCalibrationProfile,
    rail_reference: RailPlaneReference,
    delta_z_mm: float,
    *,
    body_depth_valid: bool,
    body_depth_section_angle_degrees: float,
    maximum_depth_section_angle_degrees: float,
) -> QualityReport:
    warnings = [
        "B es una aproximación pinhole efectiva a través de agua y vidrio; "
        "D_B no corrige físicamente la refracción."
    ]
    if profile.rms_px is not None and profile.rms_px >= 0.7:
        warnings.append(
            f"El RMS de calibración ({profile.rms_px:.3f} px) no alcanza el objetivo previsto de < 0,7 px."
        )
    if rail_reference.direction_source == "manual":
        warnings.append(
            "La dirección del rail fue suministrada manualmente; se recomienda "
            "estimarla con referencias en dos o más posiciones conocidas."
        )
    if rail_reference.calibration_context_hash is None:
        warnings.append(
            "La referencia del rail es heredada y no enlaza el contexto completo "
            "de calibración; regenérela para trazabilidad plena."
        )
    if rail_reference.rail_scale_check_status == "WARNING":
        scale_error = rail_reference.rail_scale_relative_error
        assert scale_error is not None and rail_reference.rail_scale_norm is not None
        warnings.append(
            "Referencia B provisional — pendiente de validación métrica: "
            f"la escala pose/rail tiene norma {rail_reference.rail_scale_norm:.4f} "
            f"({scale_error * 100:+.2f} % respecto de 1)."
        )
    elif rail_reference.rail_scale_check_status == "NOT_AVAILABLE":
        warnings.append(
            "La referencia B no conserva un diagnóstico de escala pose/rail; "
            "permanece provisional hasta validarla físicamente."
        )
    if not math.isclose(delta_z_mm, 0.0, abs_tol=1e-9):
        warnings.append(
            f"La captura está separada {delta_z_mm:+.3f} mm de la zona de calibración; "
            "la exactitud debe comprobarse físicamente en esta posición."
        )
    if not body_depth_valid:
        warnings.append(
            "p3–p4 no pertenece a una sección suficientemente perpendicular al eje "
            f"({body_depth_section_angle_degrees:.3f}° > "
            f"{maximum_depth_section_angle_degrees:.3f}°); la profundidad fue invalidada."
        )
    return QualityReport(status="PENDING_VALIDATION", warnings=tuple(warnings))


def measure_b(
    image_id: str,
    points_px: Mapping[str, Point],
    calibration_profile: BCalibrationProfile,
    rail_reference: RailPlaneReference,
    capture_rail_position_mm: float,
    replica_plane_offset_mm: float,
    *,
    replica_id: str,
    repetition: str | int | None = None,
    image_shape: tuple[int, ...] | None = None,
    units: str = "mm",
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
    replica_plane_offset_direction: str = "rail",
) -> BMeasurementResult:
    """Mide p1–p4 mediante rayos efectivos e intersección rayo–plano.

    Este contrato no recibe observaciones, IDs ni tamaños ArUco. Los puntos son
    las coordenadas de la imagen original compartidas con A y A′.
    """

    from .. import __version__

    validate_b_calibration_profile(calibration_profile)
    validate_rail_reference(rail_reference)
    if str(units).strip().lower() != "mm":
        raise MeasurementError("El método B requiere unidades físicas en mm.")
    if not str(image_id).strip():
        raise MeasurementError("B requiere un ID de imagen.")
    if not str(replica_id).strip():
        raise MeasurementError("B requiere seleccionar un ID de réplica.")
    if rail_reference.calibration_profile_hash != calibration_profile.profile_hash:
        raise RailGeometryError(
            "La referencia cámara–rail fue creada con otro perfil de calibración B."
        )
    if (
        rail_reference.calibration_context_hash is not None
        and rail_reference.calibration_context_hash
        != calibration_profile.calibration_context_hash
    ):
        raise RailGeometryError(
            "La referencia cámara–rail fue creada en otro contexto de calibración B."
        )
    if not math.isclose(
        rail_reference.z_ref_mm,
        calibration_profile.calibration_rail_position_mm,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise RailGeometryError(
            "z_ref_mm de la referencia no coincide con la zona del perfil B."
        )
    if image_shape is not None:
        if len(image_shape) < 2:
            raise MeasurementError("La forma de imagen no es válida.")
        actual_resolution = (int(image_shape[1]), int(image_shape[0]))
        if actual_resolution != calibration_profile.resolution:
            raise MeasurementError(
                f"Resolución incompatible con B: imagen {actual_resolution[0]}×{actual_resolution[1]}; "
                f"perfil {calibration_profile.resolution[0]}×{calibration_profile.resolution[1]}."
            )
    normalized_points = validate_points(points_px, image_shape)
    normalized_axis_px = normalize_axis(longitudinal_axis_px)
    plane_point, plane_normal, delta_z_mm = build_measurement_plane(
        rail_reference,
        capture_rail_position_mm,
        replica_plane_offset_mm,
        replica_plane_offset_direction=replica_plane_offset_direction,
    )
    points_camera = intersect_image_points_with_plane(
        normalized_points,
        calibration_profile.K,
        calibration_profile.D,
        plane_point,
        plane_normal,
    )
    axis_camera = image_axis_to_plane_direction(
        normalized_points["p1"],
        normalized_axis_px,
        calibration_profile.K,
        calibration_profile.D,
        plane_point,
        plane_normal,
        probe_length_px=max(30.0, min(calibration_profile.resolution) * 0.1),
    )
    morphometry = measure_projected_morphometry_3d(
        points_camera,
        axis_camera,
        plane_normal,
        maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
    )
    quality = _quality_warnings(
        calibration_profile,
        rail_reference,
        delta_z_mm,
        body_depth_valid=morphometry.body_depth_valid,
        body_depth_section_angle_degrees=morphometry.body_depth_section_angle_degrees,
        maximum_depth_section_angle_degrees=float(maximum_depth_section_angle_degrees),
    )
    return BMeasurementResult(
        method="B",
        image_id=str(image_id),
        replica_id=str(replica_id),
        repetition=None if repetition is None else str(repetition),
        capture_rail_position_mm=float(capture_rail_position_mm),
        delta_z_mm=delta_z_mm,
        replica_plane_offset_mm=float(replica_plane_offset_mm),
        replica_plane_offset_direction=str(replica_plane_offset_direction).strip().lower(),
        units="mm",
        points_px=dict(normalized_points),
        points_camera_mm=points_camera,
        longitudinal_axis_px=normalized_axis_px,
        longitudinal_axis_camera=morphometry.longitudinal_axis,
        normal_axis_camera=morphometry.normal_axis,
        maximum_depth_section_angle_degrees=float(maximum_depth_section_angle_degrees),
        total_length_mm=morphometry.total_length_mm,
        body_depth_mm=morphometry.body_depth_mm,
        total_length_euclidean_mm=morphometry.total_length_euclidean_mm,
        body_depth_euclidean_mm=morphometry.body_depth_euclidean_mm,
        body_depth_section_offset_mm=morphometry.body_depth_section_offset_mm,
        body_depth_section_angle_degrees=morphometry.body_depth_section_angle_degrees,
        body_depth_valid=morphometry.body_depth_valid,
        calibration_profile_id=calibration_profile.profile_id,
        calibration_profile_hash=calibration_profile.profile_hash,
        calibration_context_hash=calibration_profile.calibration_context_hash,
        rail_reference_id=rail_reference.reference_id,
        rail_reference_hash=rail_reference.reference_hash,
        quality=quality,
        metadata={
            "model": calibration_profile.model,
            "resolution": list(calibration_profile.resolution),
            "calibration_rms_px": calibration_profile.rms_px,
            "calibration_rail_position_mm": calibration_profile.calibration_rail_position_mm,
            "calibration_context_hash": calibration_profile.calibration_context_hash,
            "measurement_plane_point_camera_mm": list(plane_point),
            "measurement_plane_normal_camera": list(plane_normal),
            "rail_direction_camera": list(rail_reference.rail_direction_camera),
            "rail_direction_source": rail_reference.direction_source,
            "rail_positions_used_mm": list(rail_reference.rail_positions_used_mm),
            "rail_fit_residual_mm": rail_reference.rail_fit_residual_mm,
            "rail_normal_spread_degrees": rail_reference.normal_spread_degrees,
            "rail_scale_norm": rail_reference.rail_scale_norm,
            "rail_scale_relative_error": rail_reference.rail_scale_relative_error,
            "rail_scale_check_status": rail_reference.rail_scale_check_status,
            "maximum_rail_scale_relative_error": (
                rail_reference.maximum_rail_scale_relative_error
            ),
            "rail_reference_metric_validation_status": "PENDING_VALIDATION",
            "rail_positive_direction": rail_reference.positive_direction,
            "reference_image_id": rail_reference.reference_image_id,
            "reference_reprojection_error_px": rail_reference.reprojection_error_px,
            "replica_planes_parallel_to_board": rail_reference.replica_planes_parallel_to_board,
            "rail_perpendicular_to_board": rail_reference.rail_perpendicular_to_board,
            "uses_aruco": False,
            "points_source": "shared_annotation",
            "measurement_convention": "projected_anatomical_axes",
            "algorithm_version": "b_projected_anatomical_axes.v1",
            "app_version": __version__,
            "replica_plane_offset_direction": str(replica_plane_offset_direction).strip().lower(),
            "ray_model": "cv2.undistortPoints(P=None) -> (x,y,1)",
        },
    )


def measure_b_safe(
    image_id: str,
    points_px: Mapping[str, Point],
    calibration_profile: BCalibrationProfile,
    rail_reference: RailPlaneReference,
    capture_rail_position_mm: float,
    replica_plane_offset_mm: float,
    *,
    replica_id: str,
    repetition: str | int | None = None,
    image_shape: tuple[int, ...] | None = None,
    units: str = "mm",
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
    replica_plane_offset_direction: str = "rail",
) -> BMeasurementResult:
    """Devuelve un resultado ``ERROR`` trazable cuando una captura se excluye.

    ``measure_b`` mantiene el contrato estricto (lanza una excepción); esta
    variante es útil para lotes y para exportar el motivo de exclusión.
    """

    try:
        return measure_b(
            image_id,
            points_px,
            calibration_profile,
            rail_reference,
            capture_rail_position_mm,
            replica_plane_offset_mm,
            replica_id=replica_id,
            repetition=repetition,
            image_shape=image_shape,
            units=units,
            longitudinal_axis_px=longitudinal_axis_px,
            maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
            replica_plane_offset_direction=replica_plane_offset_direction,
        )
    except Exception as exc:  # noqa: BLE001 - el motivo se conserva en la trazabilidad B.
        try:
            safe_capture = float(capture_rail_position_mm)
            if not math.isfinite(safe_capture):
                safe_capture = 0.0
        except (TypeError, ValueError):
            safe_capture = 0.0
        try:
            safe_offset = float(replica_plane_offset_mm)
            if not math.isfinite(safe_offset):
                safe_offset = 0.0
        except (TypeError, ValueError):
            safe_offset = 0.0
        safe_points: dict[str, Point] = {}
        point_items = points_px.items() if isinstance(points_px, Mapping) else ()
        for name, point in point_items:
            try:
                safe_points[str(name)] = (float(point[0]), float(point[1]))
            except (TypeError, ValueError, IndexError):
                continue
        try:
            safe_reference_position = float(getattr(rail_reference, "z_ref_mm", 0.0))
            if not math.isfinite(safe_reference_position):
                safe_reference_position = 0.0
        except (TypeError, ValueError):
            safe_reference_position = 0.0

        def safe_text(value: object) -> str:
            return "" if value is None else str(value)

        try:
            reference_hash = safe_text(getattr(rail_reference, "reference_hash", ""))
        except Exception:  # noqa: BLE001 - la referencia defectuosa es el error a registrar.
            reference_hash = ""
        try:
            context_hash = safe_text(
                getattr(calibration_profile, "calibration_context_hash", "")
            )
        except Exception:  # noqa: BLE001 - el perfil defectuoso es el error a registrar.
            context_hash = ""
        return BMeasurementResult(
            method="B",
            image_id=str(image_id),
            replica_id=str(replica_id),
            repetition=None if repetition is None else str(repetition),
            capture_rail_position_mm=safe_capture,
            delta_z_mm=safe_capture - safe_reference_position,
            replica_plane_offset_mm=safe_offset,
            replica_plane_offset_direction=str(replica_plane_offset_direction),
            units="mm",
            points_px=safe_points,
            points_camera_mm={},
            longitudinal_axis_px=None,
            longitudinal_axis_camera=None,
            normal_axis_camera=None,
            maximum_depth_section_angle_degrees=None,
            total_length_mm=None,
            body_depth_mm=None,
            total_length_euclidean_mm=None,
            body_depth_euclidean_mm=None,
            body_depth_section_offset_mm=None,
            body_depth_section_angle_degrees=None,
            body_depth_valid=None,
            calibration_profile_id=safe_text(getattr(calibration_profile, "profile_id", "")),
            calibration_profile_hash=safe_text(
                getattr(calibration_profile, "profile_hash", "")
            ),
            calibration_context_hash=context_hash,
            rail_reference_id=safe_text(getattr(rail_reference, "reference_id", "")),
            rail_reference_hash=reference_hash,
            quality=QualityReport(status="ERROR", warnings=(str(exc),)),
            exclusion_reason=str(exc),
            metadata={
                "uses_aruco": False,
                "excluded": True,
                "error_type": type(exc).__name__,
            },
        )


calculate_b = measure_b


__all__ = ["calculate_b", "measure_b", "measure_b_safe"]
