"""Geometry classifier tests use synthetic 21-point landmarks, no webcam."""
import pytest

from gesture.gesture_recognition import classify_gesture


def pose(extended):
    """Build upright 2D hand geometry with near-straight extended finger chains."""
    points = [(0.50, 0.78, 0.0) for _ in range(21)]
    points[0] = (0.50, 0.82, 0.0)  # wrist
    points[1] = (0.48, 0.76, 0.0)
    points[2] = (0.45, 0.71, 0.0)
    points[3] = (0.43, 0.65, 0.0)
    # A tucked thumb tip stays close to its base; a raised tip models thumbs-up.
    points[4] = (0.41, 0.59, 0.0) if "thumb" in extended else (0.48, 0.73, 0.0)
    finger_specs = {
        "index": (5, 6, 7, 8, 0.42),
        "middle": (9, 10, 11, 12, 0.49),
        "ring": (13, 14, 15, 16, 0.56),
        "pinky": (17, 18, 19, 20, 0.63),
    }
    for name, (mcp, pip, dip, tip, x) in finger_specs.items():
        if name in extended:
            points[mcp] = (x, 0.65, 0.0)
            points[pip] = (x, 0.51, 0.0)
            points[dip] = (x, 0.40, 0.0)
            points[tip] = (x, 0.29, 0.0)
        else:
            points[mcp] = (x, 0.65, 0.0)
            points[pip] = (x, 0.70, 0.0)
            points[dip] = (x, 0.75, 0.0)
            points[tip] = (x, 0.77, 0.0)
    return points


@pytest.mark.parametrize(("fingers", "expected"), [
    ({"thumb", "index", "middle", "ring", "pinky"}, "OPEN_PALM"),
    (set(), "FIST"),
    ({"thumb"}, "THUMBS_UP"),
    ({"index", "middle"}, "VICTORY"),
    ({"index"}, "POINTING"),
])
def test_recognizes_supported_clear_poses(fingers, expected):
    result = classify_gesture(pose(fingers), "Right")
    assert result.gesture == expected
    assert result.reason


def test_absent_malformed_and_ambiguous_poses_are_unrecognized():
    assert classify_gesture(None).gesture is None
    assert classify_gesture([(0.0, 0.0, 0.0)] * 5).gesture is None
    assert classify_gesture(pose({"index", "ring"})).gesture is None


def test_result_exposes_finger_state_diagnostics():
    result = classify_gesture(pose({"index"}))
    assert result.finger_states["index"] is True
    assert result.finger_states["middle"] is False
