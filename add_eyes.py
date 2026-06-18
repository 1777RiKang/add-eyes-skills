#!/usr/bin/env python3
"""
MiMo Vision — 纯文本模型的视觉桥接工具
Vision bridge for text-only LLMs (DeepSeek V4 Flash/Pro, etc.)

纯文本模型（如 DeepSeek V4 Flash/Pro）看不懂图片。
这个脚本将图片编码后发送到外部视觉 API，返回文字描述，
让纯文本模型「看到」图片内容。

Usage:
  python add_eyes.py <image_path> [question] [--model <backend>]
  python add_eyes.py - [question] [--model <backend>]  # read base64 from stdin
  python add_eyes.py screenshot.png
  python add_eyes.py screenshot.png "What is in this image?" --model gpt-4o

Stdin formats (when image_path is "-"):
  - Raw base64: echo "<base64>" | python add_eyes.py - "describe" --type png
  - Data URI:   echo "data:image/png;base64,<base64>" | python add_eyes.py -

Vision backends (via env config):
  Backend                Env Key              Env Base URL (optional)
  ─────────────────────────────────────────────────────────────────
  mimo-v2.5      (def)  MIMO_API_KEY         MIMO_BASE_URL
  gpt-4o                OPENAI_API_KEY       OPENAI_BASE_URL
  gpt-4-turbo           OPENAI_API_KEY       OPENAI_BASE_URL
  claude-3.5-sonnet     ANTHROPIC_API_KEY    ANTHROPIC_BASE_URL
  gemini-1.5-pro        GEMINI_API_KEY       GEMINI_BASE_URL
"""

# ── Fix Windows terminal encoding for Chinese output ────────────────
import sys
import os
import io

if sys.platform == "win32":
    # Force UTF-8 output on Windows (more Pythonic than os.system("chcp"))
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        # Python < 3.7 fallback
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import base64
import json
import re
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# ── Supported file formats ────────────────────────────────────────────
SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

# ── Default model config (MiMo) ──────────────────────────────────────
DEFAULT_CONFIG = {
    "api_key_env": "MIMO_API_KEY",
    "base_url_env": "MIMO_BASE_URL",
    "default_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
    "max_tokens": 4096,
}

def _find_preset(model_name):
    """Find the best matching preset for a model name.

    Handles cases like:
    - "ollama:minicpm-v" -> exact match
    - "ollama:minicpm-v:latest" -> prefix match
    - "gpt-4o-2024-01-01" -> prefix match
    """
    # Exact match first
    if model_name in MODEL_PRESETS:
        return MODEL_PRESETS[model_name]

    # Prefix match: try progressively shorter prefixes
    # This handles "ollama:minicpm-v:latest" -> "ollama:minicpm-v"
    parts = model_name.split(":")
    if len(parts) > 2:
        prefix = ":".join(parts[:2])
        if prefix in MODEL_PRESETS:
            return MODEL_PRESETS[prefix]

    # Try matching by model family (e.g. "gpt-4o-2024-01-01" -> "gpt-4o")
    # Only match if the next char after preset_name is a delimiter or end-of-string
    # This prevents "gpt-4o-mini" from matching "gpt-4o"
    for preset_name, preset in MODEL_PRESETS.items():
        if model_name.startswith(preset_name):
            rest = model_name[len(preset_name):]
            if not rest or rest[0] in "-_.":
                return preset

    return None


# ── Model presets ─────────────────────────────────────────────────────
MODEL_PRESETS = {
    "mimo-v2.5": {
        "api_key_env": "MIMO_API_KEY",
        "base_url_env": "MIMO_BASE_URL",
        "default_base_url": "https://token-plan-cn.xiaomimimo.com/v1/chat/completions",
        "max_tokens": 4096,
    },
    "gpt-4o": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1/chat/completions",
        "max_tokens": 4096,
    },
    "gpt-4-vision-preview": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1/chat/completions",
        "max_tokens": 4096,
    },
    "gpt-4-turbo": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1/chat/completions",
        "max_tokens": 4096,
    },
    "claude-3-opus-20240229": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com/v1/messages",
        "max_tokens": 4096,
        "anthropic_version": "2023-06-01",
    },
    "claude-3-sonnet-20240229": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com/v1/messages",
        "max_tokens": 4096,
        "anthropic_version": "2023-06-01",
    },
    "claude-3-5-sonnet-20241022": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com/v1/messages",
        "max_tokens": 8192,
        "anthropic_version": "2023-06-01",
    },
    "claude-sonnet-4-6": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com/v1/messages",
        "max_tokens": 8192,
        "anthropic_version": "2023-06-01",
    },
    "gemini-1.5-pro": {
        "api_key_env": "GEMINI_API_KEY",
        "base_url_env": "GEMINI_BASE_URL",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
        "max_tokens": 4096,
    },
    "gemini-1.5-flash": {
        "api_key_env": "GEMINI_API_KEY",
        "base_url_env": "GEMINI_BASE_URL",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        "max_tokens": 4096,
    },
    "ollama:minicpm-v": {
        "api_key_env": None,
        "base_url_env": "OLLAMA_HOST",
        "default_base_url": "http://localhost:11434",
        "max_tokens": 4096,
        "ollama_model": "minicpm-v",
    },
    "ollama:llava": {
        "api_key_env": None,
        "base_url_env": "OLLAMA_HOST",
        "default_base_url": "http://localhost:11434",
        "max_tokens": 4096,
        "ollama_model": "llava",
    },
    "ollama:moondream": {
        "api_key_env": None,
        "base_url_env": "OLLAMA_HOST",
        "default_base_url": "http://localhost:11434",
        "max_tokens": 4096,
        "ollama_model": "moondream",
    },
}


