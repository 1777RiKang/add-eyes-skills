---
description: MiMo Vision — 纯文本模型的视觉桥接，通过外部视觉 API 让模型"看懂"图片
globs:
  - "*.png"
  - "*.jpg"
  - "*.jpeg"
  - "*.gif"
  - "*.webp"
  - "*.bmp"
alwaysApply: false
---

# MiMo Vision — 视觉桥接（Cursor 版）

## 触发条件

当以下任一情况发生时，使用本规则：
- 用户粘贴/拖放图片并询问图片内容
- 用户提到"看这张图"、"这张截图"、"look at this image"
- 当前模型不支持多模态，用户却贴了图

## 工作流程

### 1. 检测图片

1. **用户提供了路径** → 直接用
2. **检查 `~/Pictures/Screenshots/` 下最新文件** → `ls -lt ~/Pictures/Screenshots/*.png | head -3`
3. **搜一轮就停**：只在截图目录和 session temp 搜一次
4. **找不到就立即问用户** → 禁止全盘反复搜索！贴图可能被 IDE 内嵌不落盘。

### 2. 选择视觉后端

优先级：
1. 用户明确指定的模型
2. 环境变量 `MIMO_MODEL`
3. 默认 `mimo-v2.5`

### 3. 调用视觉分析

在终端中运行（在 mimo-vision-skill 目录下）：

```bash
python mimo_vision.py "<图片路径>" "<问题>" [--model <视觉后端>]
```

默认问题（用户无具体问题时）：
```
"请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"
```

UI/前端截图的推荐问题：
```
"分析这个页面的布局结构、组件层级和UI问题"
```

报错截图的推荐问题：
```
"提取截图中的所有错误信息、日志和关键细节"
```

### 4. 解析并回答

拿到视觉后端的文字描述后，**用你自己的语言能力**分析、解释、修复或重构，而不是直接粘贴原始输出。

## 视觉后端

| 后端 | Key 环境变量 | 备注 |
|---|---|---|
| `mimo-v2.5` | `MIMO_API_KEY` | 默认，国内直连 |
| `gpt-4o` | `OPENAI_API_KEY` | OpenAI |
| `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` | Anthropic 最新 |
| `claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` | Claude 3.5 |
| `gemini-1.5-pro` | `GEMINI_API_KEY` | Google |

完整列表：`python mimo_vision.py --list-models`

## OCR 降级（无 API Key 时）

```bash
pip install pillow pytesseract easyocr
python mimo_vision.py screenshot.png --ocr
```

注意：`pytesseract` 还需要系统安装 [tesseract-ocr](https://github.com/tesseract-ocr/tesseract)。

## 限制

- 图片上限 10MB
- 支持格式：PNG/JPG/JPEG/GIF/WebP/BMP
- 视觉描述质量取决于后端模型能力
