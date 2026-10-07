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
    RefractedRay,
    RefractivePortError,
    make_measurement_plane,
    trace_refracted_ray,
)
from ..measurements.morphometry import measure_projected_morphometry_3d, normalize_axis
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
        plane = make_measurement_plane(
            point,
            normal,
            source=str(value.get("source", "explicit")),
            plane_id=str(value.get("plane_id", "measurement-plane")),
            coordinate_frame=str(
                value.get("coordinate_frame", "physical_camera_refractive")
            ),
        )
        stored_hash = value.get("plane_hash")
        if stored_hash is not None and str(stored_hash) != plane.plane_hash:
            raise MeasurementError("El hash del plano de medición C no coincide.")
        return plane
    except RefractivePortError as exc:
        raise MeasurementError(str(exc)) from exc


def _trace_to_plane(
    points_px: Mapping[str, Point],
    air_profile: AirCalibrationProfile,
    flat_port: FlatPortParameters,
    plane: MeasurementPlane,
    *,
    interface_tolerance_mm: float,
    minimum_plane_incidence_cosine: float,
) -> tuple[dict[str, Point3D], dict[str, RefractedRay]]:
    rays = undistort_points_to_rays(points_px, air_profile.K, air_profile.D)
    measured: dict[str, Point3D] = {}
    traces: dict[str, RefractedRay] = {}
    plane_normal = np.asarray(plane.normal_camera, dtype=float)
    for name, ray in rays.items():
        trace = trace_refracted_ray(
            ray, flat_port, interface_tolerance_mm=interface_tolerance_mm
        )
        incidence = abs(float(np.dot(plane_normal, np.asarray(trace.v_water, dtype=float))))
        if incidence < minimum_plane_incidence_cosine:
            raise RayPlaneError(
                "El rayo llega casi paralelo al plano de medición; la intersección es inestable."
            )
        measured[name] = intersect_ray_line_plane(
            trace.q2_camera_mm,
            trace.v_water,
            plane.point_camera_mm,
            plane.normal_camera,
            parallel_epsilon=minimum_plane_incidence_cosine,
        )
        traces[name] = trace
    return measured, traces


