# MiMo Vision — Vision Bridge for GitHub Copilot

## When to Use

Execute the vision pipeline whenever:
- The user pastes or drags an image into the chat and asks about its content
- The current model lacks multimodal support (e.g., DeepSeek V4 Flash/Pro, GPT-4 base)
- The user says phrases like "看这张图", "what's in this image", "check this screenshot"

## How It Works

```
User pastes image → text-only model can't see it
  → Call external vision API via mimo_vision.py
  → Get text description → model "sees" and responds
```

## Workflow

### Step 1: Locate the image file

Quick search, then ask:

1. Check if the user provided a path — use it directly
2. Check `~/Pictures/Screenshots/` for the latest file → `ls -lt ~/Pictures/Screenshots/*.png | head -3`
3. **Search once, then stop** — screenshot dir and session temp only
4. **Ask the user immediately if not found** → ❌ **Do NOT recursively search the entire disk!** Images may be embedded inline by VSCode/IDE and never touch disk. Say: "Can't find the image file — can you tell me the path or save it manually?"

### Step 2: Choose a vision backend

Priority order:
1. User-specified model (e.g., "use GPT-4o")
2. `MIMO_MODEL` environment variable
3. Default: `mimo-v2.5`

### Step 3: Run vision analysis

```bash
python "<repo_root>/mimo_vision.py" "<image_path>" "<question>" [--model <backend>]
```

Default question when user has no specific one:
"请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"

For UI/frontend screenshots:
"分析这个页面的布局结构、组件和问题"

For error screenshots:
"提取截图中的所有错误信息和日志"

### Step 4: Integrate the response

Process the returned text description with your own language capabilities — analyze, fix, refactor, or explain. Never paste raw API output directly.

## Available Backends

| Model | API Key Env Var | Notes |
|---|---|---|
| `mimo-v2.5` (default) | `MIMO_API_KEY` | Xiaomi MiMo, direct China access |
| `gpt-4o` | `OPENAI_API_KEY` | OpenAI |
| `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` | Latest Claude |
| `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` | Claude 3.5 |
| `gemini-1.5-pro` | `GEMINI_API_KEY` | Google Gemini |

List all: `python mimo_vision.py --list-models`

## OCR Fallback (no API key)

```bash
pip install pillow pytesseract easyocr
python mimo_vision.py screenshot.png --ocr
```

pytesseract requires system tesseract-ocr installation.

## Constraints

- Max image size: 10 MB
- Supported formats: PNG, JPG, JPEG, GIF, WebP, BMP
- Description quality depends on the vision backend model
