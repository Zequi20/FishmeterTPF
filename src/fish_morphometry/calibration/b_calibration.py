"""Calibración pinhole efectiva B con un tablero sumergido.

La distorsión estimada aquí es parte de un modelo pinhole *efectivo*.  No
representa ni corrige físicamente la refracción del conjunto aire–vidrio–agua.
"""

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


SCHEMA = "fish_morphometry.b_calibration.v1"
SUPPORTED_DISTORTION_LENGTHS = (0, 4, 5, 8, 12, 14)
SUPPORTED_PINHOLE_MODELS = {
    "SIMPLE_PINHOLE",
    "PINHOLE",
    "SIMPLE_RADIAL",
    "RADIAL",
    "OPENCV",
    "FULL_OPENCV",
}


class CalibrationError(ValueError):
    """Error de configuración, detección o ajuste de una calibración B."""

    def __init__(self, message: str, *, reports: Sequence["CalibrationViewReport"] = ()):
        super().__init__(message)
        self.reports = tuple(reports)


@dataclass(frozen=True)
class CalibrationViewReport:
    """Resultado auditable del procesamiento de una vista del tablero."""

    image_id: str
    accepted: bool
    rejection_reason: str | None = None
    reprojection_error_px: float | None = None
    board_center_normalized: tuple[float, float] | None = None
    board_area_fraction: float | None = None
    tilt_degrees: float | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "image_id": self.image_id,
            "accepted": self.accepted,
            "rejection_reason": self.rejection_reason,
            "reprojection_error_px": self.reprojection_error_px,
            "board_center_normalized": (
                None
                if self.board_center_normalized is None
                else list(self.board_center_normalized)
            ),
            "board_area_fraction": self.board_area_fraction,
            "tilt_degrees": self.tilt_degrees,
        }


@dataclass(frozen=True)
class BCalibrationProfile:
    """Intrínsecos efectivos de B y su procedencia experimental."""

    profile_id: str
    profile_hash: str
    model: str
    camera_matrix: tuple[tuple[float, float, float], ...]
    distortion_coefficients: tuple[float, ...]
    resolution: tuple[int, int]
    calibration_rail_position_mm: float
    created_at_utc: str
    opencv_version: str
    app_version: str
    source: str
    board_inner_corners: tuple[int, int] | None = None
    square_size_mm: float | None = None
    rms_px: float | None = None
    views_received: int = 0
    views_accepted: int = 0
    views_rejected: int = 0
    view_reports: tuple[CalibrationViewReport, ...] = ()
    source_metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        validate_b_calibration_profile(self)

    @property
    def K(self) -> np.ndarray:
        return np.asarray(self.camera_matrix, dtype=np.float64)

    @property
    def D(self) -> np.ndarray:
        return np.asarray(self.distortion_coefficients, dtype=np.float64)

    @property
    def calibration_context_hash(self) -> str:
        """Identifica intrínsecos y condiciones experimentales de calibración."""

        payload = {
            "profile_hash": self.profile_hash,
            "calibration_rail_position_mm": self.calibration_rail_position_mm,
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
            "calibration_rail_position_mm": self.calibration_rail_position_mm,
            "created_at_utc": self.created_at_utc,
            "versions": {
                "opencv": self.opencv_version,
                "fish_morphometry": self.app_version,
            },
            "source": self.source,
            "board": (
                None
                if self.board_inner_corners is None
                else {
                    "inner_corners": list(self.board_inner_corners),
                    "square_size_mm": self.square_size_mm,
                }
            ),
            "rms_px": self.rms_px,
            "views": {
                "received": self.views_received,
                "accepted": self.views_accepted,
                "rejected": self.views_rejected,
                "reports": [report.to_dict() for report in self.view_reports],
            },
            "source_metadata": self.source_metadata or {},
            "limitations": [
                "Modelo pinhole efectivo a través de vidrio y agua.",
                "D_B no es una corrección física de la refracción.",
                "La validez métrica depende de la posición del rail.",
            ],
        }


