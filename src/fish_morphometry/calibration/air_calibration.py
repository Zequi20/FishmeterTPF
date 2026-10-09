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
from ..vision.chessboard_detector import ChessboardInputError, detect_chessboard_corners


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
    board_center_normalized: tuple[float, float] | None = None
    board_area_fraction: float | None = None
    tilt_degrees: float | None = None
    detector_method: str | None = None
    detected_corner_count: int | None = None
    detection_time_ms: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
            "reprojection_error_px": self.reprojection_error_px,
            "rvec": None if self.rvec is None else list(self.rvec),
            "tvec_mm": None if self.tvec_mm is None else list(self.tvec_mm),
            "board_center_normalized": (
                None
                if self.board_center_normalized is None
                else list(self.board_center_normalized)
            ),
            "board_area_fraction": self.board_area_fraction,
            "tilt_degrees": self.tilt_degrees,
            "detector_method": self.detector_method,
            "detected_corner_count": self.detected_corner_count,
            "detection_time_ms": self.detection_time_ms,
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

    @property
    def calibration_context_hash(self) -> str:
        """Identifica intrínsecos y condiciones que afectan la calibración C."""

        payload = {
            "profile_hash": self.profile_hash,
            "source": self.source,
            "board_inner_corners": self.board_inner_corners,
            "square_size_mm": self.square_size_mm,
            "source_metadata": self.source_metadata or {},
        }
        packed = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return hashlib.sha256(packed).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "profile_id": self.profile_id,
            "profile_hash": self.profile_hash,
            "calibration_context_hash": self.calibration_context_hash,
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
    if profile.board_inner_corners is not None and profile.square_size_mm is None:
        raise AirCalibrationError("Un tablero declarado requiere square_size_mm.")
    if profile.board_inner_corners is None and profile.square_size_mm is not None:
        raise AirCalibrationError("square_size_mm no puede declararse sin el tablero asociado.")
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
    maximum_per_view_error_px: float = 1.5,
    minimum_center_span_fraction: float = 0.20,
    minimum_tilt_span_degrees: float = 10.0,
) -> AirCalibrationProfile:
    """Calibra K_air/D_air y rechaza vistas o conjuntos geométricamente débiles."""

    columns, rows = int(inner_corners[0]), int(inner_corners[1])
    scale = unit_scale_to_mm(units)
    square_mm = _finite(square_size, "El tamaño del cuadro") * scale
    if columns < 2 or rows < 2 or square_mm <= 0:
        raise AirCalibrationError("El tablero y el tamaño de cuadro deben ser positivos.")
    if int(minimum_usable_views) < 15:
        raise AirCalibrationError("La calibración en aire requiere solicitar al menos 15 vistas.")
    maximum_view_error = _finite(maximum_per_view_error_px, "El error máximo por vista")
    minimum_center_span = _finite(
        minimum_center_span_fraction, "La cobertura mínima de centros"
    )
    minimum_tilt_span = _finite(
        minimum_tilt_span_degrees, "La diversidad angular mínima"
    )
    if maximum_view_error <= 0:
        raise AirCalibrationError("El error máximo por vista debe ser positivo.")
    if minimum_center_span < 0 or minimum_center_span > 1:
        raise AirCalibrationError("La cobertura mínima debe estar entre 0 y 1.")
    if minimum_tilt_span < 0 or minimum_tilt_span >= 90:
        raise AirCalibrationError(
            "La diversidad angular mínima debe estar entre 0 y 90 grados."
        )
    expected_resolution = None if resolution is None else (int(resolution[0]), int(resolution[1]))
    if expected_resolution is not None and any(value <= 0 for value in expected_resolution):
        raise AirCalibrationError("La resolución configurada debe ser positiva.")
    objects = _object_points((columns, rows), square_mm)
    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    reports: list[AirCalibrationViewReport] = []
    accepted_indices: list[int] = []
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
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        except cv2.error as exc:
            reports.append(
                AirCalibrationViewReport(
                    image_id,
                    False,
                    f"imagen ilegible: no se pudo convertir a grises ({exc})",
                )
            )
            continue
        try:
            detection = detect_chessboard_corners(gray, (columns, rows))
        except ChessboardInputError as exc:
            reports.append(AirCalibrationViewReport(image_id, False, f"imagen inválida para detección: {exc}"))
            continue
        if not detection.found:
            reports.append(
                AirCalibrationViewReport(
                    image_id,
                    False,
                    (
                        f"tablero no detectado completo; se esperaban {len(objects)} esquinas; "
                        f"{detection.diagnostic_summary}"
                    ),
                    detection_time_ms=detection.elapsed_ms,
                )
            )
            continue
        assert detection.corners is not None and detection.method is not None
        object_points.append(objects.copy())
        image_points.append(detection.corners.astype(np.float32))
        accepted_indices.append(len(reports))
        reports.append(
            AirCalibrationViewReport(
                image_id,
                True,
                detector_method=detection.method,
                detected_corner_count=detection.corner_count,
                detection_time_ms=detection.elapsed_ms,
            )
        )
    if expected_resolution is None:
        raise AirCalibrationError("No se recibió ninguna imagen legible.", reports=reports)
    if len(object_points) < int(minimum_usable_views):
        raise AirCalibrationError(
            f"Se requieren al menos {minimum_usable_views} vistas utilizables; se aceptaron {len(object_points)}.",
            reports=reports,
        )
    def run_calibration() -> tuple[
        float,
        np.ndarray,
        np.ndarray,
        list[np.ndarray],
        list[np.ndarray],
        np.ndarray,
    ]:
        try:
            if hasattr(cv2, "calibrateCameraExtended"):
                result = cv2.calibrateCameraExtended(
                    object_points, image_points, expected_resolution, None, None
                )
                rms_value, matrix_value, distortion_value, rvec_values, tvec_values = result[:5]
                error_values = np.asarray(result[7], dtype=float).reshape(-1)
            else:
                rms_value, matrix_value, distortion_value, rvec_values, tvec_values = cv2.calibrateCamera(
                    object_points, image_points, expected_resolution, None, None
                )
                computed_errors: list[float] = []
                for objects, observed, rvec, tvec in zip(
                    object_points, image_points, rvec_values, tvec_values, strict=True
                ):
                    projected, _ = cv2.projectPoints(
                        objects, rvec, tvec, matrix_value, distortion_value
                    )
                    computed_errors.append(
                        float(cv2.norm(observed, projected, cv2.NORM_L2) / math.sqrt(len(objects)))
                    )
                error_values = np.asarray(computed_errors, dtype=float)
            return (
                float(rms_value),
                matrix_value,
                distortion_value,
                list(rvec_values),
                list(tvec_values),
                np.asarray(error_values, dtype=float).reshape(-1),
            )
        except (AttributeError, cv2.error) as exc:
            raise AirCalibrationError(
                f"OpenCV no pudo calibrar en aire: {exc}", reports=reports
            ) from exc

    while True:
        rms, matrix, distortion, rvecs, tvecs, errors = run_calibration()
        if len(errors) != len(object_points):
            raise AirCalibrationError(
                "OpenCV devolvió un número inconsistente de errores por vista.",
                reports=reports,
            )
        outliers = [
            index
            for index, error in enumerate(errors)
            if not math.isfinite(float(error)) or float(error) > maximum_view_error
        ]
        if not outliers:
            break
        outlier_set = set(outliers)
        for local_index in outliers:
            report_index = accepted_indices[local_index]
            error = float(errors[local_index])
            reports[report_index] = replace(
                reports[report_index],
                accepted=False,
                rejection_reason=(
                    f"error de reproyección {error:.3f} px > {maximum_view_error:.3f} px"
                ),
                reprojection_error_px=error,
            )
        if len(object_points) - len(outliers) < int(minimum_usable_views):
            raise AirCalibrationError(
                "La eliminación de vistas con alto error deja menos vistas que el mínimo requerido.",
                reports=reports,
            )
        object_points[:] = [
            value for index, value in enumerate(object_points) if index not in outlier_set
        ]
        image_points[:] = [
            value for index, value in enumerate(image_points) if index not in outlier_set
        ]
        accepted_indices[:] = [
            value for index, value in enumerate(accepted_indices) if index not in outlier_set
        ]

    centers: list[tuple[float, float]] = []
    normals: list[np.ndarray] = []
    width, height = expected_resolution
    for index, report_index in enumerate(accepted_indices):
        observed = image_points[index].reshape(-1, 2)
        center = (
            float(np.mean(observed[:, 0]) / width),
            float(np.mean(observed[:, 1]) / height),
        )
        area_fraction = float(
            abs(cv2.contourArea(cv2.convexHull(observed))) / (width * height)
        )
        rotation, _ = cv2.Rodrigues(rvecs[index])
        normal = rotation @ np.asarray((0.0, 0.0, 1.0))
        normal /= np.linalg.norm(normal)
        tilt = math.degrees(math.acos(float(np.clip(abs(normal[2]), 0.0, 1.0))))
        centers.append(center)
        normals.append(normal)
        reports[report_index] = replace(
            reports[report_index],
            reprojection_error_px=float(errors[index]),
            rvec=tuple(float(v) for v in np.asarray(rvecs[index]).reshape(3)),
            tvec_mm=tuple(float(v) for v in np.asarray(tvecs[index]).reshape(3)),
            board_center_normalized=center,
            board_area_fraction=area_fraction,
            tilt_degrees=tilt,
        )
    center_span_x = max(value[0] for value in centers) - min(value[0] for value in centers)
    center_span_y = max(value[1] for value in centers) - min(value[1] for value in centers)
    tilt_span = max(
        math.degrees(math.acos(float(np.clip(abs(np.dot(first, second)), 0.0, 1.0))))
        for index, first in enumerate(normals)
        for second in normals[index:]
    )
    if center_span_x < minimum_center_span or center_span_y < minimum_center_span:
        raise AirCalibrationError(
            "Las vistas no cubren suficiente diversidad espacial de centros del tablero: "
            f"span=({center_span_x:.3f}, {center_span_y:.3f}), mínimo={minimum_center_span:.3f}.",
            reports=reports,
        )
    if tilt_span < minimum_tilt_span:
        raise AirCalibrationError(
            "Las vistas no cubren suficiente diversidad de inclinación: "
            f"span={tilt_span:.3f}°, mínimo={minimum_tilt_span:.3f}°.",
            reports=reports,
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
        source_metadata={
            "minimum_usable_views": int(minimum_usable_views),
            "rms_target_px": 0.5,
            "rms_scope": "in_air_intrinsics",
            "maximum_per_view_error_px": maximum_view_error,
            "minimum_center_span_fraction": minimum_center_span,
            "center_span_fraction": [center_span_x, center_span_y],
            "minimum_tilt_span_degrees": minimum_tilt_span,
            "tilt_span_degrees": tilt_span,
            "tilt_span_definition": "maximum_pairwise_board_normal_angle",
        },
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
                board_center_normalized=(
                    None
                    if item.get("board_center_normalized") is None
                    else tuple(float(v) for v in item["board_center_normalized"])
                ),
                board_area_fraction=(
                    None
                    if item.get("board_area_fraction") is None
                    else float(item["board_area_fraction"])
                ),
                tilt_degrees=(
                    None
                    if item.get("tilt_degrees") is None
                    else float(item["tilt_degrees"])
                ),
                detector_method=None if item.get("detector_method") is None else str(item["detector_method"]),
                detected_corner_count=(
                    None
                    if item.get("detected_corner_count") is None
                    else int(item["detected_corner_count"])
                ),
                detection_time_ms=(
                    None
                    if item.get("detection_time_ms") is None
                    else float(item["detection_time_ms"])
                ),
            )
            for item in views.get("reports", [])
        )
        profile = AirCalibrationProfile(
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
        stored_context_hash = payload.get("calibration_context_hash")
        if (
            stored_context_hash is not None
            and str(stored_context_hash) != profile.calibration_context_hash
        ):
            raise AirCalibrationError("El hash del contexto de calibración en aire no coincide.")
        return profile
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
