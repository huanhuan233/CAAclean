import math

from app.tube.section import native_concentric_profile


def profile(inner_center=(0, 0), inner_radius=2.5, outer_radius=3):
    return {"axis": {"status": "verified_orthonormal"}, "elements": [
        {"element_id": "outer", "construction": False, "kind": "circle",
         "center_2d_mm": [0, 0], "radius_mm": outer_radius,
         "parameter_range_raw": [0, 2 * math.pi]},
        {"element_id": "inner", "construction": False, "kind": "circle",
         "center_2d_mm": list(inner_center), "radius_mm": inner_radius,
         "parameter_range_raw": [0, 2 * math.pi]},
    ]}


def test_native_profile_is_nominal_not_solid_wall_measurement():
    result = native_concentric_profile(profile())
    assert result["status"] == "native_profile_annulus"
    assert result["outer_diameter_mm"] == 6
    assert result["inner_diameter_mm"] == 5
    assert result["nominal_wall_mm"] == 0.5
    assert "solid_wall_unverified" in result["scope"]


def test_eccentric_or_partial_profile_is_not_a_concentric_tube():
    assert native_concentric_profile(profile(inner_center=(0.2, 0)))["status"] == "unsupported_profile"
    sketch = profile()
    sketch["elements"][0]["parameter_range_raw"] = [0, math.pi]
    assert native_concentric_profile(sketch)["outer_diameter_mm"] is None


def test_missing_center_and_extra_design_geometry_are_rejected():
    sketch = profile()
    del sketch["elements"][0]["center_2d_mm"]
    assert native_concentric_profile(sketch)["status"] == "unsupported_profile"
    sketch = profile()
    sketch["elements"].append({"kind": "line", "construction": False})
    assert native_concentric_profile(sketch)["status"] == "unsupported_profile"