def read_stdin_image(ext_hint=None):
    """Read base64 image data from stdin.

    Supports two formats:
    1. Raw base64:  echo "<base64>" | python add_eyes.py -
    2. Data URI:    echo "data:image/png;base64,<base64>" | python add_eyes.py -

    Returns (b64, mime) tuple.
    """
    raw = sys.stdin.read().strip()

    # Try data URI format: data:image/png;base64,<payload>
    if raw.startswith("data:"):
        # "data:image/png;base64,<payload>"
        header, _, payload = raw.partition(",")
        # "data:image/png" -> "image/png"
        mime = header.removeprefix("data:").removesuffix(";base64")
        if mime in MIME_MAP.values():
            return payload, mime
        # Extract mime from "data:image/<format>;base64"
        parts = mime.split(";")
        mime = parts[0] if parts[0].startswith("image/") else "image/png"
        return payload, mime

    # Raw base64 — need --type to determine mime
    if ext_hint:
        ext = ext_hint if ext_hint.startswith(".") else f".{ext_hint}"
        mime = MIME_MAP.get(ext.lower())
        if not mime:
            raise ValueError(f"Unknown format hint: {ext_hint}. Use png, jpg, jpeg, gif, webp, or bmp.")
        return raw, mime

    # No hint — default to png
    return raw, "image/png"


def encode_image(path):
    """Read and base64-encode an image file."""
    ext = Path(path).suffix.lower()
    if ext not in SUPPORTED_EXTS:
        raise ValueError(
            f"Unsupported format: {ext}\n"
            f"Supported: {', '.join(SUPPORTED_EXTS)}"
        )
    mime = MIME_MAP[ext]
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return data, mime


def crop_region(image_path, region=None, focus=None):
    """Crop image to a specific region for focused analysis.

    Args:
        image_path: Path to the image file.
        region: Tuple (x1, y1, x2, y2) in pixels or percentages (0-1).
        focus: Keyword like "左上", "右下", "中间", "top", "bottom", etc.

    Returns:
        Tuple of (cropped_base64, mime) or original (base64, mime) if no crop.
    """
    # If neither region nor focus specified, return original
    if not region and not focus:
        return encode_image(image_path)

    try:
        from PIL import Image
    except ImportError:
        # Pillow not available, return original
        return encode_image(image_path)

    img = Image.open(image_path)
    w, h = img.size

    if region:
        # Parse region: can be (x1, y1, x2, y2) in pixels or percentages
        x1, y1, x2, y2 = region
        # If values are <= 1, treat as percentages
        if all(0 <= v <= 1 for v in [x1, y1, x2, y2]):
            x1, y1, x2, y2 = int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)
        # Clamp to image bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        cropped = img.crop((x1, y1, x2, y2))

    elif focus:
        # Keyword-based region selection
        focus_lower = focus.lower()
        regions = {
            # Chinese
            "左上": (0, 0, 0.5, 0.5),
            "右上": (0.5, 0, 1, 0.5),
            "左下": (0, 0.5, 0.5, 1),
            "右下": (0.5, 0.5, 1, 1),
            "顶部": (0, 0, 1, 0.33),
            "底部": (0, 0.67, 1, 1),
            "左侧": (0, 0, 0.5, 1),
            "右侧": (0.5, 0, 1, 1),
            "中间": (0.25, 0.25, 0.75, 0.75),
            "左上角": (0, 0, 0.5, 0.5),
            "右上角": (0.5, 0, 1, 0.5),
            "左下角": (0, 0.5, 0.5, 1),
            "右下角": (0.5, 0.5, 1, 1),
            # English
            "top-left": (0, 0, 0.5, 0.5),
            "top-right": (0.5, 0, 1, 0.5),
            "bottom-left": (0, 0.5, 0.5, 1),
            "bottom-right": (0.5, 0.5, 1, 1),
            "top": (0, 0, 1, 0.33),
            "bottom": (0, 0.67, 1, 1),
            "left": (0, 0, 0.5, 1),
            "right": (0.5, 0, 1, 1),
            "center": (0.25, 0.25, 0.75, 0.75),
        }

        # Find matching region
        box = None
        for keyword, bbox in regions.items():
            if keyword in focus_lower:
                box = bbox
                break

        if box:
            x1, y1, x2, y2 = [int(v * dim) for v, dim in zip(box, [w, h, w, h])]
            cropped = img.crop((x1, y1, x2, y2))
        else:
            # Unknown focus keyword, return original
            return encode_image(image_path)
    else:
        return encode_image(image_path)

    # Encode cropped image — preserve original format to avoid bloat
    import io
    buffer = io.BytesIO()
    ext = Path(image_path).suffix.lower()
    if ext in (".jpg", ".jpeg"):
        cropped = cropped.convert("RGB")  # JPEG doesn't support alpha
        cropped.save(buffer, format="JPEG", quality=90)
        mime_type = "image/jpeg"
    elif ext == ".webp":
        cropped.save(buffer, format="WEBP", quality=90)
        mime_type = "image/webp"
    else:
        cropped.save(buffer, format="PNG")
        mime_type = "image/png"
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return b64, mime_type


def build_openai_payload(model_name, b64, mime, question, max_tokens):
    """Build payload for OpenAI-compatible chat/completions API."""
    return {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        "max_tokens": max_tokens,
        "stream": False,
    }


