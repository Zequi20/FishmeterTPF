import pytest
import yaml

from fish_morphometry.geometry.refractive_port import (
    FlatPortParameters,
    RefractivePortError,
    load_manual_flat_port,
    make_flat_port_parameters,
    trace_refracted_ray,
)
from fish_morphometry.methods.c import measure_c


def test_q1_q2_belong_to_parallel_interfaces(flat_port):
    traced = trace_refracted_ray((0.1, 0, 1), flat_port)
    assert traced.q1_camera_mm[2] == pytest.approx(flat_port.interface_distance_mm)
    assert traced.q2_camera_mm[2] == pytest.approx(flat_port.interface_distance_mm + flat_port.glass_thickness_mm)
    assert traced.first_interface_residual_mm == pytest.approx(0.0)
    assert traced.second_interface_residual_mm == pytest.approx(0.0)


def test_axis_ray_does_not_deviate(flat_port):
    traced = trace_refracted_ray((0, 0, 1), flat_port)
    assert traced.v_glass == pytest.approx((0, 0, 1))
    assert traced.v_water == pytest.approx((0, 0, 1))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"interface_distance_mm": -1},
        {"glass_thickness_mm": -1},
        {"n_air": 0},
        {"n_glass": -1},
        {"n_water": 0},
    ],
)
def test_port_rejects_physically_impossible_parameters(kwargs):
    base = dict(
        normal_camera=(0, 0, 1),
        interface_distance_mm=100,
        glass_thickness_mm=10,
        n_air=1,
        n_glass=1.5,
        n_water=1.333,
    )
    base.update(kwargs)
    with pytest.raises(RefractivePortError):
        make_flat_port_parameters(**base)


def test_non_mm_units_are_rejected_by_manual_port():
    with pytest.raises(RefractivePortError):
        FlatPortParameters(
            port_normal=(0, 0, 1), interface_distance_mm=100, glass_thickness_mm=10,
            n_air=1, n_glass=1.5, n_water=1.333, units="cm",
        )


def test_refracted_ray_parallel_to_measurement_plane_is_rejected(air_profile, flat_port, points_px):
    with pytest.raises(ValueError, match="paralelo"):
        measure_c(
            "parallel", points_px, air_profile, flat_port,
            {"point_camera_mm": (0, 0, 200), "normal_camera": (1, 0, 0)},
            replica_id="r",
            image_shape=(200, 200, 3),
        )


def test_port_normal_is_normalized_and_flagged():
    port = make_flat_port_parameters(
        normal_camera=(0, 0, 2), interface_distance_mm=100, glass_thickness_mm=10,
        n_air=1, n_glass=1.5, n_water=1.333,
    )
    assert port.port_normal == pytest.approx((0, 0, 1))
    assert port.normal_was_normalized is True


def test_port_and_plane_hashes_detect_tampering(tmp_path, air_profile, points_px):
    port = make_flat_port_parameters(
        normal_camera=(0, 0, 1), interface_distance_mm=100, glass_thickness_mm=10,
        n_air=1, n_glass=1.5, n_water=1.333,
    )
    payload = {"flat_port": port.to_dict()}
    path = tmp_path / "port.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    loaded = load_manual_flat_port(path)
    assert loaded.port_hash == port.port_hash
    payload["flat_port"]["interface_distance_mm"] = 101
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(RefractivePortError, match="hash"):
        load_manual_flat_port(path)

    with pytest.raises(ValueError, match="hash"):
        measure_c(
            "tampered-plane",
            points_px,
            air_profile,
            port,
            {
                "point_camera_mm": (0, 0, 200),
                "normal_camera": (0, 0, 1),
                "plane_hash": "invalid",
            },
            replica_id="r",
        )
