"""Geometría efectiva en coordenadas de cámara para el método B."""

from .rail_plane import (
    RailGeometryError,
    RailPlaneReference,
    build_measurement_plane,
    estimate_rail_reference_from_images,
    estimate_rail_reference_from_observations,
)
from .ray_plane import (
    RayPlaneError,
    image_axis_to_plane_direction,
    intersect_ray_line_plane,
    intersect_ray_plane,
    intersect_ray_with_plane,
    intersect_ray_with_measurement_plane,
    undistort_points_to_rays,
)
from .refractive_port import (
    FlatPortParameters,
    MeasurementPlane,
    RefractedRay,
    RefractivePortError,
    make_measurement_plane,
    measurement_plane_from_rail,
    trace_refracted_ray,
)
from .snells_law import SnellError, TotalInternalReflectionError, normalize_vector, refract_direction

__all__ = [
    "RailGeometryError",
    "RailPlaneReference",
    "RayPlaneError",
    "build_measurement_plane",
    "estimate_rail_reference_from_images",
    "estimate_rail_reference_from_observations",
    "FlatPortParameters",
    "MeasurementPlane",
    "RefractedRay",
    "RefractivePortError",
    "intersect_ray_plane",
    "image_axis_to_plane_direction",
    "intersect_ray_line_plane",
    "intersect_ray_with_plane",
    "intersect_ray_with_measurement_plane",
    "refract_direction",
    "normalize_vector",
    "make_measurement_plane",
    "measurement_plane_from_rail",
    "SnellError",
    "TotalInternalReflectionError",
    "trace_refracted_ray",
    "undistort_points_to_rays",
]
