import math

import pytest
from PIL import Image

from wall.config import EffectsConfig
from wall.effects import EFFECTS, choose_effect
from wall.effects.base import Placement, Point, paste_position, stable_seed, up_vector
from wall.faces import cut_by_crop, face_from_points, same_face, tiles
from wall.process import process_one

W = {"glasses": 25, "mustache": 25, "party_hat": 25, "vintage": 25}


def face(cx=100.0, cy=100.0, eye_dist=40.0, roll=0.0, nose_dx=0.0):
    """A face from synthetic landmarks: eyes at (cx±d/2, cy) rotated by roll, nose below the midpoint."""
    pts = [(cx, cy)] * 478
    c, s = math.cos(roll), math.sin(roll)

    def rot(dx, dy):
        return (cx + dx * c - dy * s, cy + dx * s + dy * c)

    pts[468], pts[473] = rot(-eye_dist / 2, 0), rot(eye_dist / 2, 0)
    pts[1] = rot(nose_dx, 25)
    pts[13], pts[14], pts[10], pts[152] = rot(0, 38), rot(0, 42), rot(0, -45), rot(0, 70)
    return face_from_points(pts)


def test_face_geometry_from_landmarks():
    f = face(eye_dist=40, roll=math.radians(30), nose_dx=8)

    assert round(f.size, 6) == 40
    assert round(math.degrees(f.roll), 6) == 30
    assert round(f.yaw, 6) == 0.2  # 8 px of nose offset / 40 px eye distance


def test_effect_choice_is_deterministic_per_media_id():
    picks = [choose_effect("photo-17", 0, [face()], W, 0.35)[0] for _ in range(3)]

    assert len(set(picks)) == 1


def test_reroll_salt_changes_the_seed():
    assert stable_seed("photo-17", 0) != stable_seed("photo-17", 1)


def test_no_faces_means_no_effect():
    assert choose_effect("x", 0, [], W, 0.35)[0] is None


def test_turned_faces_only_get_non_accessory_effects():
    picks = {choose_effect(f"id{i}", 0, [face(nose_dx=30)], W, 0.35)[0] for i in range(40)}

    assert picks == {"vintage"}


def test_zero_weight_disables_an_effect():
    weights = {**W, "glasses": 0, "mustache": 0, "vintage": 0}

    picks = {choose_effect(f"id{i}", 0, [face()], weights, 0.35)[0] for i in range(20)}

    assert picks == {"party_hat"}


def test_up_vector_follows_head_roll():
    level, tilted = up_vector(face()), up_vector(face(roll=math.radians(90)))

    assert (round(level.x, 6), round(level.y, 6)) == (0, -1)
    assert (round(tilted.x, 6), round(tilted.y, 6)) == (1, 0)


def test_anchor_lands_on_target_without_rotation():
    p = Placement(target=Point(x=100, y=50), width=80, angle=0, anchor=Point(x=0.5, y=1.0))

    corner, w, h = paste_position(p, asset_w=160, asset_h=200)

    assert (corner.x, corner.y, w, h) == (60, -50, 80, 100)  # bottom-centre of the 80x100 asset at (100, 50)


def test_anchor_lands_on_target_rotated_90_degrees():
    p = Placement(target=Point(x=100, y=50), width=80, angle=math.pi / 2, anchor=Point(x=0.5, y=1.0))

    corner, w, h = paste_position(p, asset_w=160, asset_h=200)

    # rotated clockwise, the asset lies on its side (100 wide, 80 tall) with its bottom-centre at the left middle
    assert (round(corner.x, 6), round(corner.y, 6), round(w, 6), round(h, 6)) == (100, 10, 100, 80)


def test_tiles_cover_full_image_then_overlapping_grids():
    t = tiles(1000, 800)

    assert len(t) == 1 + 4 + 9
    assert t[0] == (0, 0, 1000, 800)
    assert t[1:5] == [(0, 0, 571, 457), (429, 0, 1000, 457), (0, 343, 571, 800), (429, 343, 1000, 800)]


def test_same_face_detected_twice_is_merged():
    assert same_face(face(100, 100), face(110, 104))
    assert not same_face(face(100, 100), face(160, 100))


def test_face_cut_by_inner_crop_edge_is_rejected():
    f = face(cx=500, cy=300)  # box spans x 480..520

    assert cut_by_crop(f, (0, 0, 510, 800), 1000, 800)
    assert not cut_by_crop(f, (0, 0, 1000, 800), 1000, 800)


class OneFace:
    def detect(self, img):
        return [face(cx=img.width / 2, cy=img.height / 2, eye_dist=80)]


@pytest.fixture
def original(tmp_path):
    p = tmp_path / "in.jpg"
    Image.new("RGB", (400, 300), "white").save(p)
    return p


def test_process_applies_an_effect_and_saves(original, tmp_path):
    out = tmp_path / "out.jpg"

    f = process_one("photo-1", original, out, OneFace(), EffectsConfig())

    assert (f.status, f.faces, f.width, f.height) == ("ready", 1, 400, 300)
    assert f.effect in EFFECTS and out.exists()


def test_effect_failure_falls_back_to_unedited_photo(original, tmp_path, monkeypatch):
    def boom(*a):
        raise RuntimeError("bad svg")

    for e in EFFECTS.values():
        monkeypatch.setattr(e, "apply", boom)

    f = process_one("photo-1", original, tmp_path / "out.jpg", OneFace(), EffectsConfig())

    assert (f.status, f.effect, f.error) == ("ready", None, "effect failed: bad svg")


def test_faces_below_min_size_get_no_effect(original, tmp_path):
    class TinyFace:
        def detect(self, img):
            return [face(eye_dist=10)]  # box ~20 px wide

    f = process_one("p", original, tmp_path / "o.jpg", TinyFace(), EffectsConfig(min_face_px=60))

    assert (f.faces, f.effect) == (0, None)
