"""Referencia cámara–rail y construcción del plano de simetría de la réplica."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
import yaml

from ..calibration.b_calibration import BCalibrationProfile
from ..domain.models import Point, Point3D
from ..measurements.quality import MeasurementError


SCHEMA = "fish_morphometry.rail_plane_reference.v1"


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

    def __post_init__(self) -> None:
        validate_rail_reference(self)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "reference_id": self.reference_id,
            "reference_image_id": self.reference_image_id,
            "calibration_profile_hash": self.calibration_profile_hash,
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
    if _finite(reference.reprojection_error_px, "El error de solvePnP") < 0:
        raise RailGeometryError("El error de solvePnP no puede ser negativo.")


def _board_points(inner_corners: tuple[int, int], square_size_mm: float) -> np.ndarray:
    columns, rows = inner_corners
    points = np.zeros((columns * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points[:, :2] *= float(square_size_mm)
    return points


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
    normal = rotation @ np.array([0.0, 0.0, 1.0])
    normal_tuple = _unit_vector(normal, "La normal estimada")
    direction_tuple = _unit_vector(rail_direction_camera, "La dirección del rail")
    projected, _ = cv2.projectPoints(
        objects, rvec, tvec, profile.K, None if profile.D.size == 0 else profile.D
    )
    reprojection_error = float(
        np.linalg.norm(image_points.reshape(-1, 2) - projected.reshape(-1, 2))
        / math.sqrt(len(objects))
    )
    tvec_flat = np.asarray(tvec, dtype=float).reshape(3)
    rvec_flat = np.asarray(rvec, dtype=float).reshape(3)
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
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    try:
        found, corners = cv2.findChessboardCorners(
            gray,
            inner_corners,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
        )
    except cv2.error as exc:
        raise RailGeometryError(f"OpenCV no pudo detectar el tablero de referencia: {exc}") from exc
    if not found or corners is None:
        raise RailGeometryError("No se detectó completo el tablero en la fotografía de referencia.")
    termination = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
    refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), termination)
    return estimate_rail_reference_from_points(refined, profile, **kwargs)  # type: ignore[arg-type]


def build_measurement_plane(
    reference: RailPlaneReference,
    capture_rail_position_mm: float,
    replica_plane_offset_mm: float,
) -> tuple[Point3D, Point3D, float]:
    """Traslada el plano por el rail y devuelve ``(P0,n,delta_z_mm)``.

    El desplazamiento de la réplica es firmado: positivo sigue el sentido
    positivo documentado del rail.
    """

    validate_rail_reference(reference)
    if not reference.replica_planes_parallel_to_board:
        raise RailGeometryError(
            "La orientación del plano de la réplica es desconocida: no se confirmó que permanezca "
            "paralelo al tablero de referencia."
        )
    capture = _finite(capture_rail_position_mm, "La posición del carrito")
    offset = _finite(replica_plane_offset_mm, "El desplazamiento al plano de simetría")
    delta_z = capture - reference.z_ref_mm
    point = np.asarray(reference.plane_point_camera_mm, dtype=float) + np.asarray(
        reference.rail_direction_camera, dtype=float
    ) * (delta_z + offset)
    if not np.all(np.isfinite(point)):
        raise RailGeometryError("El plano de medición calculado no es finito.")
    return (
        (float(point[0]), float(point[1]), float(point[2])),
        _unit_vector(reference.plane_normal_camera, "La normal del plano"),
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
        return RailPlaneReference(
            reference_id=str(payload["reference_id"]),
            reference_image_id=str(payload["reference_image_id"]),
            calibration_profile_hash=str(payload["calibration_profile_hash"]),
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
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RailGeometryError(f"La referencia cámara–rail está incompleta: {exc}") from exc


build_plane_for_capture = build_measurement_plane
create_rail_reference_from_points = estimate_rail_reference_from_points
create_rail_reference_from_image = estimate_rail_reference_from_image


__all__ = [
    "RailGeometryError",
    "RailPlaneReference",
    "SCHEMA",
    "build_measurement_plane",
    "build_plane_for_capture",
    "create_rail_reference_from_image",
    "create_rail_reference_from_points",
    "estimate_rail_reference_from_image",
    "estimate_rail_reference_from_points",
    "load_rail_reference",
    "save_rail_reference",
    "validate_rail_reference",
]
