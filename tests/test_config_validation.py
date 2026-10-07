import yaml
import pytest

from fish_morphometry.config import ConfigError, load_config


def _valid_config():
    return {
        "experiment": {"name": "test", "units": "mm"},
        "aruco": {
            "dictionary": "DICT_4X4_50",
            "method_a": {"id": 10, "side_mm": 30, "role": "glass", "plane": "glass_inner_surface"},
            "method_a_prime": {"id": 11, "side_mm": 30, "role": "coplanar", "plane": "replica_symmetry_plane"},
        },
        "quality": {"minimum_marker_side_px": 30, "maximum_side_cv": 0.1},
    }


def test_valid_config_loads(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(_valid_config()), encoding="utf-8")
    config = load_config(path)
    assert config.method_a.marker_role == "glass"
    assert config.method_a_prime.marker_role == "coplanar"
    assert config.longitudinal_axis_px == (1.0, 0.0)
    assert config.maximum_depth_section_angle_degrees == pytest.approx(5.0)


@pytest.mark.parametrize("mutation", [
    lambda payload: payload["aruco"].pop("method_a"),
    lambda payload: payload["experiment"].pop("units"),
    lambda payload: payload["aruco"].pop("dictionary"),
    lambda payload: payload["aruco"]["method_a"].update({"side_mm": -1}),
    lambda payload: payload["aruco"]["method_a_prime"].update({"id": 10}),
    lambda payload: payload["experiment"].update({"units": "furlong"}),
    lambda payload: payload["aruco"]["method_a"].update({"role": "coplanar"}),
    lambda payload: payload["aruco"]["method_a_prime"].update({"coplanarity_error_mm": -1}),
    lambda payload: payload.update({"measurements": {"longitudinal_axis_px": [0, 0]}}),
    lambda payload: payload.update({"measurements": {"maximum_depth_section_angle_degrees": 90}}),
])
def test_invalid_config_is_rejected(tmp_path, mutation):
    payload = _valid_config()
    mutation(payload)
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
