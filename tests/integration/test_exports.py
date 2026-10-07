import csv
import json

from fish_morphometry.io.exporters import export_method_results, export_results_csv
from fish_morphometry.methods.a import measure_a
from fish_morphometry.methods.a_prime import measure_a_prime
from fish_morphometry.methods.b import measure_b
from fish_morphometry.methods.c import measure_c_safe


def test_json_csv_export_is_consistent_and_keeps_failure_reason(
    tmp_path, points_px, image_shape, marker_glass, marker_coplanar, air_profile, flat_port, measurement_plane
):
    a = measure_a("export-image", marker_glass, points_px, 30, image_shape=image_shape)
    ap = measure_a_prime("export-image", marker_coplanar, points_px, 30, image_shape=image_shape)
    c = measure_c_safe("export-image", {"p1": (100, 100)}, air_profile, flat_port, measurement_plane, replica_id="r")
    paths = export_method_results(tmp_path, "export-image", a, ap, result_c=c)
    payload = json.loads(paths["C"].read_text(encoding="utf-8"))
    assert payload["image_id"] == "export-image"
    assert payload["points_source"] == "shared_annotation"
    assert payload["body_depth_selection"] is None
    assert payload["quality"]["status"] == "ERROR"
    assert payload["exclusion_reason"]
    with paths["master"].open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["method"] for row in rows} == {"A", "A_PRIME", "C"}
    assert all(row["image_id"] == "export-image" for row in rows)
    direct_rows = {row["method"]: row for row in rows if row["method"] in {"A", "A_PRIME"}}
    assert direct_rows["A"]["metric_transform"] == "uniform_scale_approximation"
    assert direct_rows["A_PRIME"]["metric_transform"] == "planar_homography"
    assert direct_rows["A_PRIME"]["longitudinal_axis_metric"]
    assert direct_rows["A_PRIME"]["points_metric_mm"]
    assert direct_rows["A"]["body_depth_selection"] == (
        "manual_section_not_automatically_verified_global_max"
    )
    assert direct_rows["A_PRIME"]["body_depth_selection"] == (
        "manual_section_not_automatically_verified_global_max"
    )


def test_export_does_not_overwrite_other_image(tmp_path, points_px, image_shape, marker_glass):
    first = measure_a("one", marker_glass, points_px, 30, image_shape=image_shape)
    second = measure_a("two", marker_glass, points_px, 30, image_shape=image_shape)
    export_results_csv((first,), tmp_path / "master_one.csv")
    export_results_csv((second,), tmp_path / "master_two.csv")
    assert "one" in (tmp_path / "master_one.csv").read_text(encoding="utf-8")
    assert "two" in (tmp_path / "master_two.csv").read_text(encoding="utf-8")


def test_b_export_keeps_projected_diagnostics_and_geometry_hashes(
    tmp_path, points_px, image_shape, b_profile, rail_reference
):
    result = measure_b(
        "b-export",
        points_px,
        b_profile,
        rail_reference,
        100,
        0,
        replica_id="r",
        image_shape=image_shape,
    )
    path = export_results_csv((result,), tmp_path / "b.csv")
    with path.open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["total_length_euclidean_mm"]
    assert row["longitudinal_axis_camera"]
    assert row["delta_rail_mm"] == "0.0"
    assert row["calibration_context_hash"] == b_profile.calibration_context_hash
    assert row["rail_reference_hash"] == rail_reference.reference_hash
