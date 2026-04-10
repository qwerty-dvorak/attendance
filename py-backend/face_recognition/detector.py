from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from insightface.model_zoo import model_zoo
from insightface.model_zoo.scrfd import SCRFD as SCRFDModel


@dataclass
class DetectionResult:
    bbox: np.ndarray
    score: float
    kps: np.ndarray | None


class SCRFDDetector:
    def __init__(
        self,
        model_path: str,
        input_size: int = 640,
        threshold: float = 0.45,
        allow_download: bool = False,
    ):
        self.model_path = str(Path(model_path).expanduser())
        self.input_size = input_size
        self.threshold = threshold

        self.model = None
        if self._is_scrfd_path(self.model_path):
            self.model = self._safe_get_scrfd(self.model_path)

        if self.model is None:
            self.model = self._safe_get_model(self.model_path)
        if self.model is None and allow_download and self._is_onnx(self.model_path):
            candidates = [
                Path(self.model_path).name,
                "scrfd_34g_bnkps.onnx",
                "scrfd_2.5g_bnkps.onnx",
            ]
            for name in candidates:
                self.model = self._safe_get_model(name, download=True)
                if self.model is not None:
                    break
        if self.model is None and self._is_onnx(self.model_path):
            self.model = self._safe_get_scrfd(self.model_path)
        if self.model is None:
            raise RuntimeError(
                "SCRFD model failed to load. Provide an ONNX SCRFD model path in "
                "SCRFD_ONNX_PATH (e.g. converted SCRFD-34G ONNX)."
            )
        self.model.prepare(
            ctx_id=-1,
            input_size=(input_size, input_size),
            det_thresh=float(threshold),
        )

    @staticmethod
    def _safe_get_model(name: str, **kwargs):
        try:
            return model_zoo.get_model(name, **kwargs)
        except Exception:
            return None

    @staticmethod
    def _safe_get_scrfd(path: str):
        try:
            return SCRFDModel(path)
        except Exception:
            return None

    @staticmethod
    def _is_onnx(path: str) -> bool:
        return path.lower().endswith(".onnx")

    @staticmethod
    def _is_scrfd_path(path: str) -> bool:
        lower = path.lower()
        return lower.endswith(".onnx") and "scrfd" in lower

    def detect(self, image_bgr: np.ndarray) -> list[DetectionResult]:
        try:
            bboxes, kpss = self.model.detect(image_bgr, threshold=self.threshold)
        except TypeError:
            bboxes, kpss = self.model.detect(
                image_bgr, input_size=(self.input_size, self.input_size)
            )
        if bboxes is None or len(bboxes) == 0:
            return []
        detections: list[DetectionResult] = []
        for idx, bbox in enumerate(bboxes):
            kps = None if kpss is None else kpss[idx]
            detections.append(
                DetectionResult(
                    bbox=bbox[:4].astype(np.float32),
                    score=float(bbox[4]),
                    kps=kps.astype(np.float32) if kps is not None else None,
                )
            )
        return detections