def _refracted_axis_to_plane_direction(
    anchor_px: Point,
    axis_px: Point,
    air_profile: AirCalibrationProfile,
    flat_port: FlatPortParameters,
    plane: MeasurementPlane,
    *,
    interface_tolerance_mm: float,
    minimum_plane_incidence_cosine: float,
) -> Point3D:
    axis = np.asarray(normalize_axis(axis_px), dtype=float)
    anchor = np.asarray(anchor_px, dtype=float)
    probe_length_px = max(30.0, min(air_profile.resolution) * 0.1)
    probe = anchor + axis * probe_length_px
    mapped, _traces = _trace_to_plane(
        {"anchor": tuple(anchor), "probe": tuple(probe)},
        air_profile,
        flat_port,
        plane,
        interface_tolerance_mm=interface_tolerance_mm,
        minimum_plane_incidence_cosine=minimum_plane_incidence_cosine,
    )
    direction = np.asarray(mapped["probe"], dtype=float) - np.asarray(
        mapped["anchor"], dtype=float
    )
    norm = float(np.linalg.norm(direction))
    if not np.all(np.isfinite(direction)) or norm <= 0:
        raise MeasurementError("El eje longitudinal no pudo transformarse al plano de C.")
    direction /= norm
    return (float(direction[0]), float(direction[1]), float(direction[2]))


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
    longitudinal_axis_px: Point = (1.0, 0.0),
    maximum_depth_section_angle_degrees: float = 5.0,
    minimum_plane_incidence_cosine: float = 1e-4,
) -> CMeasurementResult:
    """Traza p1–p4 y mide sobre ejes anatómicos en el plano físico de C."""

    from .. import __version__

    validate_air_profile(air_profile)
    if str(units).strip().lower() != "mm":
        raise MeasurementError("El método C requiere unidades internas explícitas en mm.")
    if not str(image_id).strip():
        raise MeasurementError("C requiere un ID de imagen.")
    if not str(replica_id).strip():
        raise MeasurementError("C requiere seleccionar un ID de réplica.")
    try:
        minimum_incidence = float(minimum_plane_incidence_cosine)
    except (TypeError, ValueError) as exc:
        raise MeasurementError(
            "El coseno mínimo de incidencia al plano debe ser numérico."
        ) from exc
    if not math.isfinite(minimum_incidence) or minimum_incidence <= 0 or minimum_incidence >= 1:
        raise MeasurementError(
            "El coseno mínimo de incidencia al plano debe estar entre 0 y 1."
        )
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
    normalized_axis_px = normalize_axis(longitudinal_axis_px)
    plane = _coerce_plane(measurement_plane)
    try:
        measured, traces = _trace_to_plane(
            normalized_points,
            air_profile,
            flat_port,
            plane,
            interface_tolerance_mm=interface_tolerance_mm,
            minimum_plane_incidence_cosine=minimum_incidence,
        )
        axis_camera = _refracted_axis_to_plane_direction(
            normalized_points["p1"],
            normalized_axis_px,
            air_profile,
            flat_port,
            plane,
            interface_tolerance_mm=interface_tolerance_mm,
            minimum_plane_incidence_cosine=minimum_incidence,
        )
        morphometry = measure_projected_morphometry_3d(
            measured,
            axis_camera,
            plane.normal_camera,
            maximum_depth_section_angle_degrees=maximum_depth_section_angle_degrees,
        )
    except (RefractivePortError, RayPlaneError) as exc:
        raise MeasurementError(f"No se pudo calcular la geometría refractiva de C: {exc}") from exc
    q1_values: dict[str, Point3D] = {}
    q2_values: dict[str, Point3D] = {}
    air_values: dict[str, Point3D] = {}
    glass_values: dict[str, Point3D] = {}
    water_values: dict[str, Point3D] = {}
    residuals: dict[str, dict[str, float]] = {}
    for name, trace in traces.items():
        air_values[name] = trace.v_air
        q1_values[name] = trace.q1_camera_mm
        glass_values[name] = trace.v_glass
        q2_values[name] = trace.q2_camera_mm
        water_values[name] = trace.v_water
        residuals[name] = {
            "first_interface_mm": trace.first_interface_residual_mm,
            "second_interface_mm": trace.second_interface_residual_mm,
        }
    warnings = [
        "C usa el modelo explícito aire–vidrio–agua y requiere validación física sumergida.",
        "El estado inicial es PENDING_VALIDATION hasta cumplir el protocolo físico.",
    ]
    if air_profile.rms_px is not None and air_profile.rms_px >= 0.5:
        rms_scope = (air_profile.source_metadata or {}).get("rms_scope")
        label = (
            "RMS refractivo global de Calibmar"
            if rms_scope == "calibmar_refractive_overall"
            else "RMS de calibración en aire"
        )
        warnings.append(f"El {label} ({air_profile.rms_px:.3f} px) es ≥ 0,5 px.")
    if flat_port.lens_distance_approximation:
        warnings.append("La distancia de interfaz proviene de una aproximación lente–vidrio; registre su incertidumbre.")
    if flat_port.normal_was_normalized:
        warnings.append("La normal del puerto fue normalizada al cargar el perfil.")
    if all(
        value is None
        for value in (
            flat_port.water_temperature_c,
            flat_port.water_salinity_ppt,
            flat_port.water_pressure_dbar,
        )
    ):
        warnings.append(
            "No se registraron temperatura, salinidad o presión del agua asociadas a n_water."
        )
    if not morphometry.body_depth_valid:
        warnings.append(
            "p3–p4 no pertenece a una sección suficientemente perpendicular al eje "
            f"({morphometry.body_depth_section_angle_degrees:.3f}° > "
            f"{float(maximum_depth_section_angle_degrees):.3f}°); la profundidad fue invalidada."
        )
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
        longitudinal_axis_px=normalized_axis_px,
        longitudinal_axis_camera=morphometry.longitudinal_axis,
        normal_axis_camera=morphometry.normal_axis,
        maximum_depth_section_angle_degrees=float(maximum_depth_section_angle_degrees),
        measurement_plane_point_camera_mm=plane.point_camera_mm,
        measurement_plane_normal_camera=plane.normal_camera,
        port_normal_camera=flat_port.port_normal,
        interface_distance_mm=flat_port.interface_distance_mm,
        glass_thickness_mm=flat_port.glass_thickness_mm,
        n_air=flat_port.n_air,
        n_glass=flat_port.n_glass,
        n_water=flat_port.n_water,
        units="mm",
        total_length_mm=morphometry.total_length_mm,
        body_depth_mm=morphometry.body_depth_mm,
        total_length_euclidean_mm=morphometry.total_length_euclidean_mm,
        body_depth_euclidean_mm=morphometry.body_depth_euclidean_mm,
        body_depth_section_offset_mm=morphometry.body_depth_section_offset_mm,
        body_depth_section_angle_degrees=morphometry.body_depth_section_angle_degrees,
        body_depth_valid=morphometry.body_depth_valid,
        calibration_context_hash=air_profile.calibration_context_hash,
        flat_port_hash=flat_port.port_hash,
        measurement_plane_id=plane.plane_id,
        measurement_plane_hash=plane.plane_hash,
        quality=QualityReport(status="PENDING_VALIDATION", warnings=tuple(warnings)),
        metadata={
            "points_source": "shared_annotation",
            "port_source": flat_port.source,
            "lens_distance_approximation": flat_port.lens_distance_approximation,
            "port_uncertainty_note": flat_port.uncertainty_note,
            "port_parameter_standard_deviations": flat_port.parameter_standard_deviations,
            "water_conditions": {
                "temperature_c": flat_port.water_temperature_c,
                "salinity_ppt": flat_port.water_salinity_ppt,
                "pressure_dbar": flat_port.water_pressure_dbar,
            },
            "normal_was_normalized": flat_port.normal_was_normalized,
            "measurement_plane": plane.to_dict(),
            "interface_residuals_mm": residuals,
            "interface_tolerance_mm": float(interface_tolerance_mm),
            "minimum_plane_incidence_cosine": minimum_incidence,
            "calibration_context_hash": air_profile.calibration_context_hash,
            "flat_port_hash": flat_port.port_hash,
            "measurement_plane_hash": plane.plane_hash,
            "measurement_convention": "projected_anatomical_axes",
            "axis_mapping": "refractive_local_probe_at_p1",
            "algorithm_version": "c_refractive_projected_anatomical_axes.v1",
            "app_version": __version__,
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
        point_items = points_px.items() if isinstance(points_px, Mapping) else ()
        for name, point in point_items:
            try:
                safe_points[str(name)] = (float(point[0]), float(point[1]))
            except (TypeError, ValueError, IndexError):
                continue

        def safe_text(value: object) -> str:
            return "" if value is None else str(value)

        profile_id = safe_text(getattr(air_profile, "profile_id", ""))
        profile_hash = safe_text(getattr(air_profile, "profile_hash", ""))
        try:
            context_hash = safe_text(getattr(air_profile, "calibration_context_hash", ""))
        except Exception:  # noqa: BLE001 - el perfil defectuoso es el error registrado.
            context_hash = ""
        try:
            port_hash = safe_text(getattr(flat_port, "port_hash", ""))
        except Exception:  # noqa: BLE001 - el puerto defectuoso es el error registrado.
            port_hash = ""

        def safe_float(attribute: str, fallback: float) -> float:
            try:
                value = float(getattr(flat_port, attribute, fallback))
                return value if math.isfinite(value) else fallback
            except (TypeError, ValueError):
                return fallback

        def safe_vector(attribute: str, fallback: Point3D) -> Point3D:
            try:
                value = tuple(float(item) for item in getattr(flat_port, attribute))
                if len(value) == 3 and all(math.isfinite(item) for item in value):
                    return value  # type: ignore[return-value]
            except (AttributeError, TypeError, ValueError):
                pass
            return fallback
        return CMeasurementResult(
            method="C",
            image_id=str(image_id),
            replica_id=replica_id,
            repetition=None if repetition is None else str(repetition),
            calibration_profile_id=profile_id,
            calibration_profile_hash=profile_hash,
            points_px=safe_points,
            q1_camera_mm={}, q2_camera_mm={}, v_air={}, v_glass={}, v_water={}, points_camera_mm={},
            longitudinal_axis_px=None,
            longitudinal_axis_camera=None,
            normal_axis_camera=None,
            maximum_depth_section_angle_degrees=None,
            measurement_plane_point_camera_mm=plane.point_camera_mm,
            measurement_plane_normal_camera=plane.normal_camera,
            port_normal_camera=safe_vector("port_normal", (0.0, 0.0, 1.0)),
            interface_distance_mm=safe_float("interface_distance_mm", 0.0),
            glass_thickness_mm=safe_float("glass_thickness_mm", 0.0),
            n_air=safe_float("n_air", 0.0),
            n_glass=safe_float("n_glass", 0.0),
            n_water=safe_float("n_water", 0.0),
            units="mm",
            total_length_mm=None,
            body_depth_mm=None,
            total_length_euclidean_mm=None,
            body_depth_euclidean_mm=None,
            body_depth_section_offset_mm=None,
            body_depth_section_angle_degrees=None,
            body_depth_valid=None,
            calibration_context_hash=context_hash,
            flat_port_hash=port_hash,
            measurement_plane_id=plane.plane_id,
            measurement_plane_hash=plane.plane_hash,
            quality=QualityReport(status="ERROR", warnings=(str(exc),)),
            exclusion_reason=str(exc), metadata={"excluded": True, "uses_aruco": False},
        )


calculate_c = measure_c


__all__ = ["calculate_c", "measure_c", "measure_c_safe"]
