#!/usr/bin/env python3
"""
MiMo Vision — 纯文本模型的视觉桥接工具
Vision bridge for text-only LLMs (DeepSeek V4 Flash/Pro, etc.)

纯文本模型（如 DeepSeek V4 Flash/Pro）看不懂图片。
这个脚本将图片编码后发送到外部视觉 API，返回文字描述，
让纯文本模型「看到」图片内容。

Usage:
  python mimo_vision.py <image_path> [question] [--model <backend>]
  python mimo_vision.py - [question] [--model <backend>]  # read base64 from stdin
  python mimo_vision.py screenshot.png
  python mimo_vision.py screenshot.png "What is in this image?" --model gpt-4o

Stdin formats (when image_path is "-"):
  - Raw base64: echo "<base64>" | python mimo_vision.py - "describe" --type png
  - Data URI:   echo "data:image/png;base64,<base64>" | python mimo_vision.py -

Vision backends (via env config):
  Backend                Env Key              Env Base URL (optional)
  ─────────────────────────────────────────────────────────────────
  mimo-v2.5      (def)  MIMO_API_KEY         MIMO_BASE_URL
  gpt-4o                OPENAI_API_KEY       OPENAI_BASE_URL
  gpt-4-turbo           OPENAI_API_KEY       OPENAI_BASE_URL
  claude-3.5-sonnet     ANTHROPIC_API_KEY    ANTHROPIC_BASE_URL
  gemini-1.5-pro        GEMINI_API_KEY       GEMINI_BASE_URL
"""

import sys
import os
import base64
import json
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
}


def read_stdin_image(ext_hint=None):
    """Read base64 image data from stdin.

    Supports two formats:
    1. Raw base64:  echo "<base64>" | python mimo_vision.py -
    2. Data URI:    echo "data:image/png;base64,<base64>" | python mimo_vision.py -

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


def ocr_fallback(image_path):
    """OCR fallback chain: easyocr → pytesseract → Pillow basic info.

    Used when --ocr is passed and no vision API key is available.
    Returns extracted text (OCR) or image metadata (Pillow).
    """

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

    # Try each in order
    result = _try_easyocr()
    if result:
        return result

    result = _try_tesseract()
    if result:
        return result

    result = _pillow_info()
    return result


def ask_with_image(image_path=None, question=None, model_name=None, b64=None, mime=None):
    """Send image to the configured vision model and return the answer.

    Args:
        image_path: Path to image file (optional if b64+mime provided).
        question:  Question about the image.
        model_name: Vision backend model name.
        b64:       Pre-encoded base64 image data (used with mime).
        mime:      MIME type (e.g. "image/png") when using b64.

    One of image_path or (b64 + mime) must be provided.
    """

    # ── File size / data size check ────────────────────────────────
    if image_path:
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
    preset = MODEL_PRESETS.get(model_name)

    if preset is None:
        # Fallback: treat as OpenAI-compatible custom model
        # User must set MIMO_API_KEY (or override via env)
        preset = DEFAULT_CONFIG.copy()

    api_key = os.environ.get(preset["api_key_env"], "")
    if not api_key:
        raise EnvironmentError(
            f"{preset['api_key_env']} not set.\n"
            f"Run (PowerShell): $env:{preset['api_key_env']}='your-key'\n"
            f"Or (bash): export {preset['api_key_env']}=your-key\n\n"
            f"Tip: Use --ocr for offline OCR fallback (requires: pip install pillow pytesseract easyocr)"
        )

    base_url_env = preset.get("base_url_env")
    base_url = (
        os.environ.get(base_url_env) if base_url_env else None
    ) or preset.get("default_base_url", DEFAULT_CONFIG["default_base_url"])

    max_tokens = preset.get("max_tokens", DEFAULT_CONFIG["max_tokens"])

    # ── Encode image ──────────────────────────────────────────────
    if image_path:
        b64, mime = encode_image(image_path)

    # ── Detect API type and build payload ─────────────────────────
    is_anthropic = "anthropic" in model_name.lower() or "claude" in model_name.lower()
    is_gemini = "gemini" in model_name.lower()

    if is_anthropic:
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
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"API error ({e.code}) for model '{model_name}':\n{err_body}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Network error connecting to {base_url}:\n{e.reason}"
        ) from e

    # ── Parse response by API type ────────────────────────────────
    if is_anthropic:
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
            return f"(no candidates returned)\nRaw: {json.dumps(result, indent=2, ensure_ascii=False)}"
        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [p.get("text", "") for p in parts]
        return "\n".join(text_parts) or "(no text output)"

    else:
        # OpenAI-compatible
        choices = result.get("choices", [])
        if not choices:
            return f"(no choices returned)\nRaw: {json.dumps(result, indent=2, ensure_ascii=False)}"
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
                        help=f"Vision backend to use (default: mimo-v2.5)")
    parser.add_argument("--ocr", action="store_true",
                        help="Use OCR fallback when no vision API key is set (requires: pip install pillow pytesseract easyocr)")
    parser.add_argument("--list-models", action="store_true",
                        help="List supported vision backends and exit")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show debug info")
    parser.add_argument("--type", "-t",
                        default=None,
                        help="Image format hint for stdin mode: png, jpg, jpeg, gif, webp, bmp")

    args = parser.parse_args()

    if args.list_models:
        print("Supported vision backends:")
        print(f"  {'Backend':<35} {'API Key Env':<20} {'Default Base URL'}")
        print("  " + "-" * 100)
        for name, cfg in MODEL_PRESETS.items():
            print(f"  {name:<35} {cfg['api_key_env']:<20} {cfg['default_base_url']}")
        print()
        print("Set env var MIMO_MODEL=<model> to change default.")
        print("Or use --model <name> for one-off usage.")
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
            )
        except EnvironmentError as e:
            print(f"Error: {e}")
            sys.exit(1)
        print(answer)
        return

    # ── File mode ─────────────────────────────────────────────────
    if not os.path.isfile(args.image_path):
        print(f"Error: file not found: {args.image_path}")
        sys.exit(1)

    if args.verbose:
        print(f"[img]   {args.image_path}")
        print(f"[ask]   {args.question}")
        print(f"[model] {args.model}")
        if args.ocr:
            print(f"[ocr]   enabled (fallback when no API key)")
        print("-" * 50)

    try:
        answer = ask_with_image(args.image_path, args.question, args.model)
    except EnvironmentError:
        # No API key set — try OCR fallback if --ocr is enabled
        if args.ocr:
            print(f"[warn] No vision API key configured, falling back to OCR...")
            answer = ocr_fallback(args.image_path)
        else:
            raise  # Re-raise the original error
    print(answer)


if __name__ == "__main__":
    main()
