from __future__ import annotations

import numpy as np
from PIL import Image

from gitai_phase0.domain import TemplateSet
from gitai_phase0.scoring import normalize_vector


class OpenClipJudge:
    def __init__(
        self,
        model_name: str = "ViT-L-14",
        pretrained: str = "openai",
        device: str = "cpu",
    ) -> None:
        try:
            import open_clip
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "open_clip and torch are not installed. Install the optional 'clip' extra."
            ) from exc

        self._open_clip = open_clip
        self._torch = torch
        self._device = device
        self._model_name = model_name
        self._pretrained = pretrained
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model_name, pretrained=pretrained, device=device
        )
        self._model.eval()
        self._tokenizer = open_clip.get_tokenizer(model_name)

    @property
    def model_version(self) -> str:
        return f"open_clip:{self._model_name}:{self._pretrained}:fp32"

    def encode_image(self, image: Image.Image) -> np.ndarray:
        rgb = flatten_alpha(image)
        tensor = self._preprocess(rgb).unsqueeze(0).to(self._device)
        with self._torch.no_grad():
            encoded = self._model.encode_image(tensor).float()
        return normalize_vector(encoded.cpu().numpy()[0].astype(np.float32))

    def encode_text(self, label: str, template_set: TemplateSet) -> np.ndarray:
        prompts = [template.format(label=label) for template in template_set.templates]
        tokens = self._tokenizer(prompts).to(self._device)
        with self._torch.no_grad():
            encoded = self._model.encode_text(tokens).float()
        vectors = encoded.cpu().numpy().astype(np.float32)
        mean_vector = np.mean([normalize_vector(item) for item in vectors], axis=0)
        return normalize_vector(mean_vector)


def flatten_alpha(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")
