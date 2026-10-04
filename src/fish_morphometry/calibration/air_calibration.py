"""Calibración convencional de la cámara en aire para el método C."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import cv2
import numpy as np
import yaml

from .b_calibration import SUPPORTED_PINHOLE_MODELS


SCHEMA = "fish_morphometry.air_calibration.v1"
UNIT_TO_MM = {"mm": 1.0, "millimeter": 1.0, "millimeters": 1.0, "cm": 10.0, "m": 1000.0}


class AirCalibrationError(ValueError):
    """Error de adquisición, ajuste o formato de calibración en aire."""

    def __init__(self, message: str, *, reports: Sequence["AirCalibrationViewReport"] = ()):
        super().__init__(message)
        self.reports = tuple(reports)


@dataclass(frozen=True)
class AirCalibrationViewReport:
    image_id: str
    accepted: bool
    rejection_reason: str | None = None
    reprojection_error_px: float | None = None
    rvec: tuple[float, float, float] | None = None
    tvec_mm: tuple[float, float, float] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
            "reprojection_error_px": self.reprojection_error_px,
            "rvec": None if self.rvec is None else list(self.rvec),
            "tvec_mm": None if self.tvec_mm is None else list(self.tvec_mm),
        }


@dataclass(frozen=True)
class AirCalibrationProfile:
    profile_id: str
    profile_hash: str
    model: str
    camera_matrix: tuple[tuple[float, float, float], ...]
    distortion_coefficients: tuple[float, ...]
    resolution: tuple[int, int]
    board_inner_corners: tuple[int, int] | None
    square_size_mm: float | None
    units: str
    rms_px: float | None
    created_at_utc: str
    opencv_version: str
    app_version: str
    source: str
    views_received: int = 0
    views_accepted: int = 0
    views_rejected: int = 0
    view_reports: tuple[AirCalibrationViewReport, ...] = ()
    source_metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        validate_air_profile(self)

    @property
    def K(self) -> np.ndarray:
        return np.asarray(self.camera_matrix, dtype=np.float64)

    @property
    def D(self) -> np.ndarray:
        return np.asarray(self.distortion_coefficients, dtype=np.float64)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "profile_id": self.profile_id,
            "profile_hash": self.profile_hash,
            "model": self.model,
            "camera_matrix": [list(row) for row in self.camera_matrix],
            "distortion_coefficients": list(self.distortion_coefficients),
            "resolution": list(self.resolution),
            "board": (
                None
                if self.board_inner_corners is None
                else {
                    "inner_corners": list(self.board_inner_corners),
                    "square_size_mm": self.square_size_mm,
                    "units": self.units,
                }
            ),
            "rms_px": self.rms_px,
            "created_at_utc": self.created_at_utc,
            "versions": {"opencv": self.opencv_version, "fish_morphometry": self.app_version},
            "source": self.source,
            "views": {
                "received": self.views_received,
                "accepted": self.views_accepted,
                "rejected": self.views_rejected,
                "reports": [report.to_dict() for report in self.view_reports],
            },
            "source_metadata": self.source_metadata or {},
            "limitations": [
                "K_air y D_air describen la cámara calibrada en aire.",
                "No sustituyen los parámetros físicos del puerto plano.",
            ],
        }


def _finite(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AirCalibrationError(f"{label} debe ser numérico.") from exc
    if not math.isfinite(number):
        raise AirCalibrationError(f"{label} debe ser finito.")
    return number


def unit_scale_to_mm(units: str) -> float:
    key = str(units).strip().lower()
    if key not in UNIT_TO_MM:
        raise AirCalibrationError(
            f"Unidad no soportada o ambigua: {units!r}. Declare mm, cm o m explícitamente."
        )
    return UNIT_TO_MM[key]


def _hash_payload(model: str, matrix: Sequence[Sequence[float]], distortion: Sequence[float], resolution: Sequence[int]) -> str:
    payload = {
        "model": str(model).upper(),
        "camera_matrix": [[float(v) for v in row] for row in matrix],
        "distortion_coefficients": [float(v) for v in distortion],
        "resolution": [int(resolution[0]), int(resolution[1])],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_air_profile(profile: AirCalibrationProfile) -> None:
    if not str(profile.profile_id).strip():
        raise AirCalibrationError("El perfil de aire debe tener un ID no vacío.")
    model = str(profile.model).strip().upper().replace("-", "_").replace(" ", "_")
    if model not in SUPPORTED_PINHOLE_MODELS:
        raise AirCalibrationError(f"Modelo de cámara no compatible con C/OpenCV: {profile.model}.")
    matrix = np.asarray(profile.camera_matrix, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise AirCalibrationError("K_air debe ser una matriz 3×3 finita.")
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0 or not np.allclose(matrix[2], (0, 0, 1), atol=1e-9):
        raise AirCalibrationError("K_air tiene focales o última fila inválidas.")
    distortion = np.asarray(profile.distortion_coefficients, dtype=float).reshape(-1)
    if len(distortion) not in (0, 4, 5, 8, 12, 14) or not np.all(np.isfinite(distortion)):
        raise AirCalibrationError("D_air no tiene una longitud compatible con OpenCV.")
    if len(profile.resolution) != 2 or any(int(v) <= 0 for v in profile.resolution):
        raise AirCalibrationError("La resolución de calibración en aire es inválida.")
    unit_scale_to_mm(profile.units)
    if profile.board_inner_corners is not None and (
        len(profile.board_inner_corners) != 2 or any(int(v) < 2 for v in profile.board_inner_corners)
    ):
        raise AirCalibrationError("Las esquinas internas del tablero son inválidas.")
    if profile.square_size_mm is not None and _finite(profile.square_size_mm, "El cuadro") <= 0:
        raise AirCalibrationError("El tamaño del cuadro debe ser positivo.")
    if profile.rms_px is not None and _finite(profile.rms_px, "El RMS") < 0:
        raise AirCalibrationError("El RMS no puede ser negativo.")
    if profile.profile_hash != _hash_payload(profile.model, profile.camera_matrix, profile.distortion_coefficients, profile.resolution):
        raise AirCalibrationError("El hash del perfil de aire no coincide con sus parámetros.")
    if profile.views_received != profile.views_accepted + profile.views_rejected:
        raise AirCalibrationError("El conteo de vistas del perfil de aire es inconsistente.")


def make_air_calibration_profile(
    *,
    profile_id: str,
    model: str,
    camera_matrix: Sequence[Sequence[float]],
    distortion_coefficients: Sequence[float],
    resolution: Sequence[int],
    board_inner_corners: Sequence[int] | None,
    square_size_mm: float | None,
    units: str,
    rms_px: float | None,
    source: str,
    view_reports: Sequence[AirCalibrationViewReport] = (),
    source_metadata: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> AirCalibrationProfile:
    from .. import __version__

    scale = unit_scale_to_mm(units)
    reports = tuple(view_reports)
    matrix = tuple(tuple(float(v) for v in row) for row in camera_matrix)
    distortion = tuple(float(v) for v in distortion_coefficients)
    image_resolution = (int(resolution[0]), int(resolution[1]))
    return AirCalibrationProfile(
        profile_id=str(profile_id).strip(),
        profile_hash=_hash_payload(model, matrix, distortion, image_resolution),
        model=str(model).upper(),
        camera_matrix=matrix,
        distortion_coefficients=distortion,
        resolution=image_resolution,
        board_inner_corners=None if board_inner_corners is None else (int(board_inner_corners[0]), int(board_inner_corners[1])),
        square_size_mm=None if square_size_mm is None else float(square_size_mm) * scale,
        units="mm",
        rms_px=None if rms_px is None else float(rms_px),
        created_at_utc=created_at_utc or datetime.now(timezone.utc).isoformat(),
        opencv_version=cv2.__version__,
        app_version=__version__,
        source=str(source),
        views_received=len(reports),
        views_accepted=sum(report.accepted for report in reports),
        views_rejected=sum(not report.accepted for report in reports),
        view_reports=reports,
        source_metadata={**(source_metadata or {}), "input_units": str(units), "internal_units": "mm"},
    )


def _read_image(source: str | Path | np.ndarray, index: int) -> tuple[str, np.ndarray | None]:
    if isinstance(source, np.ndarray):
        return f"view_{index + 1:03d}", source
    path = Path(source)
    try:
        image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, cv2.error):
        image = None
    return str(path), image


def _object_points(inner_corners: tuple[int, int], square_size_mm: float) -> np.ndarray:
    columns, rows = inner_corners
    points = np.zeros((columns * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points[:, :2] *= float(square_size_mm)
    return points


def calibrate_air_from_images(
    images: Iterable[str | Path | np.ndarray],
    *,
    inner_corners: tuple[int, int],
    square_size: float,
    units: str,
    resolution: tuple[int, int] | None,
    profile_id: str = "C-air",
    minimum_usable_views: int = 15,
) -> AirCalibrationProfile:
    """Calibra K_air/D_air con tablero en aire y conserva poses por vista."""

    columns, rows = int(inner_corners[0]), int(inner_corners[1])
    scale = unit_scale_to_mm(units)
    square_mm = _finite(square_size, "El tamaño del cuadro") * scale
    if columns < 2 or rows < 2 or square_mm <= 0:
        raise AirCalibrationError("El tablero y el tamaño de cuadro deben ser positivos.")
    if int(minimum_usable_views) < 15:
        raise AirCalibrationError("La calibración en aire requiere solicitar al menos 15 vistas.")
    expected_resolution = None if resolution is None else (int(resolution[0]), int(resolution[1]))
    objects = _object_points((columns, rows), square_mm)
    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    reports: list[AirCalibrationViewReport] = []
    accepted_indices: list[int] = []
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)
    for index, source in enumerate(images):
        image_id, image = _read_image(source, index)
        if image is None or image.size == 0:
            reports.append(AirCalibrationViewReport(image_id, False, "imagen ilegible"))
            continue
        height, width = image.shape[:2]
        actual = (width, height)
        if expected_resolution is None:
            expected_resolution = actual
        if actual != expected_resolution:
            reports.append(AirCalibrationViewReport(image_id, False, f"resolución incompatible: {actual[0]}×{actual[1]}"))
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        try:
            found, corners = cv2.findChessboardCorners(gray, (columns, rows), flags=flags)
        except cv2.error as exc:
            reports.append(AirCalibrationViewReport(image_id, False, f"error OpenCV: {exc}"))
            continue
        if not found or corners is None or len(corners) != len(objects):
            reports.append(AirCalibrationViewReport(image_id, False, "tablero no detectado completo"))
            continue
        try:
            refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        except cv2.error as exc:
            reports.append(AirCalibrationViewReport(image_id, False, f"falló refinamiento subpíxel: {exc}"))
            continue
        object_points.append(objects.copy())
        image_points.append(refined.astype(np.float32))
        accepted_indices.append(len(reports))
        reports.append(AirCalibrationViewReport(image_id, True))
    if expected_resolution is None:
        raise AirCalibrationError("No se recibió ninguna imagen legible.", reports=reports)
    if len(object_points) < int(minimum_usable_views):
        raise AirCalibrationError(
            f"Se requieren al menos {minimum_usable_views} vistas utilizables; se aceptaron {len(object_points)}.",
            reports=reports,
        )
    try:
        result = cv2.calibrateCameraExtended(object_points, image_points, expected_resolution, None, None)
        rms, matrix, distortion, rvecs, tvecs = result[:5]
        errors = np.asarray(result[7], dtype=float).reshape(-1)
    except (AttributeError, cv2.error) as exc:
        raise AirCalibrationError(f"OpenCV no pudo calibrar en aire: {exc}", reports=reports) from exc
    for index, report_index in enumerate(accepted_indices):
        reports[report_index] = replace(
            reports[report_index],
            reprojection_error_px=float(errors[index]),
            rvec=tuple(float(v) for v in np.asarray(rvecs[index]).reshape(3)),
            tvec_mm=tuple(float(v) for v in np.asarray(tvecs[index]).reshape(3)),
        )
    return make_air_calibration_profile(
        profile_id=profile_id,
        model="OPENCV",
        camera_matrix=matrix,
        distortion_coefficients=np.asarray(distortion).reshape(-1),
        resolution=expected_resolution,
        board_inner_corners=(columns, rows),
        square_size_mm=square_mm,
        units="mm",
        rms_px=float(rms),
        source="opencv_calibrateCamera_air",
        view_reports=reports,
        source_metadata={"minimum_usable_views": int(minimum_usable_views), "rms_target_px": 0.5},
    )


def save_air_calibration(profile: AirCalibrationProfile, path: str | Path) -> Path:
    validate_air_profile(profile)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(profile.to_dict(), sort_keys=False, allow_unicode=True), encoding="utf-8")
    return output


def load_air_calibration(path: str | Path) -> AirCalibrationProfile:
    input_path = Path(path)
    try:
        payload = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AirCalibrationError(f"No se pudo leer el perfil de calibración en aire: {input_path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise AirCalibrationError("El archivo no usa el esquema nativo air_calibration.v1.")
    try:
        versions = payload["versions"]
        board = payload.get("board")
        views = payload.get("views", {})
        reports = tuple(
            AirCalibrationViewReport(
                image_id=str(item["image_id"]),
                accepted=bool(item["accepted"]),
                rejection_reason=item.get("rejection_reason"),
                reprojection_error_px=None if item.get("reprojection_error_px") is None else float(item["reprojection_error_px"]),
                rvec=None if item.get("rvec") is None else tuple(float(v) for v in item["rvec"]),
                tvec_mm=None if item.get("tvec_mm") is None else tuple(float(v) for v in item["tvec_mm"]),
            )
            for item in views.get("reports", [])
        )
        return AirCalibrationProfile(
            profile_id=str(payload["profile_id"]),
            profile_hash=str(payload["profile_hash"]),
            model=str(payload["model"]),
            camera_matrix=tuple(tuple(float(v) for v in row) for row in payload["camera_matrix"]),
            distortion_coefficients=tuple(float(v) for v in payload["distortion_coefficients"]),
            resolution=(int(payload["resolution"][0]), int(payload["resolution"][1])),
            board_inner_corners=None if board is None else tuple(int(v) for v in board["inner_corners"]),
            square_size_mm=None if board is None else float(board["square_size_mm"]),
            units=str("mm" if board is None else board.get("units", "mm")),
            rms_px=None if payload.get("rms_px") is None else float(payload["rms_px"]),
            created_at_utc=str(payload["created_at_utc"]),
            opencv_version=str(versions["opencv"]),
            app_version=str(versions["fish_morphometry"]),
            source=str(payload["source"]),
            views_received=int(views.get("received", len(reports))),
            views_accepted=int(views.get("accepted", sum(r.accepted for r in reports))),
            views_rejected=int(views.get("rejected", sum(not r.accepted for r in reports))),
            view_reports=reports,
            source_metadata=dict(payload.get("source_metadata") or {}),
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise AirCalibrationError(f"El perfil de aire está incompleto: {exc}") from exc


calibrate_c_air = calibrate_air_from_images


__all__ = [
    "AirCalibrationError",
    "AirCalibrationProfile",
    "AirCalibrationViewReport",
    "SCHEMA",
    "calibrate_air_from_images",
    "calibrate_c_air",
    "load_air_calibration",
    "make_air_calibration_profile",
    "save_air_calibration",
    "unit_scale_to_mm",
    "validate_air_profile",
]