def build_anthropic_payload(model_name, b64, mime, question, max_tokens):
    """Build payload for Anthropic Claude Messages API."""
    media_type = mime  # e.g. "image/png"
    return {
        "model": model_name,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": question},
                ],
            }
        ],
    }


def build_gemini_payload(model_name, b64, mime, question, max_tokens):
    """Build payload for Google Gemini generateContent API."""
    return {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": b64,
                        }
                    },
                    {"text": question},
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
        },
    }


def build_ollama_payload(model_name, b64, _mime, question, max_tokens):
    """Build payload for Ollama /api/generate API. MIME type not needed by Ollama."""
    return {
        "model": model_name,
        "prompt": question,
        "images": [b64],
        "stream": False,
        "options": {
            "num_predict": max_tokens,
        },
    }


def ocr_fallback(image_path=None, b64=None, mime=None):
    """OCR fallback chain: easyocr → pytesseract → Pillow basic info.

    Used when --ocr is passed and no vision API key is available.
    Accepts either a file path or base64-encoded image data.

    Returns extracted text (OCR) or image metadata (Pillow).
    """
    import tempfile

    # If b64 data provided, write to temp file for OCR processing
    temp_file = None
    if b64 and not image_path:
        try:
            # Decode base64 to bytes
            img_bytes = base64.b64decode(b64)
            # Determine extension from mime type using reverse MIME_MAP
            ext = ".png"
            if mime:
                reverse_mime = {v: k for k, v in MIME_MAP.items()}
                ext = reverse_mime.get(mime, ".png")
            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(img_bytes)
                image_path = f.name
                temp_file = f.name
        except Exception as e:
            return f"[Error creating temp file for OCR: {e}]"

    if not image_path or not os.path.isfile(image_path):
        return "[Error: No valid image path for OCR]"

    def _try_easyocr():
        """Try easyocr (offline, downloads model on first run)."""
        try:
            import easyocr
            reader = easyocr.Reader(['ch_sim', 'en'], verbose=False)
            results = reader.readtext(image_path)
            if results:
                texts = []
                for (bbox, text, conf) in results:
                    texts.append(f"[{conf:.0%}] {text}")
                return "=== OCR (easyocr) ===\n" + "\n".join(texts)
            return None
        except ImportError:
            return None
        except Exception as e:
            return f"[easyocr error: {e}]"

    def _try_tesseract():
        """Try pytesseract (requires system tesseract installed)."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='chi_sim+eng')
            if text.strip():
                return "=== OCR (tesseract) ===\n" + text.strip()
            return None
        except ImportError:
            return None
        except Exception as e:
            return f"[tesseract error: {e}]"

    def _pillow_info():
        """Pillow basic metadata (final fallback)."""
        try:
            from PIL import Image
            img = Image.open(image_path)
            info = [
                f"=== Image Info (Pillow) ===",
                f"Format: {img.format}",
                f"Size: {img.size[0]}×{img.size[1]} pixels",
                f"Mode: {img.mode}",
                f"File: {image_path}",
            ]
            # Try EXIF if available
            exif = img.getexif()
            if exif:
                info.append(f"EXIF: {len(exif)} tags found")
            return "\n".join(info)
        except ImportError:
            # Final fallback: just file info
            size_mb = os.path.getsize(image_path) / (1024 * 1024)
            return (
                f"=== Image Info ===\n"
                f"File: {image_path}\n"
                f"Size: {size_mb:.1f} MB\n"
                f"Format: {Path(image_path).suffix}\n\n"
                f"Install OCR dependencies for text extraction:\n"
                f"  pip install pillow pytesseract easyocr\n"
                f"  (Note: pytesseract requires system tesseract: https://github.com/tesseract-ocr/tesseract)"
            )

    # Try each in order (inside try/finally for temp file cleanup)
    try:
        result = _try_easyocr()
        if result:
            return result

        result = _try_tesseract()
        if result:
            return result

        result = _pillow_info()
        return result
    finally:
        # Clean up temp file if we created one
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
            except OSError:
                pass


def auto_route(message, attachments=None):
    """Auto-detect if a message needs vision processing.

    Analyzes the message content and attachments to determine if the user's
    message contains images that need vision model processing.

    Args:
        message: User's message text
        attachments: List of attachment paths (optional)

    Returns:
        dict with keys:
            - needs_vision (bool): Whether vision processing is needed
            - image_paths (list): List of image paths found
            - question (str): Extracted question about the image
            - context (str): Conversation context
    """
    result = {
        "needs_vision": False,
        "image_paths": [],
        "question": "",
        "context": "",
    }

    if not message:
        return result

    message_lower = message.lower()

    # ── 1. Check attachments ──────────────────────────────────────
    if attachments:
        for path in attachments:
            if path and os.path.isfile(path):
                ext = Path(path).suffix.lower()
                if ext in SUPPORTED_EXTS:
                    result["needs_vision"] = True
                    result["image_paths"].append(path)

    # ── 2. Check for image references in message ──────────────────
    # Pattern 1: Reasonix attachments - convert to actual filesystem path
    _re_attach = re.compile(r'@\.reasonix/attachments/([^\s]+\.(png|jpg|jpeg|gif|webp|bmp))', re.IGNORECASE)
    for match in _re_attach.finditer(message):
        result["needs_vision"] = True
        # Convert @.reasonix/attachments/xxx.png to actual path
        filename = match.group(1)
        actual_path = os.path.join(os.environ.get("APPDATA", ""), "reasonix", "global-workspace", ".reasonix", "attachments", filename)
        if os.path.isfile(actual_path):
            result["image_paths"].append(actual_path)
        else:
            # Fallback: try relative path
            result["image_paths"].append(match.group(0))

    # Pattern 2: Generic file paths (Windows C:\... or Unix /...)
    _re_path = re.compile(r'(?:[A-Za-z]:\\|[~/])[^\s]+\.(png|jpg|jpeg|gif|webp|bmp)', re.IGNORECASE)
    for match in _re_path.finditer(message):
        if match.group(0) not in result["image_paths"]:
            result["needs_vision"] = True
            result["image_paths"].append(match.group(0))

    # ── 3. Check for standalone image file references ─────────────
    # Require file name to be a standalone token (preceded by space/start, followed by space/end/punctuation)
    _re_file = re.compile(r'(?:^|[\s(]|[@/\\])([\w.-]+\.(?:png|jpg|jpeg|gif|webp|bmp))(?:[\s).,;!?]|$)', re.IGNORECASE)
    for match in _re_file.finditer(message):
        fname = match.group(1)
        if fname not in result["image_paths"]:
            result["needs_vision"] = True
            result["image_paths"].append(fname)

    # ── 4. Check for vision-related keywords ──────────────────────
    # Only trigger on strong signals that the user is talking about images
    # Avoid weak signals like "这是什么" which could be about code/variables
    vision_keywords = [
        # Strong signals (explicitly about images)
        "看这张图", "看图", "截图", "设计稿",
        "这张图", "这张图片", "这张截图", "这张照片",
        "图片内容", "图片里", "图片中",
        "读取图片", "识别图片",
        # English strong signals
        "this image", "the image", "this screenshot",
        "look at this image", "check this screenshot",
        "what's in this image", "what does this image",
    ]

    for keyword in vision_keywords:
        if keyword in message_lower:
            result["needs_vision"] = True
            break

    # ── 5. Extract question and context ───────────────────────────
    # Heuristic: find the line most likely to be a question
    lines = message.strip().split('\n')
    if len(lines) > 1:
        question_indicators = ['?', '？', '什么', '怎么', '为什么', '如何', '哪个',
                               'what', 'how', 'why', 'which', 'describe', 'explain',
                               '帮我', '分析', '看看', '看下']
        question_line = None
        context_lines = []
        for line in lines:
            if question_line is None and any(ind in line.lower() for ind in question_indicators):
                question_line = line
            else:
                context_lines.append(line)
        if question_line:
            result["question"] = question_line
            result["context"] = '\n'.join(context_lines) if context_lines else ""
        else:
            # Fallback: last line is question
            result["context"] = '\n'.join(lines[:-1])
            result["question"] = lines[-1]
    else:
        # Single line: the whole message is the question
        result["question"] = message
        result["context"] = ""

    # ── 6. If we found images but no clear question, use default ──
    if result["needs_vision"]:
        # Check if question is just a file path (no real question)
        is_just_path = (
            not result["question"] or
            result["question"].endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')) or
            '@.reasonix/attachments/' in result["question"]
        )
        if is_just_path:
            result["question"] = "请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"
            result["context"] = ""  # No meaningful context when user just pastes an image

    return result


def auto_detect_backends():
    """Auto-detect available vision backends.

    Checks for available vision backends by testing:
    1. Ollama (local) - check if running and models available
    2. Cloud APIs - check environment variables for API keys
    3. Custom endpoints - check for custom base URLs

    Returns:
        dict with keys:
            - available (list): List of available backend names
            - recommended (str): Recommended backend name
            - details (dict): Detailed info about each backend
    """
    available = []
    details = {}

    # ── 1. Check Ollama (local) ───────────────────────────────────
    try:
        # Check if Ollama is running
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        req = urllib.request.Request(f"{ollama_host}/api/tags")
        req.method = "GET"

        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            models = result.get("models", [])

            # Check for vision models
            vision_models = ["minicpm-v", "llava", "moondream"]
            for model in models:
                model_name = model.get("name", "").lower()
                for vision_model in vision_models:
                    if vision_model in model_name:
                        backend_name = f"ollama:{vision_model}"
                        available.append(backend_name)
                        details[backend_name] = {
                            "type": "local",
                            "model": model_name,
                            "host": ollama_host,
                            "status": "available",
                        }
    except Exception:
        pass

    # ── 2. Check Cloud APIs ───────────────────────────────────────
    # Use MODEL_PRESETS directly to avoid duplication and env var errors
    for backend_name, preset in MODEL_PRESETS.items():
        # Skip Ollama models (already handled above)
        if backend_name.startswith("ollama:"):
            continue

        api_key_env = preset.get("api_key_env", "")
        if not api_key_env:
            continue

        api_key = os.environ.get(api_key_env, "")
        if api_key:
            base_url_env = preset.get("base_url_env", "")
            base_url = os.environ.get(base_url_env, preset.get("default_base_url", ""))

            # Mask API keys in URLs to prevent leaks
            safe_url = base_url
            if api_key and api_key in safe_url:
                safe_url = safe_url.replace(api_key, f"{api_key[:6]}***")

            available.append(backend_name)
            details[backend_name] = {
                "type": "cloud",
                "api_key_env": api_key_env,
                "base_url_env": base_url_env,
                "base_url": safe_url,
                "status": "available",
            }

    # ── 3. Determine recommended backend ──────────────────────────
    # Priority: local > cloud
    recommended = None

    # Prefer local models (no API key needed, faster)
    for backend in available:
        if backend.startswith("ollama:"):
            recommended = backend
            break

    # Fallback to cloud models
    if not recommended and available:
        recommended = available[0]

    return {
        "available": available,
        "recommended": recommended,
        "details": details,
    }


def _resolve_path(path):
    """Resolve image path, converting Reasonix references to actual filesystem paths."""
    if not path:
        return path
    
    # Handle Reasonix attachment references
    if path.startswith('@.reasonix/attachments/'):
        filename = path.split('/')[-1]
        # Try standard Reasonix location
        appdata = os.environ.get("APPDATA", "")
        actual = os.path.join(appdata, "reasonix", "global-workspace", ".reasonix", "attachments", filename)
        if os.path.isfile(actual):
            return actual
        # Fallback: try home directory
        home = os.path.expanduser("~")
        actual = os.path.join(home, ".reasonix", "attachments", filename)
        if os.path.isfile(actual):
            return actual
    
    return path


def smart_question(question, context=None):
    """Enhance user question with context hints.

    Design principle: AUGMENT, don't REPLACE.
    - User's original question stays at the front (highest weight)
    - Context provides lightweight hints as a prefix
    - Multiple categories can combine (UI + error)
    - Extracts concrete info from context (error messages, tech stack)
    - Auto-detects language for hint prefix

    Args:
        question: Original user question
        context: Conversation context (optional)

    Returns:
        Enhanced question (original question preserved at front)
    """
    if not context or not question:
        return question

    context_lower = context.lower()

    # ── Category detection (non-exclusive, can combine) ───────────
    # Code/programming
    code_keywords = ["代码", "code", "函数", "function", "变量", "variable",
                     "类", "class", "方法", "method", "接口", "api",
                     "数据库", "database", "sql", "查询", "query",
                     "框架", "framework", "库", "library"]

    # UI/frontend
    # Note: "组件"/"component" is ambiguous — in debugging context it means "React component has a bug",
    # not "UI design component". We'll filter it out when error is already detected.
    ui_keywords = ["界面", "ui", "design", "设计", "布局", "layout",
                   "组件", "component", "样式", "style", "css", "html",
                   "前端", "frontend", "页面", "page", "截图", "screenshot",
                   "按钮", "button", "输入框", "input", "导航", "nav"]

    # Data/analysis
    data_keywords = ["数据", "data", "图表", "chart", "分析", "analysis",
                     "统计", "statistics", "指标", "metric", "报告", "report",
                     "趋势", "trend", "可视化", "visualization"]

    # Error/debugging
    error_keywords = ["错误", "error", "异常", "exception", "bug", "报错",
                      "失败", "fail", "崩溃", "crash", "日志", "log",
                      "调试", "debug", "堆栈", "stack", "traceback",
                      "报错信息", "错误信息", "error message"]

    detected = []
    if any(kw in context_lower for kw in error_keywords):
        detected.append("error")
    if any(kw in context_lower for kw in code_keywords):
        detected.append("code")

    # UI detection with disambiguation:
    # When error is already detected, exclude ambiguous words like "组件"/"component"
    # that could mean "React component has a bug" rather than "UI design"
    ui_detected = False
    if "error" in detected:
        # Stricter: exclude ambiguous UI words in debugging context
        ui_strict = [kw for kw in ui_keywords if kw not in ("组件", "component")]
        ui_detected = any(kw in context_lower for kw in ui_strict)
    else:
        ui_detected = any(kw in context_lower for kw in ui_keywords)
    if ui_detected:
        detected.append("ui")

    if any(kw in context_lower for kw in data_keywords):
        detected.append("data")

    # No category matched → return original
    if not detected:
        return question

    # ── Extract concrete info from context ────────────────────────
    hints = []

    # Try to extract error message patterns (e.g. "TypeError: xxx")
    import re
    error_patterns = re.findall(
        r'((?:Type|Reference|Syntax|Runtime|Value|Attribute|Key|Index|Name|Import|Module|File)Error[:\s][^\n]{5,80})',
        context
    )
    if error_patterns:
        hints.append(error_patterns[0].strip())

    # Try to extract tech stack mentions
    # Use (?<![A-Za-z]) instead of \b because \b doesn't work between CJK and Latin chars
    tech_patterns = re.findall(
        r'(?<![A-Za-z])(React|Vue|Angular|Next\.js|Nuxt|Django|Flask|FastAPI|Express|Spring|Laravel|Tailwind|Bootstrap|TypeScript|JavaScript|Python|Java|Go|Rust)(?![A-Za-z])',
        context, re.IGNORECASE
    )
    if tech_patterns:
        hints.extend(list(set(tech_patterns))[:3])

    # ── Build lightweight prefix hint ─────────────────────────────
    # Detect language: Chinese or English
    has_cjk = any('\u4e00' <= c <= '\u9fff' for c in question)
    is_english = not has_cjk

    # Category hint tags
    category_tags = {
        "error": "error/debug" if is_english else "错误/调试",
        "code": "code" if is_english else "代码",
        "ui": "UI/frontend" if is_english else "UI/界面",
        "data": "data/chart" if is_english else "数据/图表",
    }

    tag_str = " + ".join(category_tags[c] for c in detected if c in category_tags)
    hint_parts = [f"[{tag_str}]"]

    if hints:
        hint_parts.append(f"[context: {'; '.join(hints[:2])}]")

    prefix = " ".join(hint_parts)

    # ── Final result: prefix + original question (original stays dominant) ──
    return f"{prefix} {question}"


def smart_focus(question, context=None):
    """Auto-detect if region focusing is needed and which region.

    Analyzes the question and context to determine:
    1. Whether focusing is needed
    2. Which region to focus on

    Args:
        question: User's question
        context: Conversation context (optional)

    Returns:
        Tuple of (should_focus: bool, focus_keyword: str or None)
    """
    combined = f"{question or ''} {context or ''}".lower()

    # ── 1. Explicit region keywords in question ──────────────────
    # Direct mention of a region → definitely focus
    region_keywords = {
        # Chinese
        "左上": "左上", "左上角": "左上",
        "右上": "右上", "右上角": "右上",
        "左下": "左下", "左下角": "左下",
        "右下": "右下", "右下角": "右下",
        "顶部": "顶部", "上方": "顶部", "上边": "顶部", "上面": "顶部",
        "底部": "底部", "下方": "底部", "下边": "底部", "下面": "底部",
        "左侧": "左侧", "左边": "左侧", "左半": "左侧",
        "右侧": "右侧", "右边": "右侧", "右半": "右侧",
        "中间": "中间", "中央": "中间", "中心": "中间",
        # English
        "top-left": "top-left", "top right": "top-right",
        "bottom-left": "bottom-left", "bottom right": "bottom-right",
        "top": "top", "bottom": "bottom",
        "left side": "left", "right side": "right",
        "center": "center", "middle": "center",
    }

    for keyword, focus_area in region_keywords.items():
        if keyword in combined:
            return True, focus_area

    # ── 2. Contextual clues — only detect category, don't assume position ──
    # "按钮" could be anywhere. "导航" is usually top. "footer" is usually bottom.
    # But "错误信息" could be in a modal, sidebar, or inline — don't hardcode position.
    # Only detect categories that have strong positional consensus:
    context_clues = {
        # Strong positional consensus (90%+ of cases)
        "导航": "顶部", "nav": "顶部", "header": "顶部",
        "logo": "顶部", "菜单": "顶部", "menu": "顶部",
        "footer": "底部", "页脚": "底部", "底部导航": "底部",
        "侧边栏": "左侧", "sidebar": "左侧", "边栏": "左侧",
    }
    # Removed: 按钮, button, 输入框, input, 报错, error message, console
    # These are too position-ambiguous — let the vision model see the whole image
    # instead of cropping to an assumed position.

    for keyword, focus_area in context_clues.items():
        if keyword in combined:
            return True, focus_area

    # ── 3. No focusing needed ────────────────────────────────────
    return False, None


def ask_with_image(image_path=None, question=None, model_name=None, b64=None, mime=None, context=None, region=None, focus=None):
    """Send image to the configured vision model and return the answer.

    Args:
        image_path: Path to image file (optional if b64+mime provided).
        question:  Question about the image.
        model_name: Vision backend model name.
        b64:       Pre-encoded base64 image data (used with mime).
        mime:      MIME type (e.g. "image/png") when using b64.
        context:   Conversation context for smart question generation.
        region:    Crop region tuple (x1, y1, x2, y2).
        focus:     Focus area keyword (e.g. "左上", "center").

    One of image_path or (b64 + mime) must be provided.
    """

    # ── Smart question generation ──────────────────────────────────
    if context:
        question = smart_question(question, context)

    # ── Smart focus detection ─────────────────────────────────────
    # If user didn't explicitly specify focus/region, try to detect from context
    if not focus and not region and (question or context):
        should_focus, detected_focus = smart_focus(question, context)
        if should_focus and detected_focus:
            focus = detected_focus
            # Notify user that auto-focus is being applied (transparency)
            print(f"[auto-focus] 检测到区域线索，自动聚焦: {detected_focus}", file=sys.stderr)
            print(f"[auto-focus] 如不需要聚焦，请使用 --focus none 显式禁用", file=sys.stderr)
            # Append focus hint to question for the vision model
            question = f"[请特别关注图片的{detected_focus}区域] {question}"

    # ── File size / data size check ────────────────────────────────
    if image_path:
        image_path = _resolve_path(image_path)
        file_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        if file_size_mb > 10:
            raise ValueError(
                f"Image file is {file_size_mb:.1f} MB — exceeds 10 MB limit.\n"
                f"Please compress or resize the image first."
            )
    elif b64:
        # Rough check: base64 is ~1.33x binary size, 10MB binary ≈ 13.3MB base64
        if len(b64) > 14_000_000:
            raise ValueError(
                f"Base64 data is {len(b64) / 1e6:.1f} MB — likely exceeds 10 MB image limit.\n"
                f"Please compress or resize the image first."
            )

    # ── Determine model config ────────────────────────────────────
    model_name = model_name or os.environ.get("MIMO_MODEL", "mimo-v2.5")
    preset = _find_preset(model_name)

    if preset is None:
        # Fallback: treat as OpenAI-compatible custom model
        # User must set MIMO_API_KEY (or override via env)
        preset = DEFAULT_CONFIG.copy()

    # ── Check if this is an Ollama model (no API key needed) ──────
    is_ollama = model_name.startswith("ollama:")

    if not is_ollama:
        api_key = os.environ.get(preset.get("api_key_env", ""), "")
        if not api_key:
            raise EnvironmentError(
                f"{preset.get('api_key_env')} not set.\n"
                f"Run (PowerShell): $env:{preset.get('api_key_env')}='your-key'\n"
                f"Or (bash): export {preset.get('api_key_env')}=your-key\n\n"
                f"Tip: Use --ocr for offline OCR fallback (requires: pip install pillow pytesseract easyocr)"
            )
    else:
        api_key = None  # Ollama doesn't need an API key

    base_url_env = preset.get("base_url_env")
    base_url = (
        os.environ.get(base_url_env) if base_url_env else None
    ) or preset.get("default_base_url", DEFAULT_CONFIG["default_base_url"])

    max_tokens = preset.get("max_tokens", DEFAULT_CONFIG["max_tokens"])

    # ── Encode image (with optional region crop) ─────────────────
    if image_path:
        # --focus none disables auto-focus
        if focus == "none":
            focus = None
        if region or focus:
            b64, mime = crop_region(image_path, region, focus)
        else:
            b64, mime = encode_image(image_path)

    # ── Detect API type and build payload ─────────────────────────
    is_anthropic = "anthropic" in model_name.lower() or "claude" in model_name.lower()
    is_gemini = "gemini" in model_name.lower()
    # is_ollama already defined above at line 942

    if is_ollama:
        # Ollama models
        ollama_model = preset.get("ollama_model")
        if not ollama_model:
            # Extract model name after "ollama:" prefix, with fallback
            parts = model_name.split(":", 1)
            ollama_model = parts[1] if len(parts) > 1 else "minicpm-v"
        payload = build_ollama_payload(ollama_model, b64, mime, question, max_tokens)
        headers = {
            "Content-Type": "application/json",
        }
        base_url = f"{base_url}/api/generate"
    elif is_anthropic:
        payload = build_anthropic_payload(model_name, b64, mime, question, max_tokens)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": preset.get("anthropic_version", "2023-06-01"),
        }
    elif is_gemini:
        payload = build_gemini_payload(model_name, b64, mime, question, max_tokens)
        headers = {
            "Content-Type": "application/json",
        }
        # Gemini uses API key as query param; avoid double ?key
        sep = "&" if "?" in base_url else "?"
        base_url = f"{base_url}{sep}key={api_key}"
    else:
        # OpenAI-compatible (MiMo, GPT, DeepSeek, etc.)
        payload = build_openai_payload(model_name, b64, mime, question, max_tokens)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    # ── Send request ──────────────────────────────────────────────
    # Warn about non-HTTPS connections (security)
    if base_url.startswith("http://") and not base_url.startswith("http://localhost"):
        print(f"[warn] Using non-HTTPS connection: {base_url}", file=sys.stderr)
        print(f"[warn] API key will be sent in plaintext!", file=sys.stderr)

    # In verbose mode, mask API keys in URLs to prevent leaks
    if is_gemini and api_key:
        masked_url = base_url.replace(api_key, f"{api_key[:6]}***{api_key[-4:]}")
        print(f"[info] Request URL: {masked_url}", file=sys.stderr)

    body = json.dumps(payload).encode("utf-8")

    # Retry logic with exponential backoff
    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        # Recreate Request each retry (avoid stale socket state)
        req = urllib.request.Request(
            base_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                break  # Success, exit retry loop
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            # 429 = rate limit → retry with longer wait (use Retry-After header if available)
            # 5xx = server error → retry
            retryable = (e.code == 429 or e.code >= 500)
            if retryable and attempt < max_retries - 1:
                # For 429, use Retry-After header or longer base wait
                if e.code == 429:
                    retry_after = e.headers.get("Retry-After")
                    wait_time = int(retry_after) if retry_after else (2 ** (attempt + 2))  # 4, 8, 16s
                else:
                    wait_time = 2 ** attempt  # 1, 2, 4s
                print(f"[warn] HTTP {e.code}, retrying in {wait_time}s... ({attempt+1}/{max_retries})", file=sys.stderr)
                import time
                time.sleep(wait_time)
                last_error = e
            else:
                raise RuntimeError(
                    f"API error ({e.code}) for model '{model_name}':\n{err_body}"
                ) from e
        except urllib.error.URLError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1, 2, 4 seconds
                print(f"[warn] Network error, retrying in {wait_time}s... ({attempt+1}/{max_retries})", file=sys.stderr)
                import time
                time.sleep(wait_time)
            else:
                raise RuntimeError(
                    f"Network error connecting to {base_url} after {max_retries} attempts:\n{last_error.reason}"
                ) from last_error

    # ── Parse response by API type ────────────────────────────────
    if is_ollama:
        # Ollama response format
        response = result.get("response", "")
        return response or "(no text output)"

    elif is_anthropic:
        content_blocks = result.get("content", [])
        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        ]
        return "\n".join(text_parts) or "(no text output)"

    elif is_gemini:
        candidates = result.get("candidates", [])
        if not candidates:
            # Don't leak raw API response (may contain keys, internal IDs)
            return "(no candidates returned — API returned empty response)"
        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts]
        return "\n".join(text_parts) or "(no text output)"

    else:
        # OpenAI-compatible
        choices = result.get("choices", [])
        if not choices:
            return "(no choices returned — API returned empty response)"
        message = choices[0].get("message", {})
        content = message.get("content", "")
        reasoning = message.get("reasoning_content", "")

        output = ""
        if reasoning:
            output += f"[thinking]\n{reasoning.strip()}\n\n"
        if content:
            output += content.strip()
        else:
            output += "(no text output, possibly token limit)"
        return output


def main():
    parser = argparse.ArgumentParser(
        description="MiMo Vision — 纯文本模型的视觉桥接工具\nVision bridge for text-only LLMs (DeepSeek V4 Flash/Pro, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("image_path", nargs="?", default=None,
                        help="Path to the image file (optional with --list-models)")
    parser.add_argument("question", nargs="?", default="请详细描述这张图片的内容。",
                        help="Question about the image (default: describe)")
    parser.add_argument("--model", "-m",
                        default=os.environ.get("MIMO_MODEL", "mimo-v2.5"),
                        help=f"Vision backend to use (default: env MIMO_MODEL or mimo-v2.5)")
    parser.add_argument("--ocr", action="store_true",
                        help="Use OCR fallback when no vision API key is set (requires: pip install pillow pytesseract easyocr)")
    parser.add_argument("--context", "-c",
                        default=None,
                        help="Conversation context for smart question generation")
    parser.add_argument("--region", "-r",
                        default=None,
                        help="Crop region: x1,y1,x2,y2 (pixels or 0-1 percentages, e.g. '0,0,0.5,0.5' for top-left)")
    parser.add_argument("--focus", "-f",
                        default=None,
                        help="Focus area keyword: 左上/右上/左下/右下/顶部/底部/中间/左侧/右侧 (or English). Use 'none' to disable auto-focus.")
    parser.add_argument("--list-models", action="store_true",
                        help="List supported vision backends and exit")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show debug info")
    parser.add_argument("--type", "-t",
                        default=None,
                        help="Image format hint for stdin mode: png, jpg, jpeg, gif, webp, bmp")
    parser.add_argument("--auto-route", "-ar",
                        default=None,
                        help="Auto-detect if a message needs vision processing (returns JSON)")
    parser.add_argument("--detect-backends", "-db",
                        action="store_true",
                        help="Auto-detect available vision backends (returns JSON)")
    parser.add_argument("--version", "-V",
                        action="version",
                        version="Add Eyes Skills v2.1.0")
    parser.add_argument("--timeout",
                        type=int, default=120,
                        help="API request timeout in seconds (default: 120)")
    parser.add_argument("--output", "-o",
                        default=None,
                        help="Write result to file instead of stdout (e.g. --output result.txt)")

    args = parser.parse_args()

    # ── Auto-route mode ───────────────────────────────────────────
    if args.auto_route:
        result = auto_route(args.auto_route)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # ── Detect backends mode ──────────────────────────────────────
    if args.detect_backends:
        result = auto_detect_backends()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.list_models:
        print("Supported vision backends:")
        print(f"  {'Backend':<35} {'API Key Env':<20} {'Default Base URL'}")
        print("  " + "-" * 100)
        for name, cfg in MODEL_PRESETS.items():
            api_key_env = cfg.get('api_key_env', 'None')
            if api_key_env is None:
                api_key_env = 'None (local)'
            print(f"  {name:<35} {api_key_env:<20} {cfg['default_base_url']}")
        print()
        print("Set env var MIMO_MODEL=<model> to change default.")
        print("Or use --model <name> for one-off usage.")
        print()
        print("Ollama models (local, no API key needed):")
        print("  ollama:minicpm-v    - MiniCPM-V 2.6 (8B, recommended)")
        print("  ollama:llava        - LLaVA 1.6 (7B)")
        print("  ollama:moondream    - Moondream (1.7B, lightweight)")
        return

    if not args.image_path:
        parser.print_help()
        sys.exit(1)

    # ── Stdin mode ────────────────────────────────────────────────
    is_stdin = args.image_path == "-"
    if is_stdin:
        if args.verbose:
            print(f"[img]   (stdin)")
            print(f"[ask]   {args.question}")
            print(f"[model] {args.model}")
            if args.context:
                print(f"[ctx]   {args.context[:50]}...")
            if args.type:
                print(f"[type]  {args.type}")
            print("-" * 50)
        try:
            b64, mime = read_stdin_image(args.type)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        try:
            answer = ask_with_image(
                b64=b64, mime=mime,
                question=args.question,
                model_name=args.model,
                context=args.context,
            )
        except (EnvironmentError, RuntimeError) as e:
            if args.ocr:
                print(f"[warn] Vision API failed ({type(e).__name__}), falling back to OCR...")
                answer = ocr_fallback(b64=b64, mime=mime)
            else:
                print(f"Error: {e}")
                sys.exit(1)
        print(answer)
        return

    # ── File mode ─────────────────────────────────────────────────
    # Resolve Reasonix attachment paths
    args.image_path = _resolve_path(args.image_path)
    
    if not os.path.isfile(args.image_path):
        print(f"Error: file not found: {args.image_path}")
        sys.exit(1)

    if args.verbose:
        print(f"[img]   {args.image_path}")
        print(f"[ask]   {args.question}")
        print(f"[model] {args.model}")
        if args.context:
            print(f"[ctx]   {args.context[:50]}...")
        if args.region:
            print(f"[region] {args.region}")
        if args.focus:
            print(f"[focus]  {args.focus}")
        if args.ocr:
            print(f"[ocr]   enabled (fallback when no API key)")
        print("-" * 50)

    # Apply smart_question enhancement if context provided
    enhanced_question = args.question
    if args.context:
        enhanced_question = smart_question(args.question, args.context)
        if args.verbose and enhanced_question != args.question:
            print(f"[enhanced] {enhanced_question}")

    # Parse region if provided
    region = None
    if args.region:
        try:
            region = tuple(float(x.strip()) for x in args.region.split(","))
            if len(region) != 4:
                raise ValueError
        except ValueError:
            print(f"Error: --region must be x1,y1,x2,y2 (e.g. '0,0,0.5,0.5')")
            sys.exit(1)

    try:
        answer = ask_with_image(args.image_path, enhanced_question, args.model,
                                context=args.context, region=region, focus=args.focus)
    except (EnvironmentError, RuntimeError) as e:
        # EnvironmentError: No API key set
        # RuntimeError: Network error or API error
        if args.ocr:
            print(f"[warn] Vision API failed ({type(e).__name__}), falling back to OCR...")
            answer = ocr_fallback(args.image_path)
        else:
            raise  # Re-raise the original error
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(answer)
        print(f"[saved] Result written to: {args.output}")
    else:
        print(answer)


if __name__ == "__main__":
    main()
