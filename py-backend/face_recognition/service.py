from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np

from models import Student

from .detector import DetectionResult, SCRFDDetector
from .embedders import (
    available_embedder_names,
    build_embedders,
    choose_default_embedder,
)
from .utils import align_face, cosine_similarity, crop_face


@dataclass
class MatchResult:
    student_id: int | None
    student_name: str | None
    roll_no: str | None
    confidence: float
    embedder: str
    bbox: list[float]
    score: float


class FaceRecognitionService:
    def __init__(self, config):
        self.config = config
        cfg = self._cfg
        detector_model = (
            cfg("SCRFD_ONNX_PATH")
            if cfg("SCRFD_ONNX_PATH") and os.path.exists(cfg("SCRFD_ONNX_PATH"))
            else cfg("SCRFD_PTH_PATH")
        )
        self.detector = SCRFDDetector(
            model_path=detector_model,
            input_size=int(cfg("DETECTION_INPUT_SIZE", 640)),
            threshold=float(cfg("DETECTION_THRESHOLD", 0.45)),
            allow_download=bool(cfg("SCRFD_ALLOW_DOWNLOAD", False)),
        )

        self.embedders = build_embedders(config)
        self.default_embedder_name, _ = choose_default_embedder(
            self.embedders, str(cfg("DEFAULT_EMBEDDER", "lvface_onnx"))
        )

    def _cfg(self, key: str, default=None):
        if isinstance(self.config, dict):
            return self.config.get(key, default)
        return getattr(self.config, key, default)

    def _read_image(self, image_path: str) -> np.ndarray:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        return image

    def _face_chip(self, image: np.ndarray, detection: DetectionResult) -> np.ndarray:
        if detection.kps is not None and len(detection.kps) == 5:
            return align_face(image, detection.kps)
        return crop_face(image, detection.bbox)

    def detect_faces(self, image_path: str) -> list[DetectionResult]:
        image = self._read_image(image_path)
        return self.detector.detect(image)

    def extract_embedding(
        self, image_path: str, embedder_name: str | None = None
    ) -> tuple[np.ndarray, str, float]:
        image = self._read_image(image_path)
        detections = self.detector.detect(image)
        if not detections:
            raise ValueError("No face detected in the image")

        best = max(detections, key=lambda d: d.score)
        face_chip = self._face_chip(image, best)
        name = embedder_name or self.default_embedder_name
        if name not in self.embedders:
            raise ValueError(f"Unknown embedder: {name}")
        embedding = self.embedders[name].embed(face_chip)
        return embedding.astype(np.float32), name, float(best.score)

    def register_student_embedding(
        self, student: Student, image_path: str, embedder_name: str | None = None
    ) -> tuple[str, float]:
        embedding, used_embedder, score = self.extract_embedding(
            image_path, embedder_name
        )
        student.set_embedding(embedding, used_embedder)
        student.face_image_path = image_path
        return used_embedder, score

    def match_students(
        self, image_path: str, students: list[Student], embedder_name: str | None = None
    ) -> list[MatchResult]:
        image = self._read_image(image_path)
        detections = self.detector.detect(image)
        if not detections:
            return []

        requested_embedder = embedder_name or self.default_embedder_name
        if requested_embedder not in self.embedders:
            requested_embedder = self.default_embedder_name

        candidates = []
        for s in students:
            emb = s.get_embedding()
            if emb is None:
                continue
            candidates.append((s, emb.astype(np.float32)))

        matches: list[MatchResult] = []
        for det in detections:
            face_chip = self._face_chip(image, det)
            query_embedding = self.embedders[requested_embedder].embed(face_chip)

            best_student = None
            best_score = -1.0
            for student, ref_embedding in candidates:
                score = cosine_similarity(query_embedding, ref_embedding)
                if score > best_score:
                    best_score = score
                    best_student = student

            accepted = best_student is not None and best_score >= float(
                self._cfg("RECOGNITION_THRESHOLD", 0.35)
            )
            matches.append(
                MatchResult(
                    student_id=best_student.id if accepted else None,
                    student_name=best_student.name if accepted else None,
                    roll_no=best_student.roll_no if accepted else None,
                    confidence=float(best_score),
                    embedder=requested_embedder,
                    bbox=[float(v) for v in det.bbox],
                    score=float(det.score),
                )
            )
        return matches

    def benchmark_embedders(
        self, samples: list[dict], students: list[Student] | None = None
    ) -> dict[str, dict[str, float]]:
        if not samples:
            return {}

        use_labels = any(
            sample.get("expected_student_id") is not None
            or sample.get("expected_roll_no") is not None
            for sample in samples
        )

        def build_gallery(embedder_name: str):
            gallery = []
            if not students:
                return gallery
            for student in students:
                if not student.face_image_path or not os.path.exists(
                    student.face_image_path
                ):
                    emb = student.get_embedding()
                    if emb is not None:
                        gallery.append((student, emb.astype(np.float32)))
                    continue
                try:
                    image = self._read_image(student.face_image_path)
                    dets = self.detector.detect(image)
                    if not dets:
                        continue
                    best = max(dets, key=lambda d: d.score)
                    chip = self._face_chip(image, best)
                    emb = self.embedders[embedder_name].embed(chip)
                    gallery.append((student, emb.astype(np.float32)))
                except Exception:
                    emb = student.get_embedding()
                    if emb is not None:
                        gallery.append((student, emb.astype(np.float32)))
            return gallery

        report: dict[str, dict[str, float]] = {}
        for name, embedder in self.embedders.items():
            detected = 0
            embedded = 0
            conf_sum = 0.0
            self_gallery: list[np.ndarray] = []
            self_queries: list[np.ndarray] = []
            labeled_total = 0
            labeled_correct = 0
            gallery = build_gallery(name) if use_labels else []

            for sample in samples:
                path = sample.get("image_path")
                if not path:
                    continue
                try:
                    image = self._read_image(path)
                    detections = self.detector.detect(image)
                    if not detections:
                        continue
                    detected += 1
                    best = max(detections, key=lambda d: d.score)
                    chip = self._face_chip(image, best)
                    query = embedder.embed(chip)
                    embedded += 1
                    conf_sum += float(best.score)
                    self_gallery.append(query.astype(np.float32))

                    flip_chip = cv2.flip(chip, 1)
                    flip_query = embedder.embed(flip_chip)
                    self_queries.append(flip_query.astype(np.float32))

                    if use_labels and gallery:
                        expected_id = sample.get("expected_student_id")
                        expected_roll = sample.get("expected_roll_no")
                        if expected_id is not None or expected_roll is not None:
                            labeled_total += 1
                            winner = None
                            winner_score = -1.0
                            for student, ref_embedding in gallery:
                                score = cosine_similarity(query, ref_embedding)
                                if score > winner_score:
                                    winner_score = score
                                    winner = student
                            if winner is not None:
                                id_ok = expected_id is not None and winner.id == int(
                                    expected_id
                                )
                                roll_ok = (
                                    expected_roll is not None
                                    and winner.roll_no.upper()
                                    == str(expected_roll).upper()
                                )
                                if id_ok or roll_ok:
                                    labeled_correct += 1
                except Exception:
                    continue
            avg_conf = conf_sum / max(1, detected)
            row = {
                "detected_images": float(detected),
                "embedded_images": float(embedded),
                "avg_detection_confidence": float(avg_conf),
            }
            if labeled_total > 0:
                row["top1_accuracy"] = float(labeled_correct / labeled_total)
                row["labeled_total"] = float(labeled_total)
            elif len(self_gallery) >= 2 and len(self_gallery) == len(self_queries):
                self_top1 = 0
                pos_sum = 0.0
                neg_sum = 0.0
                gallery_mat = np.stack(self_gallery, axis=0)
                for idx, query in enumerate(self_queries):
                    sims = gallery_mat @ query
                    winner = int(np.argmax(sims))
                    if winner == idx:
                        self_top1 += 1
                    pos = float(sims[idx])
                    if len(sims) > 1:
                        mask = np.ones(len(sims), dtype=bool)
                        mask[idx] = False
                        neg = float(np.max(sims[mask]))
                    else:
                        neg = 0.0
                    pos_sum += pos
                    neg_sum += neg

                total_self = float(len(self_queries))
                row["self_top1_accuracy"] = float(self_top1 / total_self)
                row["self_avg_positive_similarity"] = float(pos_sum / total_self)
                row["self_avg_max_negative_similarity"] = float(neg_sum / total_self)
                row["self_margin"] = float(
                    row["self_avg_positive_similarity"]
                    - row["self_avg_max_negative_similarity"]
                )
            report[name] = row
        return report

    def available_embedders(self) -> list[str]:
        return available_embedder_names(self.embedders.keys())
