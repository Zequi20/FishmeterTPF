"""Retroproyección pinhole efectiva e intersección general rayo–plano."""

from __future__ import annotations

from collections.abc import Mapping
import math

import cv2
import numpy as np

from ..domain.models import Point, Point3D
from ..measurements.quality import MeasurementError


class RayPlaneError(MeasurementError):
    """Geometría no finita, paralela o situada detrás de la cámara."""


def _vector3(value: object, label: str) -> np.ndarray:
    try:
        vector = np.asarray(value, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise RayPlaneError(f"{label} debe contener tres valores numéricos.") from exc
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise RayPlaneError(f"{label} debe ser un vector 3D finito.")
    return vector


def intersect_ray_plane(
    ray: object,
    plane_point_camera_mm: object,
    plane_normal_camera: object,
    *,
    parallel_epsilon: float = 1e-12,
) -> Point3D:
    """Interseca ``X(lambda)=lambda*ray`` con un plano en el marco de cámara."""

    direction = _vector3(ray, "El rayo")
    plane_point = _vector3(plane_point_camera_mm, "El punto del plano")
    normal = _vector3(plane_normal_camera, "La normal del plano")
    normal_norm = float(np.linalg.norm(normal))
    if normal_norm <= 0:
        raise RayPlaneError("La normal del plano no puede ser nula.")
    normal /= normal_norm
    epsilon = float(parallel_epsilon)
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise RayPlaneError("La tolerancia de paralelismo debe ser positiva y finita.")
    denominator = float(np.dot(normal, direction))
    if abs(denominator) <= epsilon:
        raise RayPlaneError("El rayo es paralelo o casi paralelo al plano de medición.")
    numerator = float(np.dot(normal, plane_point))
    scale = numerator / denominator
    if not math.isfinite(scale):
        raise RayPlaneError("La intersección rayo–plano no es finita.")
    if scale <= 0:
        raise RayPlaneError("La intersección con el plano queda detrás de la cámara.")
    point = scale * direction
    if not np.all(np.isfinite(point)):
        raise RayPlaneError("La intersección rayo–plano no es finita.")
    return (float(point[0]), float(point[1]), float(point[2]))


def intersect_ray_line_plane(
    ray_origin: object,
    ray_direction: object,
    plane_point_camera_mm: object,
    plane_normal_camera: object,
    *,
    parallel_epsilon: float = 1e-12,
) -> Point3D:
    """Interseca el rayo ``origin + lambda * direction`` con un plano."""

    origin = _vector3(ray_origin, "El origen del rayo")
    direction = _vector3(ray_direction, "La dirección del rayo")
    plane_point = _vector3(plane_point_camera_mm, "El punto del plano")
    normal = _vector3(plane_normal_camera, "La normal del plano")
    normal_norm = float(np.linalg.norm(normal))
    if normal_norm <= 0:
        raise RayPlaneError("La normal del plano no puede ser nula.")
    normal /= normal_norm
    denominator = float(np.dot(normal, direction))
    try:
        epsilon = float(parallel_epsilon)
    except (TypeError, ValueError) as exc:
        raise RayPlaneError("La tolerancia de paralelismo debe ser numérica.") from exc
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise RayPlaneError("La tolerancia de paralelismo debe ser positiva y finita.")
    if abs(denominator) <= epsilon:
        raise RayPlaneError("El rayo es paralelo o casi paralelo al plano de medición.")
    scale = float(np.dot(normal, plane_point - origin)) / denominator
    if not math.isfinite(scale):
        raise RayPlaneError("La intersección rayo–plano no es finita.")
    if scale < 0:
        raise RayPlaneError("La intersección con el plano queda detrás del origen del rayo.")
    point = origin + scale * direction
    if not np.all(np.isfinite(point)):
        raise RayPlaneError("La intersección rayo–plano no es finita.")
    return (float(point[0]), float(point[1]), float(point[2]))


def undistort_points_to_rays(
    points_px: Mapping[str, Point],
    camera_matrix: object,
    distortion_coefficients: object,
) -> dict[str, Point3D]:
    """Aplica ``cv2.undistortPoints(..., P=None)`` y forma rayos ``(x,y,1)``."""

    names = tuple(points_px)
    if not names:
        raise RayPlaneError("No hay puntos de imagen para retroproyectar.")
    try:
        pixels = np.asarray([points_px[name] for name in names], dtype=np.float64).reshape(-1, 1, 2)
        matrix = np.asarray(camera_matrix, dtype=np.float64)
        distortion = np.asarray(distortion_coefficients, dtype=np.float64).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise RayPlaneError("Los puntos, K_B o D_B no tienen formato numérico válido.") from exc
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise RayPlaneError("K_B debe ser una matriz 3×3 finita.")
    if not np.all(np.isfinite(pixels)) or not np.all(np.isfinite(distortion)):
        raise RayPlaneError("Los puntos de imagen y D_B deben ser finitos.")
    try:
        normalized = cv2.undistortPoints(
            pixels,
            matrix,
            None if distortion.size == 0 else distortion,
            P=None,
        ).reshape(-1, 2)
    except cv2.error as exc:
        raise RayPlaneError(f"OpenCV no pudo retroproyectar los puntos con K_B,D_B: {exc}") from exc
    if not np.all(np.isfinite(normalized)):
        raise RayPlaneError("La retroproyección produjo coordenadas no finitas.")
    return {
        name: (float(point[0]), float(point[1]), 1.0)
        for name, point in zip(names, normalized, strict=True)
    }


def intersect_image_points_with_plane(
    points_px: Mapping[str, Point],
    camera_matrix: object,
    distortion_coefficients: object,
    plane_point_camera_mm: object,
    plane_normal_camera: object,
    *,
    parallel_epsilon: float = 1e-12,
) -> dict[str, Point3D]:
    """Retroproyecta e interseca varios puntos conservando sus nombres."""

    rays = undistort_points_to_rays(points_px, camera_matrix, distortion_coefficients)
    return {
        name: intersect_ray_plane(
            ray,
            plane_point_camera_mm,
            plane_normal_camera,
            parallel_epsilon=parallel_epsilon,
        )
        for name, ray in rays.items()
    }


def image_axis_to_plane_direction(
    anchor_px: Point,
    axis_px: Point,
    camera_matrix: object,
    distortion_coefficients: object,
    plane_point_camera_mm: object,
    plane_normal_camera: object,
    *,
    probe_length_px: float = 100.0,
) -> Point3D:
    """Transforma una recta anatómica de imagen en una dirección del plano 3D."""

    try:
        axis = np.asarray(axis_px, dtype=np.float64).reshape(2)
        anchor = np.asarray(anchor_px, dtype=np.float64).reshape(2)
        probe = float(probe_length_px)
    except (TypeError, ValueError) as exc:
        raise RayPlaneError("El eje anatómico de imagen no tiene formato válido.") from exc
    norm = float(np.linalg.norm(axis))
    if not np.all(np.isfinite(axis)) or not np.all(np.isfinite(anchor)) or norm <= 0:
        raise RayPlaneError("El eje anatómico de imagen debe ser finito y no nulo.")
    if not math.isfinite(probe) or probe <= 0:
        raise RayPlaneError("La longitud de prueba del eje debe ser positiva y finita.")
    probe_point = anchor + axis / norm * probe
    points = intersect_image_points_with_plane(
        {"anchor": tuple(anchor), "probe": tuple(probe_point)},
        camera_matrix,
        distortion_coefficients,
        plane_point_camera_mm,
        plane_normal_camera,
    )
    direction = np.asarray(points["probe"]) - np.asarray(points["anchor"])
    direction_norm = float(np.linalg.norm(direction))
    if not np.all(np.isfinite(direction)) or direction_norm <= 0:
        raise RayPlaneError("El eje anatómico no pudo transformarse al plano métrico.")
    direction /= direction_norm
    return (float(direction[0]), float(direction[1]), float(direction[2]))


# Alias explícito para consumidores que nombran la operación "with plane".
intersect_ray_with_plane = intersect_ray_plane
intersect_ray_with_measurement_plane = intersect_ray_line_plane
undistort_points = undistort_points_to_rays


__all__ = [
    "RayPlaneError",
    "intersect_image_points_with_plane",
    "image_axis_to_plane_direction",
    "intersect_ray_plane",
    "intersect_ray_with_plane",
    "intersect_ray_with_measurement_plane",
    "intersect_ray_line_plane",
    "undistort_points",
    "undistort_points_to_rays",
]
