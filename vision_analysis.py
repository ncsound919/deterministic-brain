"""
Vision Analysis Module
Multimodal vision capabilities — LOCAL-FIRST.

Uses the unified local model service (gemma-4 GGUF vision via Ollama) for
image analysis at zero cost. Falls back to OpenRouter vision models only if
the local backend is unavailable AND OPENROUTER_API_KEY is configured.

Capabilities:
- Screenshot analysis for debugging
- UI/UX audits
- Text extraction (OCR)
- Visual error diagnosis
- Image understanding
"""
import base64
import json
from typing import Dict, Optional, List
from pathlib import Path
from dataclasses import dataclass
from PIL import Image
from loguru import logger
from config import settings


@dataclass
class VisionResult:
    """Result of vision analysis"""
    success: bool
    analysis: str
    confidence: Optional[float] = None
    extracted_text: Optional[str] = None
    model_used: Optional[str] = None
    cost: Optional[float] = None
    error: Optional[str] = None


class VisionAnalyzer:
    """
    Vision analysis using the unified local model (gemma vision) first,
    then OpenRouter as a paid fallback.
    """

    def __init__(self):
        # OpenRouter vision fallbacks (sorted by cost) — only used when the
        # local backend is down AND a key is configured.
        self.vision_models = [
            {"id": "google/gemini-flash-1.5-8b", "name": "Gemini Flash 1.5 8B",
             "cost_per_1m": 0.04, "quality": "fast"},
            {"id": "anthropic/claude-3-haiku", "name": "Claude 3 Haiku",
             "cost_per_1m": 0.25, "quality": "good"},
            {"id": "google/gemini-pro-1.5", "name": "Gemini Pro 1.5",
             "cost_per_1m": 1.25, "quality": "high"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet",
             "cost_per_1m": 3.0, "quality": "excellent"},
        ]

    # ---- local-first path ----

    def _local_analyze(self, image_path: str, prompt: str) -> VisionResult | None:
        """Analyse via the unified local model (gemma vision). Returns None
        if no local backend or no vision-capable model is available."""
        try:
            from tools.local_model import get_local_model
            svc = get_local_model()
            if not svc.is_available() or not svc.supports_vision():
                return None
            analysis = svc.chat_with_image(prompt, image_path, max_tokens=512, temperature=0.1)
            if not analysis:
                return None
            model = None
            try:
                b = svc.active_backend()
                model = b.vision_model_name() if hasattr(b, "vision_model_name") else None
            except Exception:
                pass
            return VisionResult(success=True, analysis=analysis, model_used=model or "local-gemma", cost=0.0)
        except Exception as e:
            logger.warning(f"Local vision failed: {e}")
            return None

    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64"""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            raise

    def _get_image_mime_type(self, image_path: str) -> str:
        """Get MIME type from image extension"""
        suffix = Path(image_path).suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(suffix, 'image/png')

    def _optimize_image(self, image_path: str, max_size: tuple = (1920, 1080)) -> str:
        """Optimize image size to reduce API costs. Returns path to optimized image."""
        try:
            img = Image.open(image_path)
            if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                optimized_path = str(Path(image_path).with_stem(f"{Path(image_path).stem}_optimized"))
                img.save(optimized_path, quality=85, optimize=True)
                logger.debug(f"Optimized image: {image_path} -> {optimized_path}")
                return optimized_path
            return image_path
        except Exception as e:
            logger.warning(f"Image optimization failed, using original: {e}")
            return image_path

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        quality: str = "fast",
        optimize: bool = True
    ) -> VisionResult:
        """
        Analyze an image using the local vision model (paid fallback only
        when the local backend is unavailable and OpenRouter is configured).

        Args:
            image_path: Path to image file
            prompt: Analysis prompt/question
            quality: Quality level ('fast', 'good', 'high', 'excellent')
            optimize: Whether to optimize image before sending

        Returns:
            VisionResult with analysis
        """
        try:
            # Optimize image if requested
            if optimize:
                image_path = self._optimize_image(image_path)

            # 1. Local-first: gemma vision, zero cost.
            local = self._local_analyze(image_path, prompt)
            if local:
                return local

            # 2. Paid OpenRouter fallback.
            model = next(
                (m for m in self.vision_models if m["quality"] == quality),
                self.vision_models[0]
            )
            base64_image = self._encode_image(image_path)
            mime_type = self._get_image_mime_type(image_path)

            if not settings.openrouter_api_key:
                return VisionResult(
                    success=False,
                    analysis="",
                    error="No local vision model available and OPENROUTER_API_KEY not configured"
                )

            from tools.llm.openrouter_client import get_client
            client = get_client()
            if not client.available:
                return VisionResult(
                    success=False,
                    analysis="",
                    error="No local vision model and OpenRouter unavailable"
                )

            logger.info(f"Analyzing image with {model['name']}")
            messages = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                ]
            }]
            analysis_text = client.complete(messages, lane="default", model=model["id"], max_tokens=512)
            return VisionResult(success=True, analysis=analysis_text, model_used=model["id"])

        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return VisionResult(success=False, analysis="", error=str(e))

    async def analyze_screenshot_error(
        self,
        screenshot_path: str,
        error_message: str,
        context: Optional[Dict] = None
    ) -> VisionResult:
        """Analyze a screenshot in context of an error"""
        prompt = f"""Analyze this screenshot taken when an error occurred.

Error Message: {error_message}

Context: {json.dumps(context, indent=2, default=str) if context else 'None'}

Please:
1. Identify what's visible in the screenshot
2. Explain what might have caused the error
3. Suggest specific fixes or debugging steps
4. Rate your confidence (0-100%) in the diagnosis"""

        return await self.analyze_image(screenshot_path, prompt, quality="good")

    async def audit_ui_design(
        self,
        image_path: str,
        focus_areas: Optional[List[str]] = None
    ) -> VisionResult:
        """Perform UI/UX audit on a design mockup or screenshot"""
        focus = ", ".join(focus_areas) if focus_areas else "general design quality"
        prompt = f"""Perform a UI/UX audit of this interface focusing on: {focus}

Please analyze:
1. Visual hierarchy and layout
2. Color scheme and contrast
3. Typography and readability
4. Spacing and alignment
5. Interactive elements (buttons, forms)
6. Overall user experience

Provide 3-5 specific actionable improvements."""

        return await self.analyze_image(image_path, prompt, quality="high")

    async def extract_text_from_image(
        self,
        image_path: str,
        use_local_ocr: bool = True
    ) -> VisionResult:
        """Extract text from image using OCR"""
        # Try local OCR first if available
        if use_local_ocr:
            try:
                import pytesseract
                img = Image.open(image_path)
                text = pytesseract.image_to_string(img)
                if text.strip():
                    logger.info("Text extracted using local OCR (no cost)")
                    return VisionResult(
                        success=True,
                        analysis="Text extracted successfully",
                        extracted_text=text,
                        cost=0.0
                    )
            except ImportError:
                logger.warning("pytesseract not available, falling back to vision model")
            except Exception as e:
                logger.warning(f"Local OCR failed: {e}, falling back to vision model")

        # Fallback to local vision model (gemma OCR), then paid API.
        prompt = "Extract all text visible in this image. Provide the text exactly as it appears, maintaining structure and formatting where possible."
        result = await self.analyze_image(image_path, prompt, quality="fast")
        if result.success:
            result.extracted_text = result.analysis
        return result


# Global vision analyzer instance
vision_analyzer = VisionAnalyzer()
