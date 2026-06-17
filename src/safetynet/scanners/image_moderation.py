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

import base64
import binascii
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from ..core.types import Action, Context, Verdict

logger = logging.getLogger("safetynet.scanners.image_moderation")

# Image references an agent may return in its text/raw payload.
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*(\S+?)\s*\)")          # markdown ![alt](url)
_BARE_IMG_URL_RE = re.compile(r"https?://[^\s)\"']+\.(?:png|jpe?g|webp|gif|bmp)\b", re.IGNORECASE)
_DATA_URI_RE = re.compile(r"data:image/[A-Za-z.+-]+;base64,([A-Za-z0-9+/=]+)")


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


def _find_image_refs(action: Action) -> list[str]:
    """Collect image URLs / data-URIs from the response text and the agent's raw payload.

    Handles markdown image links, bare image URLs, ``data:image/...;base64,...`` URIs, and the
    ``message_files`` / ``files`` lists Dify returns for generated images.
    """
    refs: list[str] = []
    text = action.payload or ""
    refs += _MD_IMAGE_RE.findall(text)
    refs += _BARE_IMG_URL_RE.findall(text)
    refs += [f"data:image/x;base64,{b}" for b in _DATA_URI_RE.findall(text)]

    out = (action.metadata or {}).get("output")
    if isinstance(out, dict):
        for key in ("message_files", "files", "images"):
            for f in out.get(key) or []:
                if isinstance(f, dict):
                    url = f.get("url") or f.get("image_url") or f.get("preview_url")
                    if url and (f.get("type") in (None, "image") or str(url).lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))):
                        refs.append(url)
                elif isinstance(f, str):
                    refs.append(f)
    # De-duplicate, preserve order.
    seen: set[str] = set()
    return [r for r in refs if not (r in seen or seen.add(r))]


def _decode_data_uri(uri: str) -> bytes | None:
    m = _DATA_URI_RE.search(uri)
    if not m:
        return None
    try:
        return base64.b64decode(m.group(1) + "=" * (-len(m.group(1)) % 4))
    except (binascii.Error, ValueError):
        return None


def _host_allowed(url: str, allowed_hosts: tuple[str, ...]) -> bool:
    """SSRF guard: only http/https URLs whose host is on the explicit allowlist may be fetched."""
    if not allowed_hosts:
        return False  # empty allowlist => fetch nothing (must be configured explicitly)
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.hostname in allowed_hosts


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


class CLIPCopyrightBackend:
    """Image-level copyright-reproduction detector via CLIP similarity (arXiv:2403.12052).

    Embeds the generated image and compares it (cosine similarity) against reference images of
    protected works; high similarity ⇒ likely reproduction ⇒ unsafe. Optional ``[embeddings]``
    extra (sentence-transformers ships a CLIP model). The model + reference embeddings load lazily
    on first use, so construction is cheap and testable.

    Provide references via ``reference_dir`` (a folder of protected-work images) or
    ``reference_paths`` (a list). With no references it cannot judge and returns *safe* with a note.
    """

    name = "clip"

    def __init__(
        self,
        reference_dir: str | None = None,
        reference_paths: list[str] | None = None,
        model: str = "clip-ViT-B-32",
        threshold: float = 0.85,
    ) -> None:
        try:
            import sentence_transformers  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "CLIPCopyrightBackend requires the optional 'embeddings' extra. "
                "Install with: pip install '.[embeddings]'"
            ) from exc
        self.model_name = model
        self.threshold = threshold
        self.reference_dir = reference_dir
        self.reference_paths = list(reference_paths or [])
        self._model = None
        self._ref_emb = None

    def _ensure_ready(self):  # pragma: no cover - needs the model + images
        if self._model is not None:
            return
        import glob
        import os

        from PIL import Image
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)
        paths = list(self.reference_paths)
        if self.reference_dir:
            for ext in ("png", "jpg", "jpeg", "webp", "bmp", "gif"):
                paths += glob.glob(os.path.join(self.reference_dir, f"*.{ext}"))
        imgs = []
        for p in paths:
            try:
                imgs.append(Image.open(p).convert("RGB"))
            except Exception:  # noqa: BLE001
                logger.warning("could not load reference image %s", p)
        self._ref_emb = self._model.encode(imgs, convert_to_tensor=True, normalize_embeddings=True) if imgs else None

    def moderate(self, image: bytes) -> VisionResult:  # pragma: no cover - needs the model
        import io

        from PIL import Image
        from sentence_transformers import util

        self._ensure_ready()
        if self._ref_emb is None:
            return VisionResult(unsafe_score=0.0, detail="no protected reference images configured")
        img = Image.open(io.BytesIO(image)).convert("RGB")
        q = self._model.encode([img], convert_to_tensor=True, normalize_embeddings=True)
        best = float(util.cos_sim(q, self._ref_emb).max())
        unsafe = best if best >= self.threshold else best * 0.3
        cats = ["copyright_reproduction"] if best >= self.threshold else []
        return VisionResult(unsafe_score=max(0.0, min(1.0, unsafe)), categories=cats, detail=f"max CLIP similarity {best:.2f}")


