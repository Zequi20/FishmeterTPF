"""Referencia cámara–rail y construcción del plano de simetría de la réplica."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Sequence
import warnings

import cv2
import numpy as np
import yaml

from ..calibration.b_calibration import BCalibrationProfile
from ..domain.models import Point, Point3D
from ..measurements.quality import MeasurementError
from ..vision.chessboard_detector import ChessboardInputError, detect_chessboard_corners


SCHEMA = "fish_morphometry.rail_plane_reference.v1"
DEFAULT_RAIL_SCALE_RELATIVE_TOLERANCE = 0.05


class RailGeometryError(MeasurementError):
    """Falta o contradicción en la referencia métrica cámara–rail."""


def _finite(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise RailGeometryError(f"{label} debe ser numérico.") from exc
    if not math.isfinite(number):
        raise RailGeometryError(f"{label} debe ser finito.")
    return number


def _unit_vector(value: object, label: str) -> tuple[float, float, float]:
    try:
        vector = np.asarray(value, dtype=float).reshape(-1)
    except (TypeError, ValueError) as exc:
        raise RailGeometryError(f"{label} debe contener tres valores numéricos.") from exc
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise RailGeometryError(f"{label} debe ser un vector 3D finito.")
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise RailGeometryError(f"{label} no puede ser nulo.")
    vector /= norm
    return (float(vector[0]), float(vector[1]), float(vector[2]))


@dataclass(frozen=True)
class RailPlaneReference:
    """Plano del tablero de referencia y eje positivo del rail, en cámara."""

    reference_id: str
    reference_image_id: str
    calibration_profile_hash: str
    plane_point_camera_mm: Point3D
    plane_normal_camera: Point3D
    z_ref_mm: float
    rail_direction_camera: Point3D
    positive_direction: str
    rail_perpendicular_to_board: bool
    replica_planes_parallel_to_board: bool
    board_inner_corners: tuple[int, int]
    square_size_mm: float
    rvec: Point3D
    tvec_mm: Point3D
    reprojection_error_px: float
    created_at_utc: str
    direction_source: str = "manual"
    rail_positions_used_mm: tuple[float, ...] = ()
    rail_fit_residual_mm: float | None = None
    maximum_rail_fit_residual_mm: float = 1.0
    normal_spread_degrees: float | None = None
    maximum_normal_spread_degrees: float = 1.0
    maximum_reprojection_error_px: float = 1.0
    calibration_context_hash: str | None = None
    # ``rail_scale_norm`` is the norm of dtvec/drail estimated from the
    # multiposition observations.  It is deliberately retained as a
    # diagnostic instead of being silently forced to one.
    rail_scale_norm: float | None = None
    maximum_rail_scale_relative_error: float = DEFAULT_RAIL_SCALE_RELATIVE_TOLERANCE

    def __post_init__(self) -> None:
        validate_rail_reference(self)

    def _reference_hash_payload(self, *, include_scale_diagnostic: bool) -> dict[str, object]:
        payload = {
            "reference_id": self.reference_id,
            "reference_image_id": self.reference_image_id,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
            "plane_point_camera_mm": list(self.plane_point_camera_mm),
            "plane_normal_camera": list(self.plane_normal_camera),
            "z_ref_mm": self.z_ref_mm,
            "rail_direction_camera": list(self.rail_direction_camera),
            "positive_direction": self.positive_direction,
            "rail_perpendicular_to_board": self.rail_perpendicular_to_board,
            "replica_planes_parallel_to_board": self.replica_planes_parallel_to_board,
            "board_inner_corners": list(self.board_inner_corners),
            "square_size_mm": self.square_size_mm,
            "rvec": list(self.rvec),
            "tvec_mm": list(self.tvec_mm),
            "reprojection_error_px": self.reprojection_error_px,
            "direction_source": self.direction_source,
            "rail_positions_used_mm": list(self.rail_positions_used_mm),
            "rail_fit_residual_mm": self.rail_fit_residual_mm,
            "maximum_rail_fit_residual_mm": self.maximum_rail_fit_residual_mm,
            "normal_spread_degrees": self.normal_spread_degrees,
            "maximum_normal_spread_degrees": self.maximum_normal_spread_degrees,
            "maximum_reprojection_error_px": self.maximum_reprojection_error_px,
            "created_at_utc": self.created_at_utc,
        }
        if include_scale_diagnostic:
            payload["rail_scale_norm"] = self.rail_scale_norm
            payload[
                "maximum_rail_scale_relative_error"
            ] = self.maximum_rail_scale_relative_error
        return payload

    @property
    def reference_hash(self) -> str:
        """Identifica de forma reproducible la geometría que afecta las medidas."""

        payload = self._reference_hash_payload(include_scale_diagnostic=True)
        packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

    @property
    def legacy_reference_hash(self) -> str:
        """Hash v1 anterior al diagnóstico de escala, solo para cargar archivos existentes."""

        payload = self._reference_hash_payload(include_scale_diagnostic=False)
        packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

    @property
    def rail_scale_relative_error(self) -> float | None:
        """Error firmado de la escala pose/rail respecto de 1 mm/mm."""

        if self.rail_scale_norm is None:
            return None
        return float(self.rail_scale_norm - 1.0)

    @property
    def rail_scale_check_status(self) -> str:
        """Estado del diagnóstico de escala, sin declararlo validación física."""

        if self.rail_scale_norm is None:
            return "NOT_AVAILABLE"
        relative_error = self.rail_scale_relative_error
        assert relative_error is not None
        return (
            "PASS"
            if abs(relative_error) <= self.maximum_rail_scale_relative_error
            else "WARNING"
        )

    @property
    def is_provisional(self) -> bool:
        """Indica que la referencia aún requiere validación métrica física."""

        return True

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "reference_id": self.reference_id,
            "reference_hash": self.reference_hash,
            "metric_validation_status": "PENDING_VALIDATION",
            "reference_image_id": self.reference_image_id,
            "calibration_profile_hash": self.calibration_profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
            "plane_point_camera_mm": list(self.plane_point_camera_mm),
            "plane_normal_camera": list(self.plane_normal_camera),
            "z_ref_mm": self.z_ref_mm,
            "rail_direction_camera": list(self.rail_direction_camera),
            "positive_direction": self.positive_direction,
            "assumptions": {
                "rail_perpendicular_to_board": self.rail_perpendicular_to_board,
                "replica_planes_parallel_to_board": self.replica_planes_parallel_to_board,
            },
            "board": {
                "inner_corners": list(self.board_inner_corners),
                "square_size_mm": self.square_size_mm,
            },
            "solve_pnp": {
                "rvec": list(self.rvec),
                "tvec_mm": list(self.tvec_mm),
                "reprojection_error_px": self.reprojection_error_px,
                "maximum_reprojection_error_px": self.maximum_reprojection_error_px,
            },
            "rail_fit": {
                "direction_source": self.direction_source,
                "positions_used_mm": list(self.rail_positions_used_mm),
                "residual_mm": self.rail_fit_residual_mm,
                "maximum_residual_mm": self.maximum_rail_fit_residual_mm,
                "normal_spread_degrees": self.normal_spread_degrees,
                "maximum_normal_spread_degrees": self.maximum_normal_spread_degrees,
                "scale_norm": self.rail_scale_norm,
                "scale_relative_error": self.rail_scale_relative_error,
                "maximum_scale_relative_error": self.maximum_rail_scale_relative_error,
                "scale_check_status": self.rail_scale_check_status,
            },
            "created_at_utc": self.created_at_utc,
        }


def validate_rail_reference(reference: RailPlaneReference) -> None:
    if not str(reference.reference_id).strip():
        raise RailGeometryError("La referencia cámara–rail debe tener un ID.")
    if not str(reference.reference_image_id).strip():
        raise RailGeometryError("Debe identificarse la fotografía específica de referencia.")
    if not str(reference.calibration_profile_hash).strip():
        raise RailGeometryError("La referencia debe enlazar el hash de un perfil B.")
    if reference.calibration_context_hash is not None and not str(
        reference.calibration_context_hash
    ).strip():
        raise RailGeometryError("El hash del contexto de calibración no puede estar vacío.")
    point = np.asarray(reference.plane_point_camera_mm, dtype=float)
    if point.shape != (3,) or not np.all(np.isfinite(point)):
        raise RailGeometryError("El punto del plano de referencia debe ser 3D y finito.")
    if point[2] <= 0:
        raise RailGeometryError("El tablero de referencia debe quedar delante de la cámara.")
    normal = np.asarray(_unit_vector(reference.plane_normal_camera, "La normal del plano"))
    direction = np.asarray(_unit_vector(reference.rail_direction_camera, "La dirección del rail"))
    if not str(reference.positive_direction).strip():
        raise RailGeometryError("Debe documentarse el sentido positivo del rail.")
    if reference.rail_perpendicular_to_board:
        if not math.isclose(abs(float(np.dot(normal, direction))), 1.0, abs_tol=1e-3):
            raise RailGeometryError(
                "Se declaró el rail perpendicular al tablero, pero su dirección no es paralela a la normal."
            )
    if len(reference.board_inner_corners) != 2 or any(
        int(value) < 2 for value in reference.board_inner_corners
    ):
        raise RailGeometryError("El tablero de referencia debe tener al menos 2×2 esquinas internas.")
    if _finite(reference.square_size_mm, "El tamaño del cuadro") <= 0:
        raise RailGeometryError("El tamaño del cuadro debe ser positivo.")
    _finite(reference.z_ref_mm, "z_ref_mm")
    reprojection_error = _finite(reference.reprojection_error_px, "El error de solvePnP")
    maximum_reprojection = _finite(
        reference.maximum_reprojection_error_px, "El máximo error de solvePnP"
    )
    if reprojection_error < 0:
        raise RailGeometryError("El error de solvePnP no puede ser negativo.")
    if maximum_reprojection <= 0:
        raise RailGeometryError("El máximo error de solvePnP debe ser positivo.")
    if reprojection_error > maximum_reprojection:
        raise RailGeometryError(
            f"El error de solvePnP ({reprojection_error:.3f} px) supera el máximo "
            f"configurado ({maximum_reprojection:.3f} px)."
        )
    if reference.direction_source not in {"manual", "multi_position_fit"}:
        raise RailGeometryError("La procedencia de la dirección del rail no es válida.")
    maximum_fit = _finite(
        reference.maximum_rail_fit_residual_mm, "El máximo residuo del ajuste del rail"
    )
    maximum_spread = _finite(
        reference.maximum_normal_spread_degrees, "La máxima dispersión angular de normales"
    )
    if maximum_fit <= 0 or maximum_spread <= 0 or maximum_spread >= 90:
        raise RailGeometryError("Los umbrales del ajuste del rail no son válidos.")
    maximum_scale_error = _finite(
        reference.maximum_rail_scale_relative_error,
        "La tolerancia relativa de escala del rail",
    )
    if maximum_scale_error < 0 or maximum_scale_error >= 1:
        raise RailGeometryError(
            "La tolerancia relativa de escala del rail debe estar entre 0 y 1."
        )
    if reference.rail_scale_norm is not None:
        scale_norm = _finite(reference.rail_scale_norm, "La norma de escala pose/rail")
        if scale_norm <= 0:
            raise RailGeometryError("La norma de escala pose/rail debe ser positiva.")
    if reference.direction_source == "multi_position_fit":
        if len(reference.rail_positions_used_mm) < 2:
            raise RailGeometryError("El ajuste del rail requiere al menos dos posiciones.")
        positions = tuple(
            _finite(value, "Una posición usada para ajustar el rail")
            for value in reference.rail_positions_used_mm
        )
        if len(set(positions)) < 2:
            raise RailGeometryError("El ajuste del rail requiere posiciones distintas.")
        if reference.rail_fit_residual_mm is None or reference.normal_spread_degrees is None:
            raise RailGeometryError("Faltan diagnósticos del ajuste multiposición del rail.")
        fit_residual = _finite(reference.rail_fit_residual_mm, "El residuo del ajuste del rail")
        normal_spread = _finite(reference.normal_spread_degrees, "La dispersión de normales")
        if fit_residual < 0 or fit_residual > maximum_fit:
            raise RailGeometryError(
                f"El residuo del rail ({fit_residual:.3f} mm) supera el máximo "
                f"({maximum_fit:.3f} mm)."
            )
        if normal_spread < 0 or normal_spread > maximum_spread:
            raise RailGeometryError(
                f"La dispersión de normales ({normal_spread:.3f}°) supera el máximo "
                f"({maximum_spread:.3f}°)."
            )


def _board_points(inner_corners: tuple[int, int], square_size_mm: float) -> np.ndarray:
    columns, rows = inner_corners
    points = np.zeros((columns * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points[:, :2] *= float(square_size_mm)
    return points


def _solve_board_pose(
    image_points_px: Sequence[Point] | np.ndarray,
    profile: BCalibrationProfile,
    objects: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Resuelve una pose de tablero y devuelve rvec, tvec, normal y error."""

    try:
        image_points = np.asarray(image_points_px, dtype=np.float64).reshape(-1, 1, 2)
    except (TypeError, ValueError) as exc:
        raise RailGeometryError("Las esquinas de referencia no tienen formato válido.") from exc
    if len(image_points) != len(objects) or not np.all(np.isfinite(image_points)):
        raise RailGeometryError(
            f"Se requieren exactamente {len(objects)} esquinas finitas para la referencia."
        )
    try:
        success, rvec, tvec = cv2.solvePnP(
            objects,
            image_points,
            profile.K,
            None if profile.D.size == 0 else profile.D,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
    except cv2.error as exc:
        raise RailGeometryError(f"OpenCV no pudo estimar la pose de referencia: {exc}") from exc
    if not success:
        raise RailGeometryError("solvePnP no encontró una pose válida para la referencia.")
    rotation, _ = cv2.Rodrigues(rvec)
    normal = np.asarray(_unit_vector(
        rotation @ np.array([0.0, 0.0, 1.0]), "La normal estimada"
    ))
    projected, _ = cv2.projectPoints(
        objects, rvec, tvec, profile.K, None if profile.D.size == 0 else profile.D
    )
    reprojection_error = float(
        np.linalg.norm(image_points.reshape(-1, 2) - projected.reshape(-1, 2))
        / math.sqrt(len(objects))
    )
    return (
        np.asarray(rvec, dtype=float).reshape(3),
        np.asarray(tvec, dtype=float).reshape(3),
        normal,
        reprojection_error,
    )


def estimate_rail_reference_from_points(
    image_points_px: Sequence[Point] | np.ndarray,
    profile: BCalibrationProfile,
    *,
    inner_corners: tuple[int, int],
    square_size_mm: float,
    z_ref_mm: float,
    rail_direction_camera: Sequence[float],
    positive_direction: str,
    reference_image_id: str,
    reference_id: str = "rail-reference",
    rail_perpendicular_to_board: bool,
    replica_planes_parallel_to_board: bool,
    maximum_reprojection_error_px: float = 1.0,
) -> RailPlaneReference:
    """Estima el plano del tablero con solvePnP a partir de esquinas refinadas."""

    columns, rows = int(inner_corners[0]), int(inner_corners[1])
    square = _finite(square_size_mm, "El tamaño físico del cuadro")
    rail_position = _finite(z_ref_mm, "z_ref_mm")
    if not math.isclose(
        rail_position, profile.calibration_rail_position_mm, rel_tol=0.0, abs_tol=1e-6
    ):
        raise RailGeometryError(
            "z_ref_mm debe coincidir con la posición de calibración B (zona más cercana al vidrio)."
        )
    objects = _board_points((columns, rows), square)
    rvec_flat, tvec_flat, normal, reprojection_error = _solve_board_pose(
        image_points_px, profile, objects
    )
    normal_tuple = tuple(float(value) for value in normal)
    direction_tuple = _unit_vector(rail_direction_camera, "La dirección del rail")
    return RailPlaneReference(
        reference_id=str(reference_id),
        reference_image_id=str(reference_image_id),
        calibration_profile_hash=profile.profile_hash,
        plane_point_camera_mm=tuple(float(value) for value in tvec_flat),
        plane_normal_camera=normal_tuple,
        z_ref_mm=rail_position,
        rail_direction_camera=direction_tuple,
        positive_direction=str(positive_direction),
        rail_perpendicular_to_board=bool(rail_perpendicular_to_board),
        replica_planes_parallel_to_board=bool(replica_planes_parallel_to_board),
        board_inner_corners=(columns, rows),
        square_size_mm=square,
        rvec=tuple(float(value) for value in rvec_flat),
        tvec_mm=tuple(float(value) for value in tvec_flat),
        reprojection_error_px=reprojection_error,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        maximum_reprojection_error_px=float(maximum_reprojection_error_px),
        calibration_context_hash=profile.calibration_context_hash,
        rail_scale_norm=None,
    )


def estimate_rail_reference_from_observations(
    observations: Sequence[tuple[float, Sequence[Point] | np.ndarray, str]],
    profile: BCalibrationProfile,
    *,
    inner_corners: tuple[int, int],
    square_size_mm: float,
    z_ref_mm: float,
    reference_id: str = "rail-reference",
    positive_direction: str = "posición de rail creciente",
    rail_perpendicular_to_board: bool,
    replica_planes_parallel_to_board: bool,
    maximum_reprojection_error_px: float = 1.0,
    maximum_rail_fit_residual_mm: float = 1.0,
    maximum_normal_spread_degrees: float = 1.0,
    maximum_rail_scale_relative_error: float = DEFAULT_RAIL_SCALE_RELATIVE_TOLERANCE,
) -> RailPlaneReference:
    """Ajusta dirección y plano del rail desde dos o más posiciones conocidas."""

    if len(observations) < 2:
        raise RailGeometryError("Se requieren al menos dos observaciones del rail.")
    rail_position = _finite(z_ref_mm, "z_ref_mm")
    if not math.isclose(
        rail_position, profile.calibration_rail_position_mm, rel_tol=0.0, abs_tol=1e-6
    ):
        raise RailGeometryError("z_ref_mm debe coincidir con la posición de calibración B.")
    columns, rows = int(inner_corners[0]), int(inner_corners[1])
    square = _finite(square_size_mm, "El tamaño físico del cuadro")
    if columns < 2 or rows < 2 or square <= 0:
        raise RailGeometryError("La geometría del tablero de referencia no es válida.")
    max_reprojection = _finite(
        maximum_reprojection_error_px, "El máximo error de solvePnP"
    )
    max_fit = _finite(maximum_rail_fit_residual_mm, "El máximo residuo del rail")
    max_spread = _finite(
        maximum_normal_spread_degrees, "La máxima dispersión de normales"
    )
    max_scale_error = _finite(
        maximum_rail_scale_relative_error,
        "La tolerancia relativa de escala del rail",
    )
    if (
        max_reprojection <= 0
        or max_fit <= 0
        or max_spread <= 0
        or max_spread >= 90
        or max_scale_error < 0
        or max_scale_error >= 1
    ):
        raise RailGeometryError("Los umbrales de referencia cámara–rail no son válidos.")

    objects = _board_points((columns, rows), square)
    positions: list[float] = []
    image_ids: list[str] = []
    rvecs: list[np.ndarray] = []
    points: list[np.ndarray] = []
    normals: list[np.ndarray] = []
    errors: list[float] = []
    for position_raw, image_points, image_id in observations:
        position = _finite(position_raw, "Una posición del rail")
        if not str(image_id).strip():
            raise RailGeometryError("Cada observación del rail debe identificar su imagen.")
        rvec, point, normal, error = _solve_board_pose(image_points, profile, objects)
        if error > max_reprojection:
            raise RailGeometryError(
                f"La referencia {image_id} tiene error {error:.3f} px; "
                f"supera {max_reprojection:.3f} px."
            )
        positions.append(position)
        image_ids.append(str(image_id))
        rvecs.append(rvec)
        points.append(point)
        normals.append(normal)
        errors.append(error)
    if len(set(positions)) < 2:
        raise RailGeometryError("Las observaciones deben usar posiciones de rail distintas.")
    if not min(positions) <= rail_position <= max(positions):
        raise RailGeometryError("Las posiciones observadas deben abarcar z_ref_mm.")

    deltas = np.asarray(positions, dtype=float) - rail_position
    design = np.column_stack((np.ones(len(deltas)), deltas))
    coefficients, *_ = np.linalg.lstsq(design, np.asarray(points), rcond=None)
    point_at_reference = coefficients[0]
    direction_raw = coefficients[1]
    direction_norm = float(np.linalg.norm(direction_raw))
    if not math.isfinite(direction_norm) or direction_norm <= 0:
        raise RailGeometryError("No se pudo estimar una dirección de rail no nula.")
    direction = direction_raw / direction_norm
    predicted = design @ coefficients
    fit_residual = float(
        np.sqrt(np.mean(np.sum((np.asarray(points) - predicted) ** 2, axis=1)))
    )

    aligned_normals = [normals[0]]
    for normal in normals[1:]:
        aligned_normals.append(normal if np.dot(normal, normals[0]) >= 0 else -normal)
    average_normal = np.mean(aligned_normals, axis=0)
    average_normal /= np.linalg.norm(average_normal)
    normal_spread = max(
        math.degrees(math.acos(float(np.clip(np.dot(normal, average_normal), -1.0, 1.0))))
        for normal in aligned_normals
    )
    if fit_residual > max_fit:
        raise RailGeometryError(
            f"El residuo del ajuste del rail ({fit_residual:.3f} mm) supera "
            f"{max_fit:.3f} mm."
        )
    if normal_spread > max_spread:
        raise RailGeometryError(
            f"La dispersión angular ({normal_spread:.3f}°) supera {max_spread:.3f}°."
        )
    nearest = int(np.argmin(np.abs(deltas)))
    return RailPlaneReference(
        reference_id=str(reference_id),
        reference_image_id=" | ".join(image_ids),
        calibration_profile_hash=profile.profile_hash,
        plane_point_camera_mm=tuple(float(value) for value in point_at_reference),
        plane_normal_camera=tuple(float(value) for value in average_normal),
        z_ref_mm=rail_position,
        rail_direction_camera=tuple(float(value) for value in direction),
        positive_direction=str(positive_direction),
        rail_perpendicular_to_board=bool(rail_perpendicular_to_board),
        replica_planes_parallel_to_board=bool(replica_planes_parallel_to_board),
        board_inner_corners=(columns, rows),
        square_size_mm=square,
        rvec=tuple(float(value) for value in rvecs[nearest]),
        tvec_mm=tuple(float(value) for value in point_at_reference),
        reprojection_error_px=max(errors),
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        direction_source="multi_position_fit",
        rail_positions_used_mm=tuple(positions),
        rail_fit_residual_mm=fit_residual,
        maximum_rail_fit_residual_mm=max_fit,
        normal_spread_degrees=normal_spread,
        maximum_normal_spread_degrees=max_spread,
        maximum_reprojection_error_px=max_reprojection,
        calibration_context_hash=profile.calibration_context_hash,
        rail_scale_norm=direction_norm,
        maximum_rail_scale_relative_error=max_scale_error,
    )


def estimate_rail_reference_from_image(
    image_bgr: np.ndarray,
    profile: BCalibrationProfile,
    **kwargs: object,
) -> RailPlaneReference:
    """Detecta/refina el tablero de una captura identificada y ejecuta solvePnP."""

    if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.ndim < 2:
        raise RailGeometryError("La fotografía de referencia es ilegible.")
    height, width = image_bgr.shape[:2]
    if (width, height) != profile.resolution:
        raise RailGeometryError(
            f"Resolución incompatible: referencia {width}×{height}; perfil B "
            f"{profile.resolution[0]}×{profile.resolution[1]}."
        )
    inner_corners_raw = kwargs.get("inner_corners")
    if not isinstance(inner_corners_raw, (tuple, list)) or len(inner_corners_raw) != 2:
        raise RailGeometryError("Debe indicar inner_corners=(columnas, filas).")
    inner_corners = (int(inner_corners_raw[0]), int(inner_corners_raw[1]))
    _warn_square_board_orientation_ambiguity(inner_corners)
    try:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
        detection = detect_chessboard_corners(gray, inner_corners)
    except (cv2.error, ChessboardInputError) as exc:
        raise RailGeometryError(f"La imagen de referencia no es válida para detectar el damero: {exc}") from exc
    if not detection.found or detection.corners is None:
        raise RailGeometryError(
            "No se detectó completo el tablero en la fotografía de referencia; "
            f"{detection.diagnostic_summary}"
        )
    return estimate_rail_reference_from_points(detection.corners, profile, **kwargs)  # type: ignore[arg-type]


def estimate_rail_reference_from_images(
    observations: Sequence[tuple[float, np.ndarray, str]],
    profile: BCalibrationProfile,
    **kwargs: object,
) -> RailPlaneReference:
    """Detecta el tablero en varias posiciones y ajusta la geometría del rail."""

    inner_corners_raw = kwargs.get("inner_corners")
    if not isinstance(inner_corners_raw, (tuple, list)) or len(inner_corners_raw) != 2:
        raise RailGeometryError("Debe indicar inner_corners=(columnas, filas).")
    inner_corners = (int(inner_corners_raw[0]), int(inner_corners_raw[1]))
    _warn_square_board_orientation_ambiguity(inner_corners)
    point_observations: list[tuple[float, np.ndarray, str]] = []
    for position, image_bgr, image_id in observations:
        if image_bgr is None or not isinstance(image_bgr, np.ndarray) or image_bgr.ndim < 2:
            raise RailGeometryError(f"La fotografía de referencia {image_id} es ilegible.")
        height, width = image_bgr.shape[:2]
        if (width, height) != profile.resolution:
            raise RailGeometryError(
                f"Resolución incompatible en {image_id}: {width}×{height}; perfil B "
                f"{profile.resolution[0]}×{profile.resolution[1]}."
            )
        try:
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
            detection = detect_chessboard_corners(gray, inner_corners)
        except (cv2.error, ChessboardInputError) as exc:
            raise RailGeometryError(
                f"La imagen de referencia {image_id} no es válida para detectar el damero: {exc}"
            ) from exc
        if not detection.found or detection.corners is None:
            raise RailGeometryError(
                f"No se detectó completo el tablero en {image_id}; "
                f"{detection.diagnostic_summary}"
            )
        point_observations.append((float(position), detection.corners, str(image_id)))
    return estimate_rail_reference_from_observations(
        point_observations, profile, **kwargs  # type: ignore[arg-type]
    )


def _warn_square_board_orientation_ambiguity(inner_corners: tuple[int, int]) -> None:
    """Advierte que un damero cuadrado no fija por sí solo su origen/orientación."""

    if int(inner_corners[0]) == int(inner_corners[1]):
        warnings.warn(
            "El damero cuadrado no desambigua el origen ni la orientación entre "
            "fotografías del rail. Verifique una orientación física consistente o "
            "use una referencia asimétrica; Fishmeter no invierte coordenadas "
            "automáticamente.",
            UserWarning,
            stacklevel=2,
        )


def build_measurement_plane(
    reference: RailPlaneReference,
    capture_rail_position_mm: float,
    replica_plane_offset_mm: float,
    *,
    replica_plane_offset_direction: str = "rail",
) -> tuple[Point3D, Point3D, float]:
    """Traslada el plano por el rail y devuelve ``(P0,n,delta_z_mm)``.

    El desplazamiento de la réplica es firmado. Con ``rail`` sigue el sentido
    positivo documentado del rail; con ``plane_normal`` sigue la normal guardada.
    """

    validate_rail_reference(reference)
    if not reference.replica_planes_parallel_to_board:
        raise RailGeometryError(
            "La orientación del plano de la réplica es desconocida: no se confirmó que permanezca "
            "paralelo al tablero de referencia."
        )
    capture = _finite(capture_rail_position_mm, "La posición del carrito")
    offset = _finite(replica_plane_offset_mm, "El desplazamiento al plano de simetría")
    offset_direction = str(replica_plane_offset_direction).strip().lower()
    if offset_direction not in {"rail", "plane_normal"}:
        raise RailGeometryError(
            "La dirección del offset debe ser 'rail' o 'plane_normal'."
        )
    delta_z = capture - reference.z_ref_mm
    rail_direction = np.asarray(reference.rail_direction_camera, dtype=float)
    plane_normal = np.asarray(
        _unit_vector(reference.plane_normal_camera, "La normal del plano"), dtype=float
    )
    offset_axis = rail_direction if offset_direction == "rail" else plane_normal
    point = (
        np.asarray(reference.plane_point_camera_mm, dtype=float)
        + rail_direction * delta_z
        + offset_axis * offset
    )
    if not np.all(np.isfinite(point)):
        raise RailGeometryError("El plano de medición calculado no es finito.")
    return (
        (float(point[0]), float(point[1]), float(point[2])),
        tuple(float(value) for value in plane_normal),
        float(delta_z),
    )


def save_rail_reference(reference: RailPlaneReference, path: str | Path) -> Path:
    validate_rail_reference(reference)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(reference.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return output_path


def load_rail_reference(path: str | Path) -> RailPlaneReference:
    input_path = Path(path)
    try:
        payload = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RailGeometryError(f"No se pudo leer la referencia cámara–rail: {input_path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise RailGeometryError("El archivo no usa el esquema rail_plane_reference.v1.")
    try:
        assumptions = payload["assumptions"]
        board = payload["board"]
        pose = payload["solve_pnp"]
        rail_fit = payload.get("rail_fit") or {}
        reference = RailPlaneReference(
            reference_id=str(payload["reference_id"]),
            reference_image_id=str(payload["reference_image_id"]),
            calibration_profile_hash=str(payload["calibration_profile_hash"]),
            calibration_context_hash=(
                None
                if payload.get("calibration_context_hash") is None
                else str(payload["calibration_context_hash"])
            ),
            plane_point_camera_mm=tuple(float(v) for v in payload["plane_point_camera_mm"]),
            plane_normal_camera=tuple(float(v) for v in payload["plane_normal_camera"]),
            z_ref_mm=float(payload["z_ref_mm"]),
            rail_direction_camera=tuple(float(v) for v in payload["rail_direction_camera"]),
            positive_direction=str(payload["positive_direction"]),
            rail_perpendicular_to_board=bool(assumptions["rail_perpendicular_to_board"]),
            replica_planes_parallel_to_board=bool(assumptions["replica_planes_parallel_to_board"]),
            board_inner_corners=tuple(int(v) for v in board["inner_corners"]),
            square_size_mm=float(board["square_size_mm"]),
            rvec=tuple(float(v) for v in pose["rvec"]),
            tvec_mm=tuple(float(v) for v in pose["tvec_mm"]),
            reprojection_error_px=float(pose["reprojection_error_px"]),
            created_at_utc=str(payload["created_at_utc"]),
            direction_source=str(rail_fit.get("direction_source", "manual")),
            rail_positions_used_mm=tuple(
                float(value) for value in rail_fit.get("positions_used_mm", ())
            ),
            rail_fit_residual_mm=(
                None if rail_fit.get("residual_mm") is None else float(rail_fit["residual_mm"])
            ),
            maximum_rail_fit_residual_mm=float(rail_fit.get("maximum_residual_mm", 1.0)),
            normal_spread_degrees=(
                None
                if rail_fit.get("normal_spread_degrees") is None
                else float(rail_fit["normal_spread_degrees"])
            ),
            maximum_normal_spread_degrees=float(
                rail_fit.get("maximum_normal_spread_degrees", 1.0)
            ),
            maximum_reprojection_error_px=float(
                pose.get("maximum_reprojection_error_px", 1.0)
            ),
            rail_scale_norm=(
                None
                if rail_fit.get("scale_norm") is None
                else float(rail_fit["scale_norm"])
            ),
            maximum_rail_scale_relative_error=float(
                rail_fit.get(
                    "maximum_scale_relative_error",
                    DEFAULT_RAIL_SCALE_RELATIVE_TOLERANCE,
                )
            ),
        )
        stored_hash = payload.get("reference_hash")
        if stored_hash is not None:
            accepted_hashes = {reference.reference_hash}
            if "scale_norm" not in rail_fit:
                accepted_hashes.add(reference.legacy_reference_hash)
            if str(stored_hash) not in accepted_hashes:
                raise RailGeometryError("El hash de la referencia cámara–rail no coincide.")
        return reference
    except RailGeometryError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise RailGeometryError(f"La referencia cámara–rail está incompleta: {exc}") from exc


build_plane_for_capture = build_measurement_plane
create_rail_reference_from_points = estimate_rail_reference_from_points
create_rail_reference_from_image = estimate_rail_reference_from_image


__all__ = [
    "DEFAULT_RAIL_SCALE_RELATIVE_TOLERANCE",
    "RailGeometryError",
    "RailPlaneReference",
    "SCHEMA",
    "build_measurement_plane",
    "build_plane_for_capture",
    "create_rail_reference_from_image",
    "create_rail_reference_from_points",
    "estimate_rail_reference_from_image",
    "estimate_rail_reference_from_images",
    "estimate_rail_reference_from_observations",
    "estimate_rail_reference_from_points",
    "load_rail_reference",
    "save_rail_reference",
    "validate_rail_reference",
]
