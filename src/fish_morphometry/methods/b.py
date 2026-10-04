"""Método B: medición pinhole efectiva calibrada a través del vidrio."""

from __future__ import annotations

from collections.abc import Mapping
import math

import numpy as np

from ..calibration.b_calibration import BCalibrationProfile, validate_b_calibration_profile
from ..domain.models import BMeasurementResult, Point, Point3D, QualityReport
from ..geometry.rail_plane import (
    RailGeometryError,
    RailPlaneReference,
    build_measurement_plane,
    validate_rail_reference,
)
from ..geometry.ray_plane import intersect_image_points_with_plane
from ..measurements.quality import MeasurementError, validate_points


def _distance(point_a: Point3D, point_b: Point3D) -> float:
    distance = float(np.linalg.norm(np.asarray(point_b) - np.asarray(point_a)))
    if not math.isfinite(distance):
        raise MeasurementError("La distancia 3D calculada no es finita.")
    return distance


def _quality_warnings(profile: BCalibrationProfile, delta_z_mm: float) -> QualityReport:
    warnings = [
        "B es una aproximación pinhole efectiva a través de agua y vidrio; "
        "D_B no corrige físicamente la refracción."
    ]
    if profile.rms_px is not None and profile.rms_px >= 0.7:
        warnings.append(
            f"El RMS de calibración ({profile.rms_px:.3f} px) no alcanza el objetivo previsto de < 0,7 px."
        )
    if not math.isclose(delta_z_mm, 0.0, abs_tol=1e-9):
        warnings.append(
            f"La captura está separada {delta_z_mm:+.3f} mm de la zona de calibración; "
            "la exactitud debe comprobarse físicamente en esta posición."
        )
    return QualityReport(status="WARNING", warnings=tuple(warnings))


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
) -> BMeasurementResult:
    """Mide p1–p4 mediante rayos efectivos e intersección rayo–plano.

    Este contrato no recibe observaciones, IDs ni tamaños ArUco. Los puntos son
    las coordenadas de la imagen original compartidas con A y A′.
    """

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
    plane_point, plane_normal, delta_z_mm = build_measurement_plane(
        rail_reference,
        capture_rail_position_mm,
        replica_plane_offset_mm,
    )
    points_camera = intersect_image_points_with_plane(
        normalized_points,
        calibration_profile.K,
        calibration_profile.D,
        plane_point,
        plane_normal,
    )
    total_length = _distance(points_camera["p1"], points_camera["p2"])
    body_depth = _distance(points_camera["p3"], points_camera["p4"])
    quality = _quality_warnings(calibration_profile, delta_z_mm)
    return BMeasurementResult(
        method="B",
        image_id=str(image_id),
        replica_id=str(replica_id),
        repetition=None if repetition is None else str(repetition),
        capture_rail_position_mm=float(capture_rail_position_mm),
        delta_z_mm=delta_z_mm,
        replica_plane_offset_mm=float(replica_plane_offset_mm),
        units="mm",
        points_px=dict(normalized_points),
        points_camera_mm=points_camera,
        total_length_mm=total_length,
        body_depth_mm=body_depth,
        calibration_profile_id=calibration_profile.profile_id,
        calibration_profile_hash=calibration_profile.profile_hash,
        rail_reference_id=rail_reference.reference_id,
        quality=quality,
        metadata={
            "model": calibration_profile.model,
            "resolution": list(calibration_profile.resolution),
            "calibration_rms_px": calibration_profile.rms_px,
            "calibration_rail_position_mm": calibration_profile.calibration_rail_position_mm,
            "measurement_plane_point_camera_mm": list(plane_point),
            "measurement_plane_normal_camera": list(plane_normal),
            "rail_direction_camera": list(rail_reference.rail_direction_camera),
            "rail_positive_direction": rail_reference.positive_direction,
            "reference_image_id": rail_reference.reference_image_id,
            "reference_reprojection_error_px": rail_reference.reprojection_error_px,
            "replica_planes_parallel_to_board": rail_reference.replica_planes_parallel_to_board,
            "rail_perpendicular_to_board": rail_reference.rail_perpendicular_to_board,
            "uses_aruco": False,
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
        for name, point in points_px.items():
            try:
                safe_points[str(name)] = (float(point[0]), float(point[1]))
            except (TypeError, ValueError, IndexError):
                continue
        return BMeasurementResult(
            method="B",
            image_id=str(image_id),
            replica_id=str(replica_id),
            repetition=None if repetition is None else str(repetition),
            capture_rail_position_mm=safe_capture,
            delta_z_mm=safe_capture - rail_reference.z_ref_mm,
            replica_plane_offset_mm=safe_offset,
            units="mm",
            points_px=safe_points,
            points_camera_mm={},
            total_length_mm=None,
            body_depth_mm=None,
            calibration_profile_id=calibration_profile.profile_id,
            calibration_profile_hash=calibration_profile.profile_hash,
            rail_reference_id=rail_reference.reference_id,
            quality=QualityReport(status="ERROR", warnings=(str(exc),)),
            exclusion_reason=str(exc),
            metadata={"uses_aruco": False, "excluded": True},
        )


calculate_b = measure_b


__all__ = ["calculate_b", "measure_b", "measure_b_safe"]
