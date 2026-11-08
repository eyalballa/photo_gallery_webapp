"""Face detection: MediaPipe Face Landmarker behind a small protocol so tests can use fakes."""

import math
import threading
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from wall.effects.base import Face, Landmarks, Point, Rect

MODEL = Path(__file__).resolve().parents[1] / "models" / "face_landmarker.task"

# MediaPipe face mesh indices (478-point model with irises)
IRIS_A, IRIS_B = 468, 473
NOSE_TIP, LIP_UPPER, LIP_LOWER, FOREHEAD, CHIN = 1, 13, 14, 10, 152


class FaceDetector(Protocol):
    def detect(self, img: Image.Image) -> list[Face]: ...


def face_from_points(pts: list[tuple[float, float]]) -> Face:
    """Builds a Face from landmark pixel coordinates (indexable by mesh index)."""
    a, b = Point(x=pts[IRIS_A][0], y=pts[IRIS_A][1]), Point(x=pts[IRIS_B][0], y=pts[IRIS_B][1])
    left, right = (a, b) if a.x <= b.x else (b, a)
    dx, dy = right.x - left.x, right.y - left.y
    size = math.hypot(dx, dy)
    roll = math.atan2(dy, dx)
    nose = Point(x=pts[NOSE_TIP][0], y=pts[NOSE_TIP][1])
    mid = Point(x=(left.x + right.x) / 2, y=(left.y + right.y) / 2)
    # nose offset from the eye midpoint, measured along the eye line, in eye-distance units
    yaw = ((nose.x - mid.x) * dx + (nose.y - mid.y) * dy) / (size * size) if size else 0.0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return Face(
        box=Rect(x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys)),
        landmarks=Landmarks(
            left_eye=left,
            right_eye=right,
            nose_tip=nose,
            mouth_center=Point(x=(pts[LIP_UPPER][0] + pts[LIP_LOWER][0]) / 2, y=(pts[LIP_UPPER][1] + pts[LIP_LOWER][1]) / 2),
            forehead=Point(x=pts[FOREHEAD][0], y=pts[FOREHEAD][1]),
            chin=Point(x=pts[CHIN][0], y=pts[CHIN][1]),
        ),
        roll=roll,
        yaw=yaw,
        size=size,
    )


class MediaPipeDetector:
    def __init__(self, model: Path = MODEL, max_faces: int = 10):
        from mediapipe.tasks.python import BaseOptions, vision

        opts = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model)),
            num_faces=max_faces,
            running_mode=vision.RunningMode.IMAGE,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(opts)
        self._lock = threading.Lock()  # the landmarker is not safe to call from two threads at once

    def _detect_crop(self, rgb: np.ndarray, x0: int, y0: int) -> list[list[tuple[float, float]]]:
        import mediapipe as mp

        h, w = rgb.shape[:2]
        with self._lock:
            result = self._landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
        return [[(x0 + p.x * w, y0 + p.y * h) for p in lm] for lm in result.face_landmarks]

    def detect(self, img: Image.Image) -> list[Face]:
        """The landmarker's detector is short-range: it misses faces that are small in the frame (group
        shots). So we also scan overlapping 2x2 and 3x3 tiles and merge the results."""
        rgb = np.asarray(img.convert("RGB"))
        h, w = rgb.shape[:2]
        found: list[Face] = []
        for crop in tiles(w, h):
            x0, y0, x1, y1 = crop
            for pts in self._detect_crop(rgb[y0:y1, x0:x1], x0, y0):
                face = face_from_points(pts)
                if cut_by_crop(face, crop, w, h) or any(same_face(face, f) for f in found):
                    continue
                found.append(face)
        return found


def tiles(w: int, h: int, overlap: float = 0.25) -> list[tuple[int, int, int, int]]:
    """The full image, then n×n grids (n=2,3) whose cells overlap by `overlap` of a cell."""
    out = [(0, 0, w, h)]
    for n in (2, 3):
        cw, ch = w / (n - (n - 1) * overlap), h / (n - (n - 1) * overlap)
        sx, sy = cw * (1 - overlap), ch * (1 - overlap)
        out += [(round(i * sx), round(j * sy), round(i * sx + cw), round(j * sy + ch)) for j in range(n) for i in range(n)]
    return out


def same_face(a: Face, b: Face) -> bool:
    """Two detections of one face: eye midpoints closer than half an eye distance."""
    ma, mb = a.landmarks.left_eye, b.landmarks.left_eye
    return math.hypot(ma.x - mb.x, ma.y - mb.y) < 0.5 * max(a.size, b.size)


def cut_by_crop(face: Face, crop: tuple[int, int, int, int], w: int, h: int, margin: float = 2) -> bool:
    """True if the face's box touches an inner edge of the crop (landmarks of a cut-off face are unreliable)."""
    x0, y0, x1, y1 = crop
    b = face.box
    return (
        (x0 > 0 and b.x <= x0 + margin) or (y0 > 0 and b.y <= y0 + margin)
        or (x1 < w and b.x + b.w >= x1 - margin) or (y1 < h and b.y + b.h >= y1 - margin)
    )


class NoFaces:
    """Detector that finds nothing; used when effects are not wanted (and in tests)."""

    def detect(self, img: Image.Image) -> list[Face]:
        return []
