import math

from app.component_builds.composite_direction import derive_nominal_planar_direction


def _row(angle, x=(1, 0, 0), y=(0, 1, 0), normal=(0, 0, 1)):
    fields = {"composite_orientation": {"normalized_value": angle}}
    for name, vector in (("x", x), ("y", y)):
        for axis, value in zip("xyz", vector):
            fields[f"composite_rosette_{name}_{axis}"] = {"read_status": "available", "raw_value": value}
    return {"fields": fields, "contour_planar_region": {"status": "derived_planar",
            "plane": {"normal": list(normal)}}}


def test_nominal_angles_preserve_zero_and_sign():
    vectors = [derive_nominal_planar_direction(_row(angle))["vector"] for angle in (0, 45, -45, 90)]
    assert vectors[0] == [1, 0, 0]
    assert vectors[1][1] == math.sqrt(0.5)
    assert vectors[2][1] == -math.sqrt(0.5)
    assert abs(vectors[3][0]) < 1e-12 and vectors[3][1] == 1


def test_flipped_normal_changes_local_positive_rotation_without_changing_raw_angle():
    result = derive_nominal_planar_direction(_row(45, normal=(0, 0, -1)))
    assert result["status"] == "derived_planar_nominal"
    assert result["angle_deg"] == 45
    assert result["handedness"] == "opposite"
    assert result["vector"][1] > 0


def test_degenerate_rosette_or_missing_geometry_is_not_fabricated():
    assert derive_nominal_planar_direction(_row(45, x=(0, 0, 1)))["status"] == "unavailable"
    assert derive_nominal_planar_direction(_row(45, x=(2, 0, 0)))["status"] == "unavailable"
    row = _row(45)
    row["contour_planar_region"] = {"status": "unsupported"}
    assert derive_nominal_planar_direction(row)["status"] == "unavailable"
