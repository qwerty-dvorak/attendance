"""Compatibility wrapper for SCRFD ONNX export on MMDet 3.x + MMCV 2.x.

It exposes the legacy APIs expected by scripts/scrfd2onnx.py:
  - mmdet.core.build_model_from_cfg
  - mmdet.core.generate_inputs_and_wrap_model
  - mmdet.core.preprocess_example_input
"""

from __future__ import annotations

from pathlib import Path

import cv2
import mmengine
import numpy as np
import torch
from mmengine.config import Config
from mmdet.registry import MODELS
from mmdet.utils import register_all_modules


def build_model_from_cfg(config_path, checkpoint_path=None, cfg_options=None):
    register_all_modules(init_default_scope=True)
    cfg = Config.fromfile(config_path)
    if cfg_options:
        cfg.merge_from_dict(cfg_options)

    model = MODELS.build(cfg.model)
    if checkpoint_path:
        ckpt = torch.load(checkpoint_path, map_location="cpu")
        state_dict = ckpt.get("state_dict", ckpt)
        model.load_state_dict(state_dict, strict=False)
    model.eval()
    return model


def preprocess_example_input(input_config):
    input_shape = input_config["input_shape"]
    input_path = input_config.get("input_path")
    normalize_cfg = input_config.get("normalize_cfg") or {
        "mean": [127.5, 127.5, 127.5],
        "std": [128.0, 128.0, 128.0],
    }

    if input_path and Path(input_path).exists():
        img = cv2.imread(input_path)
    else:
        _, _, h, w = input_shape
        img = np.zeros((h, w, 3), dtype=np.uint8)

    h, w = input_shape[2], input_shape[3]
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)
    img = img.astype(np.float32)
    img = (img - np.array(normalize_cfg["mean"], dtype=np.float32)) / np.array(
        normalize_cfg["std"], dtype=np.float32
    )
    img = np.transpose(img, (2, 0, 1))[None, ...]
    return torch.from_numpy(img), img


def _extract_outputs(result):
    if isinstance(result, (tuple, list)):
        outputs = []
        for item in result:
            if isinstance(item, (tuple, list)):
                outputs.extend(_extract_outputs(item))
            else:
                outputs.append(item)
        return outputs

    if isinstance(result, dict):
        if "cls_scores" in result and "bbox_preds" in result:
            cls_scores = list(result["cls_scores"])
            bbox_preds = list(result["bbox_preds"])
            kps_preds = list(result.get("kps_preds", []))
            return cls_scores + bbox_preds + kps_preds
        return [value for value in result.values() if torch.is_tensor(value)]

    return [result]


class _ExportWrapper(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(self, x):
        result = self.model(x)
        flat = _extract_outputs(result)
        if not flat:
            raise RuntimeError("Failed to flatten model outputs for ONNX export")
        return tuple(flat)


def generate_inputs_and_wrap_model(config_path, checkpoint_path, input_config):
    model = build_model_from_cfg(config_path, checkpoint_path)
    tensor_data, _ = preprocess_example_input(input_config)
    return _ExportWrapper(model), tensor_data
