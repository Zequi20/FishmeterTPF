"""Método C: modelo explícito de puerto plano aire–vidrio–agua."""

from __future__ import annotations

from collections.abc import Mapping
import math

import numpy as np

from ..calibration.air_calibration import AirCalibrationProfile, validate_air_profile
from ..domain.models import CMeasurementResult, Point, Point3D, QualityReport
from ..geometry.ray_plane import RayPlaneError, intersect_ray_line_plane, undistort_points_to_rays
from ..geometry.refractive_port import (
    FlatPortParameters,
    MeasurementPlane,
    RefractivePortError,
    make_measurement_plane,
    trace_refracted_ray,
)
from ..measurements.quality import MeasurementError, validate_points


def _coerce_plane(value: MeasurementPlane | Mapping[str, object]) -> MeasurementPlane:
    if isinstance(value, MeasurementPlane):
        return value
    if not isinstance(value, Mapping):
        raise MeasurementError("El plano de medición C no está definido.")
    plane_units = str(value.get("units", "mm")).strip().lower()
    if plane_units not in {"mm", "millimeter", "millimeters"}:
        raise MeasurementError("El plano de medición C debe estar expresado explícitamente en mm.")
    point = value.get("point_camera_mm", value.get("point"))
    normal = value.get("normal_camera", value.get("normal"))
    if point is None or normal is None:
        raise MeasurementError("El plano C requiere point_camera_mm y normal_camera.")
    try:
        return make_measurement_plane(
            point,
            normal,
            source=str(value.get("source", "explicit")),
            plane_id=str(value.get("plane_id", "measurement-plane")),
        )
    except RefractivePortError as exc:
        raise MeasurementError(str(exc)) from exc


def _distance(first: Point3D, second: Point3D) -> float:
    result = float(np.linalg.norm(np.asarray(second) - np.asarray(first)))
    if not math.isfinite(result):
        raise MeasurementError("La distancia refractiva calculada no es finita.")
    return result


def measure_c(
    image_id: str,
    points_px: Mapping[str, Point],
    air_profile: AirCalibrationProfile,
    flat_port: FlatPortParameters,
    measurement_plane: MeasurementPlane | Mapping[str, object],
    *,
    replica_id: str = "",
    repetition: str | int | None = None,
    image_shape: tuple[int, ...] | None = None,
    units: str = "mm",
    interface_tolerance_mm: float = 1e-6,
) -> CMeasurementResult:
    """Convierte p1–p4 en puntos métricos con dos refracciones explícitas."""

    validate_air_profile(air_profile)
    if str(units).strip().lower() != "mm":
        raise MeasurementError("El método C requiere unidades internas explícitas en mm.")
    if not str(image_id).strip():
        raise MeasurementError("C requiere un ID de imagen.")
    if image_shape is not None:
        if len(image_shape) < 2:
            raise MeasurementError("La forma de la imagen no es válida.")
        actual = (int(image_shape[1]), int(image_shape[0]))
        if actual != air_profile.resolution:
            raise MeasurementError(
                f"Resolución incompatible con C: imagen {actual[0]}×{actual[1]}; "
                f"perfil en aire {air_profile.resolution[0]}×{air_profile.resolution[1]}."
            )
    normalized_points = validate_points(points_px, image_shape)
    plane = _coerce_plane(measurement_plane)
    rays = undistort_points_to_rays(normalized_points, air_profile.K, air_profile.D)
    q1_values: dict[str, Point3D] = {}
    q2_values: dict[str, Point3D] = {}
    air_values: dict[str, Point3D] = {}
    glass_values: dict[str, Point3D] = {}
    water_values: dict[str, Point3D] = {}
    measured: dict[str, Point3D] = {}
    residuals: dict[str, dict[str, float]] = {}
    for name, ray in rays.items():
        try:
            trace = trace_refracted_ray(ray, flat_port, interface_tolerance_mm=interface_tolerance_mm)
            point = intersect_ray_line_plane(
                trace.q2_camera_mm,
                trace.v_water,
                plane.point_camera_mm,
                plane.normal_camera,
            )
        except (RefractivePortError, RayPlaneError) as exc:
            raise MeasurementError(f"No se pudo calcular C para {name}: {exc}") from exc
        air_values[name] = trace.v_air
        q1_values[name] = trace.q1_camera_mm
        glass_values[name] = trace.v_glass
        q2_values[name] = trace.q2_camera_mm
        water_values[name] = trace.v_water
        measured[name] = point
        residuals[name] = {
            "first_interface_mm": trace.first_interface_residual_mm,
            "second_interface_mm": trace.second_interface_residual_mm,
        }
    warnings = [
        "C usa el modelo explícito aire–vidrio–agua y requiere validación física sumergida.",
        "El estado permanece PENDING_VALIDATION hasta cumplir el protocolo físico.",
    ]
    if air_profile.rms_px is not None and air_profile.rms_px >= 0.5:
        warnings.append(
            f"El RMS de calibración en aire ({air_profile.rms_px:.3f} px) no alcanza el objetivo previsto de < 0,5 px."
        )
    if flat_port.lens_distance_approximation:
        warnings.append("La distancia de interfaz proviene de una aproximación lente–vidrio; registre su incertidumbre.")
    if flat_port.normal_was_normalized:
        warnings.append("La normal del puerto fue normalizada al cargar el perfil.")
    return CMeasurementResult(
        method="C",
        image_id=str(image_id),
        replica_id=str(replica_id),
        repetition=None if repetition is None else str(repetition),
        calibration_profile_id=air_profile.profile_id,
        calibration_profile_hash=air_profile.profile_hash,
        points_px=dict(normalized_points),
        q1_camera_mm=q1_values,
        q2_camera_mm=q2_values,
        v_air=air_values,
        v_glass=glass_values,
        v_water=water_values,
        points_camera_mm=measured,
        measurement_plane_point_camera_mm=plane.point_camera_mm,
        measurement_plane_normal_camera=plane.normal_camera,
        port_normal_camera=flat_port.port_normal,
        interface_distance_mm=flat_port.interface_distance_mm,
        glass_thickness_mm=flat_port.glass_thickness_mm,
        n_air=flat_port.n_air,
        n_glass=flat_port.n_glass,
        n_water=flat_port.n_water,
        units="mm",
        total_length_mm=_distance(measured["p1"], measured["p2"]),
        body_depth_mm=_distance(measured["p3"], measured["p4"]),
        quality=QualityReport(status="PENDING_VALIDATION", warnings=tuple(warnings)),
        metadata={
            "points_source": "shared_annotation",
            "port_source": flat_port.source,
            "lens_distance_approximation": flat_port.lens_distance_approximation,
            "port_uncertainty_note": flat_port.uncertainty_note,
            "normal_was_normalized": flat_port.normal_was_normalized,
            "measurement_plane": plane.to_dict(),
            "interface_residuals_mm": residuals,
            "interface_tolerance_mm": float(interface_tolerance_mm),
            "coordinate_convention": "X derecha, Y abajo, Z cámara hacia pecera",
            "uses_aruco": False,
            "uses_global_scale": False,
        },
    )


