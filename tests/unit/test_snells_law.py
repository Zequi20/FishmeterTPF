import math

import numpy as np
import pytest

from fish_morphometry.geometry.snells_law import TotalInternalReflectionError, refract_direction


def test_normal_incidence_and_equal_indices_preserve_direction():
    assert refract_direction((0, 0, 1), (0, 0, 1), 1.0, 1.5) == pytest.approx((0, 0, 1))
    assert refract_direction((0.3, 0, math.sqrt(1 - 0.3**2)), (0, 0, 1), 1.0, 1.0) == pytest.approx(
        (0.3, 0, math.sqrt(1 - 0.3**2))
    )


def test_oblique_incidence_satisfies_snell_and_is_normalized():
    incident = (math.sin(math.radians(30)), 0, math.cos(math.radians(30)))
    transmitted = refract_direction(incident, (0, 0, 1), 1.0, 1.5)
    theta_t = math.asin(transmitted[0])
    assert math.sin(math.radians(30)) == pytest.approx(1.5 * math.sin(theta_t), abs=1e-10)
    assert np.linalg.norm(transmitted) == pytest.approx(1.0)


def test_total_internal_reflection_is_controlled_error():
    with pytest.raises(TotalInternalReflectionError):
        refract_direction((0.9, 0, math.sqrt(1 - 0.9**2)), (0, 0, 1), 1.5, 1.0)


def test_inverted_normal_is_rejected_explicitly():
    with pytest.raises(ValueError, match="normal"):
        refract_direction((0, 0, 1), (0, 0, -1), 1.0, 1.5)
