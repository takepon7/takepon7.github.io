from __future__ import annotations

import numpy as np
from PIL import Image

from gitai_phase0.domain import TemplateSet
from gitai_phase0.open_clip_judge import flatten_alpha
from gitai_phase0.scoring import normalize_vector


class SiglipJudge:
    def __init__(
        self,
        model_id: str = "google/siglip-base-patch16-224",
        device: str = "cpu",
    ) -> None:
        try:
            import torch
            from transformers import AutoModel, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "torch and transformers are not installed. Install the optional 'siglip' extra."
            ) from exc

        self._torch = torch
        self._device = device
        self._model_id = model_id
        self._processor = AutoProcessor.from_pretrained(model_id)
        self._model = AutoModel.from_pretrained(model_id).to(device)
        self._model.eval()

    @property
    def model_version(self) -> str:
        return f"siglip:{self._model_id}:fp32"

    def encode_image(self, image: Image.Image) -> np.ndarray:
        inputs = self._processor(images=flatten_alpha(image), return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            features = pooled_tensor(self._model.get_image_features(**inputs)).float()
        return normalize_vector(features.cpu().numpy()[0].astype(np.float32))

    def encode_text(self, label: str, template_set: TemplateSet) -> np.ndarray:
        prompts = [template.format(label=label) for template in template_set.templates]
        inputs = self._processor(text=prompts, padding=True, return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            features = pooled_tensor(self._model.get_text_features(**inputs)).float()
        vectors = features.cpu().numpy().astype(np.float32)
        mean_vector = np.mean([normalize_vector(item) for item in vectors], axis=0)
        return normalize_vector(mean_vector)


def pooled_tensor(output):
    if hasattr(output, "pooler_output") and output.pooler_output is not None:
        return output.pooler_output
    return output
