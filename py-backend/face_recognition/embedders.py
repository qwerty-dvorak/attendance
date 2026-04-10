from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import cv2
import numpy as np
import onnxruntime as ort
import torch
from torch import nn

from .utils import l2_normalize


def _to_numpy(tensor: torch.Tensor) -> np.ndarray:
    return tensor.detach().cpu().numpy()


class _Flatten(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.view(x.size(0), -1)


class _BasicBlockIR(nn.Module):
    def __init__(self, in_channel: int, depth: int, stride: int):
        super().__init__()
        if in_channel == depth:
            self.shortcut_layer = nn.MaxPool2d(1, stride)
        else:
            self.shortcut_layer = nn.Sequential(
                nn.Conv2d(in_channel, depth, (1, 1), stride, bias=False),
                nn.BatchNorm2d(depth),
            )
        self.res_layer = nn.Sequential(
            nn.BatchNorm2d(in_channel),
            nn.Conv2d(in_channel, depth, (3, 3), (1, 1), 1, bias=False),
            nn.BatchNorm2d(depth),
            nn.PReLU(depth),
            nn.Conv2d(depth, depth, (3, 3), stride, 1, bias=False),
            nn.BatchNorm2d(depth),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.res_layer(x) + self.shortcut_layer(x)


class AdaFaceIR50(nn.Module):
    def __init__(self):
        super().__init__()
        self.input_layer = nn.Sequential(
            nn.Conv2d(3, 64, 3, stride=1, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.PReLU(64),
        )

        block_defs: list[tuple[int, int, int]] = []
        stages = [(64, 64, 3), (64, 128, 4), (128, 256, 14), (256, 512, 3)]
        for in_channel, depth, units in stages:
            block_defs.append((in_channel, depth, 2))
            for _ in range(units - 1):
                block_defs.append((depth, depth, 1))

        self.body = nn.Sequential(
            *[
                _BasicBlockIR(in_channel=in_c, depth=out_c, stride=stride)
                for in_c, out_c, stride in block_defs
            ]
        )

        self.output_layer = nn.Sequential(
            nn.BatchNorm2d(512),
            nn.Dropout(0.4),
            _Flatten(),
            nn.Linear(512 * 7 * 7, 512),
            nn.BatchNorm1d(512, affine=False),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_layer(x)
        x = self.body(x)
        x = self.output_layer(x)
        return x


class Embedder:
    name: str

    def embed(self, face_bgr_112: np.ndarray) -> np.ndarray:
        raise NotImplementedError


@dataclass
class LVFaceONNXEmbedder(Embedder):
    model_path: str
    providers: Tuple[str, ...] = ("CPUExecutionProvider",)

    def __post_init__(self):
        self.name = "lvface_onnx"
        self.session = ort.InferenceSession(
            self.model_path, providers=list(self.providers)
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    def _preprocess(self, face_bgr_112: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(face_bgr_112, cv2.COLOR_BGR2RGB).astype(np.float32)
        tensor = (rgb - 127.5) / 128.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
        return tensor.astype(np.float32)

    def embed(self, face_bgr_112: np.ndarray) -> np.ndarray:
        inp = self._preprocess(face_bgr_112)
        embedding = self.session.run([self.output_name], {self.input_name: inp})[0][0]
        return l2_normalize(embedding.astype(np.float32))


@dataclass
class AdaFacePTEmbedder(Embedder):
    model_path: str

    def __post_init__(self):
        self.name = "cvlface_adaface_pt"
        self.device = torch.device("cpu")
        self.model = AdaFaceIR50().to(self.device)
        state = torch.load(self.model_path, map_location="cpu")
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        if isinstance(state, dict) and "model" in state:
            state = state["model"]
        if not isinstance(state, dict):
            raise RuntimeError("Unsupported AdaFace checkpoint format")
        clean_state = {k.replace("net.", "", 1): v for k, v in state.items()}
        self.model.load_state_dict(clean_state, strict=True)
        self.model.eval()

    def _preprocess(self, face_bgr_112: np.ndarray) -> torch.Tensor:
        rgb = cv2.cvtColor(face_bgr_112, cv2.COLOR_BGR2RGB).astype(np.float32)
        tensor = (rgb - 127.5) / 128.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
        return torch.from_numpy(tensor).to(self.device)

    def embed(self, face_bgr_112: np.ndarray) -> np.ndarray:
        inp = self._preprocess(face_bgr_112)
        with torch.inference_mode():
            embedding = self.model(inp)[0]
        return l2_normalize(_to_numpy(embedding).astype(np.float32))


@dataclass
class CVLFaceEmbedder(Embedder):
    model_path: str
    fallback: Embedder

    def __post_init__(self):
        self.name = "cvlface_kprpe"
        self._impl = self.fallback

        ckpt_name = Path(self.model_path).name.lower()
        if "ir50" in ckpt_name:
            self.name = "cvlface_adaface_ir50"
            self._impl = AdaFacePTEmbedder(self.model_path)
            return

        try:
            from cvlface.general_utils.config_utils import load_config

            load_config  # noqa: B018
            self.name = "cvlface_kprpe"
        except Exception:
            self.name = f"{self.fallback.name}_fallback"
            self._impl = self.fallback

    def embed(self, face_bgr_112: np.ndarray) -> np.ndarray:
        return self._impl.embed(face_bgr_112)


def build_embedders(config) -> Dict[str, Embedder]:
    def cfg(key: str, default=None):
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    embedders: Dict[str, Embedder] = {}
    lvface_onnx_path = cfg("LVFACE_ONNX_PATH")
    cvlface_pt_path = cfg("CVLFACE_PT_PATH")

    if lvface_onnx_path and Path(lvface_onnx_path).exists():
        embedders["lvface_onnx"] = LVFaceONNXEmbedder(lvface_onnx_path)

    base_fallback = embedders.get("lvface_onnx")
    if cvlface_pt_path and Path(cvlface_pt_path).exists():
        if base_fallback is None:
            base_fallback = AdaFacePTEmbedder(cvlface_pt_path)
        cvlface = CVLFaceEmbedder(cvlface_pt_path, base_fallback)
        embedders[cvlface.name] = cvlface
        if cvlface.name != "cvlface_adaface_ir50":
            embedders["cvlface_adaface_ir50"] = AdaFacePTEmbedder(cvlface_pt_path)

    if not embedders:
        raise RuntimeError("No embedders available from configured model paths")
    return embedders


def choose_default_embedder(
    embedders: Dict[str, Embedder], requested: str
) -> Tuple[str, Embedder]:
    if requested in embedders:
        return requested, embedders[requested]
    first = next(iter(embedders.items()))
    return first[0], first[1]


def available_embedder_names(embedders: Iterable[str]) -> list[str]:
    return sorted(list(embedders))