def _finite(value: object, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise CalibrationError(f"{label} debe ser numérico.") from exc
    if not math.isfinite(number):
        raise CalibrationError(f"{label} debe ser finito.")
    return number


def _profile_hash_payload(
    model: str,
    camera_matrix: Sequence[Sequence[float]],
    distortion: Sequence[float],
    resolution: Sequence[int],
) -> str:
    payload = {
        "model": str(model).upper(),
        "camera_matrix": [[float(value) for value in row] for row in camera_matrix],
        "distortion_coefficients": [float(value) for value in distortion],
        "resolution": [int(resolution[0]), int(resolution[1])],
    }
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def validate_b_calibration_profile(profile: BCalibrationProfile) -> None:
    """Valida forma, finitud y convenciones OpenCV de un perfil."""

    if not str(profile.profile_id).strip():
        raise CalibrationError("El perfil B debe tener un ID no vacío.")
    model = str(profile.model).strip().upper().replace("-", "_").replace(" ", "_")
    if model not in SUPPORTED_PINHOLE_MODELS:
        raise CalibrationError(
            f"Modelo B no compatible con OpenCV pinhole: {profile.model}. "
            f"Admitidos: {', '.join(sorted(SUPPORTED_PINHOLE_MODELS))}."
        )
    matrix = np.asarray(profile.camera_matrix, dtype=float)
    if matrix.shape != (3, 3) or not np.all(np.isfinite(matrix)):
        raise CalibrationError("K_B debe ser una matriz finita de 3×3.")
    if matrix[0, 0] <= 0 or matrix[1, 1] <= 0:
        raise CalibrationError("Las focales fx y fy de K_B deben ser positivas.")
    if not np.allclose(matrix[2], (0.0, 0.0, 1.0), atol=1e-9):
        raise CalibrationError("La última fila de K_B debe ser [0, 0, 1].")
    distortion = np.asarray(profile.distortion_coefficients, dtype=float).reshape(-1)
    if len(distortion) not in SUPPORTED_DISTORTION_LENGTHS:
        raise CalibrationError(
            "D_B debe tener longitud 0, 4, 5, 8, 12 o 14 para cv2.undistortPoints."
        )
    if not np.all(np.isfinite(distortion)):
        raise CalibrationError("D_B contiene valores no finitos.")
    if len(profile.resolution) != 2 or any(int(value) <= 0 for value in profile.resolution):
        raise CalibrationError("La resolución B debe ser [ancho, alto] con valores positivos.")
    _finite(profile.calibration_rail_position_mm, "La posición de calibración en el rail")
    if profile.board_inner_corners is not None:
        if any(int(value) < 2 for value in profile.board_inner_corners):
            raise CalibrationError("El tablero debe tener al menos 2×2 esquinas internas.")
        if profile.square_size_mm is None or _finite(profile.square_size_mm, "El tamaño del cuadro") <= 0:
            raise CalibrationError("El tamaño físico del cuadro debe ser mayor que cero.")
    if profile.rms_px is not None and _finite(profile.rms_px, "El RMS") < 0:
        raise CalibrationError("El RMS no puede ser negativo.")
    expected_hash = _profile_hash_payload(
        profile.model,
        profile.camera_matrix,
        profile.distortion_coefficients,
        profile.resolution,
    )
    if profile.profile_hash != expected_hash:
        raise CalibrationError("El hash del perfil B no coincide con K_B, D_B, modelo y resolución.")
    if profile.views_received != profile.views_accepted + profile.views_rejected:
        raise CalibrationError("El conteo de vistas B es inconsistente.")


def make_b_calibration_profile(
    *,
    profile_id: str,
    model: str,
    camera_matrix: Sequence[Sequence[float]],
    distortion_coefficients: Sequence[float],
    resolution: Sequence[int],
    calibration_rail_position_mm: float,
    created_at_utc: str | None = None,
    source: str,
    board_inner_corners: Sequence[int] | None = None,
    square_size_mm: float | None = None,
    rms_px: float | None = None,
    view_reports: Sequence[CalibrationViewReport] = (),
    source_metadata: dict[str, Any] | None = None,
) -> BCalibrationProfile:
    """Construye un perfil y calcula su hash reproducible."""

    from .. import __version__

    matrix = tuple(tuple(float(value) for value in row) for row in camera_matrix)
    distortion = tuple(float(value) for value in distortion_coefficients)
    image_resolution = (int(resolution[0]), int(resolution[1]))
    reports = tuple(view_reports)
    accepted = sum(report.accepted for report in reports)
    return BCalibrationProfile(
        profile_id=str(profile_id).strip(),
        profile_hash=_profile_hash_payload(model, matrix, distortion, image_resolution),
        model=str(model).upper(),
        camera_matrix=matrix,
        distortion_coefficients=distortion,
        resolution=image_resolution,
        calibration_rail_position_mm=float(calibration_rail_position_mm),
        created_at_utc=created_at_utc or datetime.now(timezone.utc).isoformat(),
        opencv_version=cv2.__version__,
        app_version=__version__,
        source=str(source),
        board_inner_corners=(
            None
            if board_inner_corners is None
            else (int(board_inner_corners[0]), int(board_inner_corners[1]))
        ),
        square_size_mm=None if square_size_mm is None else float(square_size_mm),
        rms_px=None if rms_px is None else float(rms_px),
        views_received=len(reports),
        views_accepted=accepted,
        views_rejected=len(reports) - accepted,
        view_reports=reports,
        source_metadata=source_metadata or {},
    )


def _read_image(source: str | Path | np.ndarray, index: int) -> tuple[str, np.ndarray | None]:
    if isinstance(source, np.ndarray):
        return f"view_{index + 1:03d}", source
    path = Path(source)
    try:
        data = np.fromfile(path, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    except (OSError, cv2.error):
        image = None
    return str(path), image


def _object_points(inner_corners: tuple[int, int], square_size_mm: float) -> np.ndarray:
    columns, rows = inner_corners
    points = np.zeros((columns * rows, 3), np.float32)
    points[:, :2] = np.mgrid[0:columns, 0:rows].T.reshape(-1, 2)
    points[:, :2] *= float(square_size_mm)
    return points


def calibrate_b_from_images(
    images: Iterable[str | Path | np.ndarray],
    *,
    inner_corners: tuple[int, int],
    square_size_mm: float,
    resolution: tuple[int, int] | None,
    calibration_rail_position_mm: float,
    profile_id: str = "B-effective",
    minimum_usable_views: int = 15,
    maximum_per_view_error_px: float = 1.5,
    minimum_center_span_fraction: float = 0.20,
    minimum_tilt_span_degrees: float = 10.0,
) -> BCalibrationProfile:
    """Detecta un damero sumergido y ajusta ``K_B,D_B`` con OpenCV.

    ``inner_corners`` sigue el orden (columnas, filas) y ``resolution`` el orden
    (ancho, alto). Cada rechazo queda en ``CalibrationError.reports`` si no se
    alcanza el mínimo de vistas utilizables.
    """

    columns, rows = (int(inner_corners[0]), int(inner_corners[1]))
    square = _finite(square_size_mm, "El tamaño físico del cuadro")
    rail_position = _finite(calibration_rail_position_mm, "La posición de calibración")
    if columns < 2 or rows < 2:
        raise CalibrationError("El tablero debe tener al menos 2×2 esquinas internas.")
    if square <= 0:
        raise CalibrationError("El tamaño físico del cuadro debe ser mayor que cero.")
    if int(minimum_usable_views) < 15:
        raise CalibrationError("B requiere solicitar al menos 15 vistas utilizables.")
    maximum_view_error = _finite(maximum_per_view_error_px, "El error máximo por vista")
    minimum_center_span = _finite(
        minimum_center_span_fraction, "La cobertura mínima de centros"
    )
    minimum_tilt_span = _finite(
        minimum_tilt_span_degrees, "La diversidad angular mínima"
    )
    if maximum_view_error <= 0:
        raise CalibrationError("El error máximo por vista debe ser positivo.")
    if minimum_center_span < 0 or minimum_center_span > 1:
        raise CalibrationError("La cobertura mínima debe estar entre 0 y 1.")
    if minimum_tilt_span < 0 or minimum_tilt_span >= 90:
        raise CalibrationError("La diversidad angular mínima debe estar entre 0 y 90 grados.")
    expected_resolution = None if resolution is None else (int(resolution[0]), int(resolution[1]))
    if expected_resolution is not None and any(value <= 0 for value in expected_resolution):
        raise CalibrationError("La resolución configurada debe ser positiva.")

    object_template = _object_points((columns, rows), square)
    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    reports: list[CalibrationViewReport] = []
    accepted_report_indices: list[int] = []
    detection_flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE
    termination = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)

    for index, source in enumerate(images):
        image_id, image = _read_image(source, index)
        if image is None or image.ndim < 2 or image.size == 0:
            reports.append(CalibrationViewReport(image_id, False, "imagen ilegible"))
            continue
        height, width = image.shape[:2]
        actual_resolution = (width, height)
        if expected_resolution is None:
            expected_resolution = actual_resolution
        if actual_resolution != expected_resolution:
            reports.append(
                CalibrationViewReport(
                    image_id,
                    False,
                    f"resolución incompatible: {width}×{height}; esperada "
                    f"{expected_resolution[0]}×{expected_resolution[1]}",
                )
            )
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        try:
            found, corners = cv2.findChessboardCorners(
                gray, (columns, rows), flags=detection_flags
            )
        except cv2.error as exc:
            reports.append(CalibrationViewReport(image_id, False, f"error OpenCV: {exc}"))
            continue
        if not found or corners is None or len(corners) != columns * rows:
            reports.append(CalibrationViewReport(image_id, False, "tablero no detectado completo"))
            continue
        try:
            refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), termination)
        except cv2.error as exc:
            reports.append(
                CalibrationViewReport(image_id, False, f"falló el refinamiento subpíxel: {exc}")
            )
            continue
        object_points.append(object_template.copy())
        image_points.append(refined.astype(np.float32))
        accepted_report_indices.append(len(reports))
        reports.append(CalibrationViewReport(image_id, True))

    if expected_resolution is None:
        raise CalibrationError("No se recibió ninguna imagen legible.", reports=reports)
    if len(object_points) < int(minimum_usable_views):
        raise CalibrationError(
            f"B requiere al menos {minimum_usable_views} vistas utilizables; "
            f"se aceptaron {len(object_points)} de {len(reports)}.",
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
                error_values = []
                for objects, observed, rvec, tvec in zip(
                    object_points, image_points, rvec_values, tvec_values, strict=True
                ):
                    projected, _ = cv2.projectPoints(
                        objects, rvec, tvec, matrix_value, distortion_value
                    )
                    error = cv2.norm(observed, projected, cv2.NORM_L2) / math.sqrt(len(objects))
                    error_values.append(float(error))
            return (
                float(rms_value),
                matrix_value,
                distortion_value,
                list(rvec_values),
                list(tvec_values),
                np.asarray(error_values, dtype=float).reshape(-1),
            )
        except cv2.error as exc:
            raise CalibrationError(
                f"OpenCV no pudo calibrar las vistas aceptadas: {exc}", reports=reports
            ) from exc

    while True:
        rms, camera_matrix, distortion, rvecs, _tvecs, per_view_errors = run_calibration()
        if len(per_view_errors) != len(object_points):
            raise CalibrationError(
                "OpenCV devolvió un número inconsistente de errores por vista.",
                reports=reports,
            )
        outliers = [
            index
            for index, error in enumerate(per_view_errors)
            if not math.isfinite(float(error)) or error > maximum_view_error
        ]
        if not outliers:
            break
        outlier_set = set(outliers)
        if len(object_points) - len(outliers) < int(minimum_usable_views):
            for local_index in outliers:
                report_index = accepted_report_indices[local_index]
                error = float(per_view_errors[local_index])
                reports[report_index] = replace(
                    reports[report_index],
                    accepted=False,
                    rejection_reason=(
                        f"error de reproyección {error:.3f} px > "
                        f"{maximum_view_error:.3f} px"
                    ),
                    reprojection_error_px=error,
                )
            raise CalibrationError(
                "La eliminación de vistas con alto error deja menos vistas que el mínimo requerido.",
                reports=reports,
            )
        for local_index in outliers:
            report_index = accepted_report_indices[local_index]
            error = float(per_view_errors[local_index])
            reports[report_index] = replace(
                reports[report_index],
                accepted=False,
                rejection_reason=(
                    f"error de reproyección {error:.3f} px > "
                    f"{maximum_view_error:.3f} px"
                ),
                reprojection_error_px=error,
            )
        object_points[:] = [value for i, value in enumerate(object_points) if i not in outlier_set]
        image_points[:] = [value for i, value in enumerate(image_points) if i not in outlier_set]
        accepted_report_indices[:] = [
            value for i, value in enumerate(accepted_report_indices) if i not in outlier_set
        ]

    centers: list[tuple[float, float]] = []
    tilts: list[float] = []
    normals: list[np.ndarray] = []
    width, height = expected_resolution
    for local_index, report_index in enumerate(accepted_report_indices):
        observed = image_points[local_index].reshape(-1, 2)
        center = (float(np.mean(observed[:, 0]) / width), float(np.mean(observed[:, 1]) / height))
        area_fraction = float(abs(cv2.contourArea(cv2.convexHull(observed))) / (width * height))
        rotation, _ = cv2.Rodrigues(rvecs[local_index])
        normal = rotation @ np.array([0.0, 0.0, 1.0])
        tilt = math.degrees(math.acos(float(np.clip(abs(normal[2]), 0.0, 1.0))))
        centers.append(center)
        tilts.append(tilt)
        normals.append(normal / np.linalg.norm(normal))
        reports[report_index] = replace(
            reports[report_index],
            reprojection_error_px=float(per_view_errors[local_index]),
            board_center_normalized=center,
            board_area_fraction=area_fraction,
            tilt_degrees=tilt,
        )
    center_span_x = max(value[0] for value in centers) - min(value[0] for value in centers)
    center_span_y = max(value[1] for value in centers) - min(value[1] for value in centers)
    tilt_span = max(
        math.degrees(
            math.acos(float(np.clip(abs(np.dot(first, second)), 0.0, 1.0)))
        )
        for index, first in enumerate(normals)
        for second in normals[index:]
    )
    if center_span_x < minimum_center_span or center_span_y < minimum_center_span:
        raise CalibrationError(
            "Las vistas no cubren suficiente diversidad espacial de centros del tablero: "
            f"span=({center_span_x:.3f}, {center_span_y:.3f}), mínimo={minimum_center_span:.3f}.",
            reports=reports,
        )
    if tilt_span < minimum_tilt_span:
        raise CalibrationError(
            "Las vistas no cubren suficiente diversidad de inclinación: "
            f"span={tilt_span:.3f}°, mínimo={minimum_tilt_span:.3f}°.",
            reports=reports,
        )
    return make_b_calibration_profile(
        profile_id=profile_id,
        model="OPENCV",
        camera_matrix=camera_matrix,
        distortion_coefficients=np.asarray(distortion).reshape(-1),
        resolution=expected_resolution,
        calibration_rail_position_mm=rail_position,
        source="opencv_calibrateCamera",
        board_inner_corners=(columns, rows),
        square_size_mm=square,
        rms_px=float(rms),
        view_reports=reports,
        source_metadata={
            "calibration_zone": "nearest_to_glass",
            "minimum_usable_views": int(minimum_usable_views),
            "rms_target_px": 0.7,
            "maximum_per_view_error_px": maximum_view_error,
            "minimum_center_span_fraction": minimum_center_span,
            "center_span_fraction": [center_span_x, center_span_y],
            "minimum_tilt_span_degrees": minimum_tilt_span,
            "tilt_span_degrees": tilt_span,
            "tilt_span_definition": "maximum_pairwise_board_normal_angle",
        },
    )


def save_b_calibration(profile: BCalibrationProfile, path: str | Path) -> Path:
    """Guarda un perfil nativo B sin perder la trazabilidad por vista."""

    validate_b_calibration_profile(profile)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(profile.to_dict(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return output_path


def load_b_calibration(path: str | Path) -> BCalibrationProfile:
    """Carga exclusivamente el esquema nativo B; Calibmar usa su adaptador."""

    input_path = Path(path)
    try:
        payload = yaml.safe_load(input_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CalibrationError(f"No se pudo leer el perfil B: {input_path}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise CalibrationError(
            "El archivo no usa el esquema nativo fish_morphometry.b_calibration.v1."
        )
    try:
        versions = payload["versions"]
        board = payload.get("board")
        views = payload.get("views", {})
        reports = tuple(
            CalibrationViewReport(
                image_id=str(item["image_id"]),
                accepted=bool(item["accepted"]),
                rejection_reason=item.get("rejection_reason"),
                reprojection_error_px=(
                    None
                    if item.get("reprojection_error_px") is None
                    else float(item["reprojection_error_px"])
                ),
                board_center_normalized=(
                    None
                    if item.get("board_center_normalized") is None
                    else (
                        float(item["board_center_normalized"][0]),
                        float(item["board_center_normalized"][1]),
                    )
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
            )
            for item in views.get("reports", [])
        )
        profile = BCalibrationProfile(
            profile_id=str(payload["profile_id"]),
            profile_hash=str(payload["profile_hash"]),
            model=str(payload["model"]),
            camera_matrix=tuple(tuple(float(value) for value in row) for row in payload["camera_matrix"]),
            distortion_coefficients=tuple(float(value) for value in payload["distortion_coefficients"]),
            resolution=(int(payload["resolution"][0]), int(payload["resolution"][1])),
            calibration_rail_position_mm=float(payload["calibration_rail_position_mm"]),
            created_at_utc=str(payload["created_at_utc"]),
            opencv_version=str(versions["opencv"]),
            app_version=str(versions["fish_morphometry"]),
            source=str(payload["source"]),
            board_inner_corners=(
                None
                if board is None
                else (int(board["inner_corners"][0]), int(board["inner_corners"][1]))
            ),
            square_size_mm=None if board is None else float(board["square_size_mm"]),
            rms_px=None if payload.get("rms_px") is None else float(payload["rms_px"]),
            views_received=int(views.get("received", len(reports))),
            views_accepted=int(views.get("accepted", sum(report.accepted for report in reports))),
            views_rejected=int(views.get("rejected", sum(not report.accepted for report in reports))),
            view_reports=reports,
            source_metadata=dict(payload.get("source_metadata") or {}),
        )
        stored_context_hash = payload.get("calibration_context_hash")
        if (
            stored_context_hash is not None
            and str(stored_context_hash) != profile.calibration_context_hash
        ):
            raise CalibrationError(
                "El hash del contexto de calibración B no coincide con el archivo."
            )
        return profile
    except CalibrationError:
        raise
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise CalibrationError(f"El perfil B está incompleto o mal formado: {exc}") from exc


# Nombres cómodos para integraciones externas que ya hablan de calibración de cámara.
calibrate_b = calibrate_b_from_images
calibrate_camera_b = calibrate_b_from_images
load_calibration_b = load_b_calibration
save_calibration_b = save_b_calibration


__all__ = [
    "BCalibrationProfile",
    "CalibrationError",
    "CalibrationViewReport",
    "SCHEMA",
    "SUPPORTED_DISTORTION_LENGTHS",
    "SUPPORTED_PINHOLE_MODELS",
    "calibrate_b_from_images",
    "calibrate_b",
    "calibrate_camera_b",
    "load_b_calibration",
    "load_calibration_b",
    "make_b_calibration_profile",
    "save_b_calibration",
    "save_calibration_b",
    "validate_b_calibration_profile",
]