BACKEND_REGISTRY: dict[str, type] = {
    "null": NullVisionBackend,
    "azure": AzureVisionBackend,
    "rekognition": RekognitionBackend,
    "nsfw": TransformersNSFWBackend,
    "clip": CLIPCopyrightBackend,
}


def build_vision_backend(name: str, **params) -> VisionBackend:
    cls = BACKEND_REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown vision backend {name!r}; expected one of {sorted(BACKEND_REGISTRY)}")
    return cls(**params)


class ImageModerationScanner:
    """Moderates images an agent returns — inline bytes, data-URIs, or fetched URLs.

    For agents like Dify that return images as markdown URLs, set ``fetch_urls: true`` and an
    explicit ``allowed_url_hosts`` allowlist (SSRF guard). Without an allowlist no URL is fetched.
    The scanner runs whenever an image is present, regardless of node kind, so it works behind a
    generic ``generate_text`` chat agent.
    """

    name = "image_moderation"

    def __init__(
        self,
        backend: str | VisionBackend = "null",
        applies_to_kinds: tuple[str, ...] = ("generate_image", "generate_video"),
        allow_path_read: bool = False,
        fetch_urls: bool = False,
        allowed_url_hosts: tuple[str, ...] | list[str] = (),
        max_image_bytes: int = 10_000_000,
        timeout: float = 10.0,
        **backend_params,
    ) -> None:
        self.backend: VisionBackend = build_vision_backend(backend, **backend_params) if isinstance(backend, str) else backend
        self.applies_to_kinds = tuple(applies_to_kinds)
        self.allow_path_read = allow_path_read
        self.fetch_urls = fetch_urls
        self.allowed_url_hosts = tuple(allowed_url_hosts)
        self.max_image_bytes = int(max_image_bytes)
        self.timeout = timeout

    def _fetch(self, url: str) -> bytes | None:
        if not _host_allowed(url, self.allowed_url_hosts):
            logger.warning("image fetch blocked (host not allowlisted): %s", url)
            return None
        try:
            import httpx
        except ImportError:
            logger.warning("fetch_urls enabled but httpx not installed (pip install '.[http]')")
            return None
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.content[: self.max_image_bytes]
        except Exception as exc:  # noqa: BLE001
            logger.warning("image fetch failed for %s: %s", url, exc)
            return None

    def _collect(self, action: Action) -> tuple[list[bytes], int]:
        """Return (image byte blobs, number of image references seen)."""
        images: list[bytes] = []
        inline = _extract_image(action, allow_path_read=self.allow_path_read)
        if inline is not None:
            images.append(inline)

        refs = _find_image_refs(action)
        for ref in refs:
            if ref.startswith("data:image/"):
                data = _decode_data_uri(ref)
                if data:
                    images.append(data)
            elif self.fetch_urls:
                data = self._fetch(ref)
                if data:
                    images.append(data)
        return images, len(refs)

    def scan(self, action: Action, context: Context) -> Verdict:
        images, n_refs = self._collect(action)

        if images:
            worst_safety, worst_detail, worst_cats = 1.0, "clean", []
            for img in images:
                res = self.backend.moderate(img)
                safety = max(0.0, 1.0 - float(res.unsafe_score))
                if safety < worst_safety:
                    worst_safety, worst_detail, worst_cats = safety, res.detail, res.categories
            detail = worst_detail or (f"unsafe: {worst_cats}" if worst_cats else "clean")
            return Verdict.from_score(self.name, worst_safety, f"[{self.backend.name}] {len(images)} image(s): {detail}")

        # No bytes obtained.
        if n_refs:
            if self.fetch_urls:
                return Verdict.from_score(self.name, 0.5, f"{n_refs} image URL(s) present but could not be fetched/moderated")
            return Verdict.from_score(self.name, 0.7, f"{n_refs} image URL(s) present; URL fetching disabled")
        if action.kind in self.applies_to_kinds:
            return Verdict.from_score(self.name, 0.85, "no image data available to moderate")
        return Verdict.from_score(self.name, 0.9, "no image content; skipped")