def measure_c_safe(
    image_id: str,
    points_px: Mapping[str, Point],
    air_profile: AirCalibrationProfile,
    flat_port: FlatPortParameters,
    measurement_plane: MeasurementPlane | Mapping[str, object],
    **kwargs: object,
) -> CMeasurementResult:
    """Variante de lote que conserva una captura excluida y su motivo."""

    try:
        return measure_c(image_id, points_px, air_profile, flat_port, measurement_plane, **kwargs)
    except Exception as exc:  # noqa: BLE001 - el motivo queda en exclusion_reason.
        replica_id = str(kwargs.get("replica_id", ""))
        repetition = kwargs.get("repetition")
        try:
            plane = _coerce_plane(measurement_plane)
        except Exception:
            plane = make_measurement_plane((0.0, 0.0, 1.0), (0.0, 0.0, 1.0), plane_id="unknown")
        safe_points: dict[str, Point] = {}
        for name, point in points_px.items():
            try:
                safe_points[str(name)] = (float(point[0]), float(point[1]))
            except (TypeError, ValueError, IndexError):
                continue
        return CMeasurementResult(
            method="C",
            image_id=str(image_id),
            replica_id=replica_id,
            repetition=None if repetition is None else str(repetition),
            calibration_profile_id=air_profile.profile_id,
            calibration_profile_hash=air_profile.profile_hash,
            points_px=safe_points,
            q1_camera_mm={}, q2_camera_mm={}, v_air={}, v_glass={}, v_water={}, points_camera_mm={},
            measurement_plane_point_camera_mm=plane.point_camera_mm,
            measurement_plane_normal_camera=plane.normal_camera,
            port_normal_camera=flat_port.port_normal,
            interface_distance_mm=flat_port.interface_distance_mm,
            glass_thickness_mm=flat_port.glass_thickness_mm,
            n_air=flat_port.n_air, n_glass=flat_port.n_glass, n_water=flat_port.n_water,
            units="mm", total_length_mm=None, body_depth_mm=None,
            quality=QualityReport(status="ERROR", warnings=(str(exc),)),
            exclusion_reason=str(exc), metadata={"excluded": True, "uses_aruco": False},
        )


calculate_c = measure_c


__all__ = ["calculate_c", "measure_c", "measure_c_safe"]
