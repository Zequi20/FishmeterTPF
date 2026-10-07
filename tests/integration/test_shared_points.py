from fish_morphometry.methods.a import measure_a
from fish_morphometry.methods.a_prime import measure_a_prime
from fish_morphometry.methods.b import measure_b
from fish_morphometry.methods.c import measure_c


def test_same_annotation_object_is_reused_by_a_aprime_b_and_c(
    points_px, image_shape, marker_glass, marker_coplanar, b_profile, rail_reference, air_profile, flat_port, measurement_plane
):
    a = measure_a("shared", marker_glass, points_px, 30.0, image_shape=image_shape)
    ap = measure_a_prime("shared", marker_coplanar, points_px, 30.0, image_shape=image_shape)
    b = measure_b("shared", points_px, b_profile, rail_reference, 100.0, 0.0, replica_id="r", image_shape=image_shape)
    c = measure_c("shared", points_px, air_profile, flat_port, measurement_plane, replica_id="r", image_shape=image_shape)
    assert a.points_px == ap.points_px == b.points_px == c.points_px == points_px
    assert all(result.image_id == "shared" for result in (a, ap, b, c))
    assert all(result.units == "mm" for result in (b, c))
    assert c.metadata["uses_aruco"] is False
    assert b.metadata["uses_aruco"] is False
