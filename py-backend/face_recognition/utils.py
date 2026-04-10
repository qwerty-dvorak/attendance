from __future__ import annotations

import cv2
import numpy as np

ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def l2_normalize(embedding: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(embedding)
    if norm <= 1e-12:
        return embedding
    return embedding / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a_norm = l2_normalize(a)
    b_norm = l2_normalize(b)
    return float(np.dot(a_norm, b_norm))


def align_face(image_bgr: np.ndarray, kps: np.ndarray) -> np.ndarray:
    if kps is None or len(kps) != 5:
        raise ValueError("Five keypoints are required for alignment")
    transform, _ = cv2.estimateAffinePartial2D(
        kps.astype(np.float32), ARCFACE_TEMPLATE, method=cv2.LMEDS
    )
    if transform is None:
        raise ValueError("Failed to estimate alignment transform")
    return cv2.warpAffine(image_bgr, transform, (112, 112), borderValue=0.0)


def crop_face(image_bgr: np.ndarray, bbox: np.ndarray) -> np.ndarray:
    x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
    h, w = image_bgr.shape[:2]
    x1 = max(0, min(x1, w - 1))
    y1 = max(0, min(y1, h - 1))
    x2 = max(x1 + 1, min(x2, w))
    y2 = max(y1 + 1, min(y2, h))
    face = image_bgr[y1:y2, x1:x2]
    if face.size == 0:
        raise ValueError("Empty crop from bounding box")
    return cv2.resize(face, (112, 112), interpolation=cv2.INTER_LINEAR)
