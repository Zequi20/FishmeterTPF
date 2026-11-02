"""Verificación no trivial del módulo refractivo de puerto plano (ruta C).

Compara el trazado de Fishmeter con la solución analítica de la ley de Snell
para dos interfaces planas y paralelas (aire–vidrio–agua), con incidencia
oblicua, índices distintos y vidrio de espesor no nulo. Los valores esperados
se calculan aquí con trigonometría escalar, sin usar el código de Fishmeter.

Parámetros del montaje de la tesis: d = 230 mm, t_g = 4 mm,
mu_a = 1,000, mu_g = 1,500 y mu_w = 1,333.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fish_morphometry.calibration.air_calibration import make_air_calibration_profile
from fish_morphometry.geometry.refractive_port import (
    make_flat_port_parameters,
    make_measurement_plane,
    trace_refracted_ray,
)
from fish_morphometry.methods.c import measure_c

D_MM = 230.0
TG_MM = 4.0
N_AIR, N_GLASS, N_WATER = 1.0, 1.5, 1.333
TOL_MM = 1e-6

# Cámara sintética del tamaño de las capturas (4096 x 3072), sin distorsión.
FX = FY = 3000.0
CX, CY = 2048.0, 1536.0


@pytest.fixture
def port():
    return make_flat_port_parameters(
        normal_camera=(0.0, 0.0, 1.0),
        interface_distance_mm=D_MM,
        glass_thickness_mm=TG_MM,
        n_air=N_AIR,
        n_glass=N_GLASS,
        n_water=N_WATER,
        source="analytic-test",
    )


def analytic_radius(theta_air: float, z_mm: float) -> float:
    """Distancia radial al eje en el plano a z mm detrás de la cara interna."""
    s = N_AIR * math.sin(theta_air)
    theta_g = math.asin(s / N_GLASS)
    theta_w = math.asin(s / N_WATER)
    return D_MM * math.tan(theta_air) + TG_MM * math.tan(theta_g) + z_mm * math.tan(theta_w)


def solve_theta_air(radius_mm: float, z_mm: float) -> float:
    """Ángulo en aire que llega a un radio dado (bisección; r(θ) es creciente)."""
    lo, hi = 0.0, math.radians(80.0)
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if analytic_radius(mid, z_mm) < radius_mm:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def air_direction(theta: float, azimuth: float) -> tuple[float, float, float]:
    return (
        math.sin(theta) * math.cos(azimuth),
        math.sin(theta) * math.sin(azimuth),
        math.cos(theta),
    )


def intersect_plane(trace, z_mm: float) -> np.ndarray:
    q2 = np.asarray(trace.q2_camera_mm, dtype=float)
    v = np.asarray(trace.v_water, dtype=float)
    lam = (D_MM + TG_MM + z_mm - q2[2]) / v[2]
    return q2 + lam * v


def project_point(x_mm: float, y_mm: float, z_mm: float) -> tuple[float, float]:
    """Proyección analítica (directa) de un punto detrás del vidrio a píxeles."""
    radius = math.hypot(x_mm, y_mm)
    azimuth = math.atan2(y_mm, x_mm)
    theta = solve_theta_air(radius, z_mm)
    vx, vy, vz = air_direction(theta, azimuth)
    return (CX + FX * vx / vz, CY + FY * vy / vz)


# 1. Trazado directo frente a la solución analítica ---------------------------
@pytest.mark.parametrize("theta_deg", [5.0, 20.0, 35.0])
@pytest.mark.parametrize("azimuth_deg", [0.0, 30.0, 135.0])
@pytest.mark.parametrize("z_mm", [50.0, 110.0, 230.0])
def test_trace_matches_analytic_flat_port(port, theta_deg, azimuth_deg, z_mm):
    theta, azimuth = math.radians(theta_deg), math.radians(azimuth_deg)
    trace = trace_refracted_ray(air_direction(theta, azimuth), port)
    point = intersect_plane(trace, z_mm)

    expected_r = analytic_radius(theta, z_mm)
    expected = (expected_r * math.cos(azimuth), expected_r * math.sin(azimuth))
    assert point[0] == pytest.approx(expected[0], abs=TOL_MM)
    assert point[1] == pytest.approx(expected[1], abs=TOL_MM)
    assert point[2] == pytest.approx(D_MM + TG_MM + z_mm, abs=TOL_MM)

    # Invariante de Snell en los tres medios: mu * sen(theta) constante.
    sines = []
    for v, n in ((trace.v_air, N_AIR), (trace.v_glass, N_GLASS), (trace.v_water, N_WATER)):
        v = np.asarray(v, dtype=float)
        sines.append(n * math.hypot(v[0], v[1]) / np.linalg.norm(v))
    assert sines[1] == pytest.approx(sines[0], abs=1e-12)
    assert sines[2] == pytest.approx(sines[0], abs=1e-12)

    # La refracción acerca el rayo al eje: sin vidrio ni agua el radio sería mayor.
    if theta_deg > 0:
        assert expected_r < (D_MM + TG_MM + z_mm) * math.tan(theta)


def test_reference_value_for_thesis(port):
    """Valor de referencia citado en la tesis: rayo a 20°, z = 110 mm."""
    trace = trace_refracted_ray(air_direction(math.radians(20.0), 0.0), port)
    point = intersect_plane(trace, 110.0)
    assert point[0] == pytest.approx(113.851166, abs=1e-5)


# 2. Ida y vuelta: punto conocido -> píxel -> trazado -> mismo punto ----------
@pytest.mark.parametrize(
    "x_mm, y_mm, z_mm",
    [(40.0, 0.0, 110.0), (-60.0, 35.0, 50.0), (90.0, -70.0, 230.0), (0.0, 0.0, 170.0)],
)
def test_round_trip_known_point_behind_glass(port, x_mm, y_mm, z_mm):
    radius = math.hypot(x_mm, y_mm)
    azimuth = math.atan2(y_mm, x_mm)
    theta = solve_theta_air(radius, z_mm)
    trace = trace_refracted_ray(air_direction(theta, azimuth), port)
    point = intersect_plane(trace, z_mm)
    assert point[0] == pytest.approx(x_mm, abs=TOL_MM)
    assert point[1] == pytest.approx(y_mm, abs=TOL_MM)


# 3. Medición completa con measure_c sobre un segmento sintético ---------------
@pytest.fixture
def synthetic_air_profile():
    return make_air_calibration_profile(
        profile_id="analytic-air",
        model="OPENCV",
        camera_matrix=((FX, 0.0, CX), (0.0, FY, CY), (0.0, 0.0, 1.0)),
        distortion_coefficients=(0.0, 0.0, 0.0, 0.0, 0.0),
        resolution=(4096, 3072),
        board_inner_corners=None,
        square_size_mm=None,
        units="mm",
        rms_px=0.1,
        source="analytic-test",
    )


def synthetic_points(z_mm: float, x0: float = 60.0, y0: float = 40.0):
    """Réplica sintética fuera del centro: LT = 140 mm y PC = 40 mm."""
    return {
        "p1": project_point(x0 - 70.0, y0, z_mm),  # extremo caudal
        "p2": project_point(x0 + 70.0, y0, z_mm),  # hocico
        "p3": project_point(x0, y0 - 20.0, z_mm),  # perfil dorsal
        "p4": project_point(x0, y0 + 20.0, z_mm),  # perfil ventral
    }


@pytest.mark.parametrize("z_mm", [50.0, 110.0, 170.0, 230.0])
def test_measure_c_recovers_known_length(port, synthetic_air_profile, z_mm):
    plane = make_measurement_plane((0.0, 0.0, D_MM + TG_MM + z_mm), (0.0, 0.0, 1.0), source="analytic-test")
    result = measure_c(
        f"analytic-{z_mm:.0f}",
        synthetic_points(z_mm),
        synthetic_air_profile,
        port,
        plane,
        replica_id="synthetic",
        image_shape=(3072, 4096, 3),
    )
    # Distancias euclidianas en el plano: deben coincidir con la geometría real.
    assert result.total_length_euclidean_mm == pytest.approx(140.0, abs=TOL_MM)
    assert result.body_depth_euclidean_mm == pytest.approx(40.0, abs=TOL_MM)
    # LT y PC proyectadas sobre el eje horizontal de la imagen: el eje se traza
    # con un punto auxiliar desplazado 1 px, por lo que la proyección difiere de la
    # distancia euclidiana en menos de 1e-4 mm (cos del pequeño giro del eje).
    assert result.total_length_mm == pytest.approx(140.0, abs=1e-4)
    assert result.body_depth_mm == pytest.approx(40.0, abs=1e-4)


def test_wrong_depth_changes_length_as_first_order_model_predicts(port, synthetic_air_profile):
    """Con una profundidad supuesta mayor que la real, C sobreestima la LT."""
    true_z, assumed_z = 110.0, 170.0
    plane = make_measurement_plane((0.0, 0.0, D_MM + TG_MM + assumed_z), (0.0, 0.0, 1.0), source="analytic-test")
    result = measure_c(
        "analytic-wrong-depth",
        synthetic_points(true_z),
        synthetic_air_profile,
        port,
        plane,
        replica_id="synthetic",
        image_shape=(3072, 4096, 3),
    )
    D = lambda z: D_MM + TG_MM / N_GLASS + z / N_WATER  # ecuación (16) de la tesis
    predicted = 140.0 * D(assumed_z) / D(true_z)
    assert result.total_length_mm > 140.0
    assert result.total_length_mm == pytest.approx(predicted, rel=0.01)
