from fish_morphometry.domain.models import MarkerObservation
from fish_morphometry.methods.a import measure_a
from fish_morphometry.methods.c import measure_c_safe
from fish_morphometry.ui.results_panel import format_method_result


def test_method_result_summary_is_empty_before_calculation():
    assert format_method_result(None) == "Aún no se calculó este método."


def test_method_result_summary_shows_measurements_status_and_warnings():
    marker = MarkerObservation(
        marker_id=10,
        corners=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
        center=(50.0, 50.0),
        area_px2=10000.0,
        side_lengths_px=(100.0, 100.0, 100.0, 100.0),
        side_mean_px=100.0,
        side_cv=0.0,
    )
    result = measure_a(
        "fish",
        marker,
        {
            "p1": (10.0, 20.0),
            "p2": (90.0, 20.0),
            "p3": (40.0, 10.0),
            "p4": (40.0, 50.0),
        },
        30.0,
        image_shape=(120, 120, 3),
    )

    summary = format_method_result(result)

    assert "Longitud total (LT): 24.000 mm" in summary
    assert "Profundidad corporal: 12.000 mm (sección válida)" in summary
    assert f"Estado: {result.quality.status}" in summary
    assert "Advertencias:" in summary


def test_method_result_summary_explains_excluded_calculation(
    air_profile, flat_port, measurement_plane
):
    result = measure_c_safe(
        "missing",
        {"p1": (100.0, 100.0)},
        air_profile,
        flat_port,
        measurement_plane,
        replica_id="replica",
    )

    summary = format_method_result(result)

    assert summary.startswith("Estado: ERROR")
    assert "Resultado no disponible:" in summary
    assert result.exclusion_reason in summary
