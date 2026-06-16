"""Vision moderation for generated images/video frames.

Where the text scanners inspect prompts, :class:`ImageModerationScanner` inspects the *output*
media of the image/video nodes (passed through the post-stage action metadata). It delegates to
a pluggable :class:`VisionBackend`:

  * :class:`NullVisionBackend` — default no-op (returns safe). Lets the scanner sit in the
    pipeline harmlessly until a real backend is configured.
  * :class:`AzureVisionBackend` — Azure AI Content Safety (image). Optional ``[vision-azure]``.
  * :class:`RekognitionBackend` — AWS Rekognition content moderation. Optional ``[vision-aws]``.
  * :class:`TransformersNSFWBackend` — local NSFW image classifier via transformers. ``[guard]``.

All cloud/model backends import lazily and are fail-closed at the gate. Image data is read from
``action.metadata`` under ``image_bytes`` or ``image_path`` (or the node ``output`` dict).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..core.types import Action, Context, Verdict

logger = logging.getLogger("safetynet.scanners.image_moderation")


@dataclass
class VisionResult:
    unsafe_score: float
    categories: list[str] = field(default_factory=list)
    detail: str = ""


@runtime_checkable
class VisionBackend(Protocol):
    name: str

    def moderate(self, image: bytes) -> VisionResult:
        ...


def _extract_image(action: Action, allow_path_read: bool = False) -> bytes | None:
    """Find image bytes in the action.

    Inline ``image_bytes`` (in metadata or the agent ``output`` dict) is always honored.
    A filesystem ``image_path`` is read **only** when ``allow_path_read`` is explicitly enabled —
    otherwise an untrusted agent response could point at an arbitrary local file (LFI). When
    enabled, the path is resolved and confirmed to be a regular file.
    """
    meta = action.metadata or {}
    if isinstance(meta.get("image_bytes"), (bytes, bytearray)):
        return bytes(meta["image_bytes"])
    out = meta.get("output")
    if isinstance(out, dict):
        for key in ("image_bytes", "pixels"):
            val = out.get(key)
            if isinstance(val, (bytes, bytearray)):
                return bytes(val)
    if allow_path_read:
        path = meta.get("image_path") or (out.get("path") if isinstance(out, dict) else None)
        if path and os.path.isfile(path):
            with open(path, "rb") as fh:
                return fh.read()
    return None


class NullVisionBackend:
    """No-op backend: treats everything as safe. The default placeholder."""

    name = "null"

    def moderate(self, image: bytes) -> VisionResult:
        return VisionResult(unsafe_score=0.0, detail="null vision backend (no moderation performed)")


class AzureVisionBackend:
    """Azure AI Content Safety (image moderation). Optional ``[vision-azure]`` extra."""

    name = "azure"

    def __init__(self, endpoint: str | None = None, api_key: str | None = None, reject_threshold: int = 2) -> None:
        try:
            from azure.ai.contentsafety import ContentSafetyClient
            from azure.core.credentials import AzureKeyCredential
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "AzureVisionBackend requires the optional 'vision-azure' extra. "
                "Install with: pip install '.[vision-azure]'"
            ) from exc
        endpoint = endpoint or os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT")
        api_key = api_key or os.environ.get("AZURE_CONTENT_SAFETY_KEY")
        if not endpoint or not api_key:
            raise RuntimeError("AzureVisionBackend needs AZURE_CONTENT_SAFETY_ENDPOINT and _KEY")
        self.reject_threshold = reject_threshold
        self._client = ContentSafetyClient(endpoint, AzureKeyCredential(api_key))

    def moderate(self, image: bytes) -> VisionResult:  # pragma: no cover - needs cloud + key
        from azure.ai.contentsafety.models import AnalyzeImageOptions, ImageData

        resp = self._client.analyze_image(AnalyzeImageOptions(image=ImageData(content=image)))
        cats = {c.category: c.severity for c in resp.categories_analysis}
        worst = max(cats.values()) if cats else 0
        unsafe = min(1.0, worst / 6.0)  # Azure severities run 0..6
        flagged = [c for c, sev in cats.items() if sev >= self.reject_threshold]
        return VisionResult(unsafe_score=unsafe, categories=flagged, detail=f"azure severities: {cats}")


class RekognitionBackend:
    """AWS Rekognition content moderation. Optional ``[vision-aws]`` extra."""

    name = "rekognition"

    def __init__(self, min_confidence: float = 50.0, region_name: str | None = None) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "RekognitionBackend requires the optional 'vision-aws' extra. "
                "Install with: pip install '.[vision-aws]'"
            ) from exc
        self.min_confidence = min_confidence
        self._client = boto3.client("rekognition", region_name=region_name)

    def moderate(self, image: bytes) -> VisionResult:  # pragma: no cover - needs AWS creds
        resp = self._client.detect_moderation_labels(Image={"Bytes": image}, MinConfidence=self.min_confidence)
        labels = resp.get("ModerationLabels", [])
        worst = max((lbl["Confidence"] for lbl in labels), default=0.0)
        return VisionResult(
            unsafe_score=min(1.0, worst / 100.0),
            categories=[lbl["Name"] for lbl in labels],
            detail=f"rekognition labels: {[lbl['Name'] for lbl in labels]}",
        )


class TransformersNSFWBackend:
    """Local NSFW image classifier via transformers. Optional ``[guard]`` extra."""

    name = "nsfw"

    def __init__(self, model_id: str = "Falconsai/nsfw_image_detection") -> None:
        try:
            from transformers import pipeline
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "TransformersNSFWBackend requires the optional 'guard' extra. "
                "Install with: pip install '.[guard]'"
            ) from exc
        self._pipe = pipeline("image-classification", model=model_id)

    def moderate(self, image: bytes) -> VisionResult:  # pragma: no cover - needs the model
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image)).convert("RGB")
        preds = {p["label"].lower(): p["score"] for p in self._pipe(img)}
        unsafe = float(preds.get("nsfw", 0.0))
        return VisionResult(unsafe_score=unsafe, categories=["nsfw"] if unsafe >= 0.5 else [], detail=f"nsfw score {unsafe:.2f}")


BACKEND_REGISTRY: dict[str, type] = {
    "null": NullVisionBackend,
    "azure": AzureVisionBackend,
    "rekognition": RekognitionBackend,
    "nsfw": TransformersNSFWBackend,
}


def build_vision_backend(name: str, **params) -> VisionBackend:
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown vision backend {name!r}; expected one of {sorted(BACKEND_REGISTRY)}")
    return cls(**params)


class ImageModerationScanner:
    """Moderates generated image/video output via a pluggable vision backend."""

    name = "image_moderation"

    def __init__(
        self,
        backend: str | VisionBackend = "null",
        applies_to_kinds: tuple[str, ...] = ("generate_image", "generate_video"),
        allow_path_read: bool = False,
        **backend_params,
    ) -> None:
        self.backend: VisionBackend = build_vision_backend(backend, **backend_params) if isinstance(backend, str) else backend
        self.applies_to_kinds = applies_to_kinds
        self.allow_path_read = allow_path_read

    def scan(self, action: Action, context: Context) -> Verdict:
        if action.kind not in self.applies_to_kinds:
            return Verdict.from_score(self.name, 0.9, "not an image/video node; skipped")
        image = _extract_image(action, allow_path_read=self.allow_path_read)
        if image is None:
            return Verdict.from_score(self.name, 0.85, "no image data available to moderate")
        result = self.backend.moderate(image)
        safety = max(0.0, 1.0 - float(result.unsafe_score))
        detail = result.detail or (f"unsafe: {result.categories}" if result.categories else "clean")
        return Verdict.from_score(self.name, safety, f"[{self.backend.name}] {detail}")
