from math import pi

from wuta_msgs.msg import Cone

from simulator_bringup.simulated_cone_colorizer import (
    _lidar_to_map_xy,
    _nearest_truth_color,
)
from simulator_bringup.track_truth_map_publisher import _resolve_track_file


def test_lidar_to_map_xy_applies_pose_yaw():
    x, y = _lidar_to_map_xy(2.0, 0.0, 10.0, 20.0, pi / 2.0)
    assert abs(x - 10.0) < 1e-9
    assert abs(y - 22.0) < 1e-9


def test_nearest_truth_color_matches_within_gate():
    truth = [
        (2.0, 1.0, Cone.COLOR_BLUE),
        (2.0, -1.0, Cone.COLOR_YELLOW),
    ]
    assert _nearest_truth_color(2.1, 0.9, truth, 0.5) == Cone.COLOR_BLUE
    assert _nearest_truth_color(2.1, -0.9, truth, 0.5) == Cone.COLOR_YELLOW


def test_nearest_truth_color_rejects_distant_detection():
    truth = [(2.0, 1.0, Cone.COLOR_BLUE)]
    assert _nearest_truth_color(4.0, 1.0, truth, 0.5) is None


def test_resolve_track_file_from_wuta_root(tmp_path, monkeypatch):
    tracks_dir = tmp_path / "tracks"
    tracks_dir.mkdir()
    expected = tracks_dir / "track2.yaml"
    expected.write_text("track: {}\n", encoding="utf-8")
    monkeypatch.setenv("WUTA_ROOT", str(tmp_path))

    assert _resolve_track_file("track2") == expected
