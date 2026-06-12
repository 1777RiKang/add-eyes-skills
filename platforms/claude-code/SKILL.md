---
name: vision
description: Vision bridge for text-only models — delegates to external vision APIs when your model cannot see images. Use when user pastes/drops an image and the model lacks multimodal support.
triggers:
  - user pastes an image
  - user drags a screenshot
  - user says "看这张图" / "look at this image" / "这张截图"
  - user asks about an image you can't see
platforms:
  - Claude Code
  - Claude.ai
  - Anthropic API
---

# MiMo Vision — 视觉桥接

## 这是什么？

如果你的 AI 模型**不支持多模态**（如 DeepSeek 等纯文本模型），当用户贴图时你"看不见"。

这个 Skill 就是给你配一副**外挂眼睛**：

```
用户贴图 → 纯文本模型看不见 → 调用外部视觉 API
    → 获得图片文字描述 → 你能「看懂」并回答
```

## 安装

```bash
git clone https://github.com/<your-org>/mimo-vision-skill.git
cd mimo-vision-skill
```

### 配置 API Key（至少一个）

```bash
# 推荐：小米 MiMo（国内直连，性价比高）
export MIMO_API_KEY='your-mimo-key'

# 或 OpenAI
export OPENAI_API_KEY='your-openai-key'

# 或 Anthropic Claude
export ANTHROPIC_API_KEY='your-anthropic-key'

# 或 Google Gemini
export GEMINI_API_KEY='your-gemini-key'
```

## 使用方式

当用户贴了一张图片，而**你正在运行的模型不支持多模态**时：

### 步骤 1：定位图片

用户贴图后，按以下优先级快速找到图片文件：

1. **用户提供了路径** → 直接用
2. **检查 `~/Pictures/Screenshots/` 下最新文件** → `ls -lt ~/Pictures/Screenshots/*.png | head -3`
3. **搜一轮就停**：只在截图目录和当前 session temp 目录搜一次
4. **找不到就立即问用户** → ❌ **禁止全盘反复搜索！** 贴图可能被 VSCode/IDE 直接内嵌在消息里不落盘。直接说："找不到图片文件，麻烦告诉我路径或手动保存一下。"

### 步骤 2：决定视觉后端

按此优先级：
1. 用户明确指定（如"用 GPT-4o 看"）
2. 环境变量 `MIMO_MODEL`
3. 默认 `mimo-v2.5`

### 步骤 3：执行视觉分析

在项目根目录（`mimo-vision-skill/`）下运行：

```bash
python "<skill_dir>/mimo_vision.py" "<absolute_image_path>" "<question>" [--model <vision_backend>]
```

- 如果用户没有具体问题，用：`"请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"`
- 如果是 UI/前端截图：`"分析这个页面的布局结构"`
- 如果是报错截图：`"提取截图中的错误信息并解释"`
- 用用户的交流语言提问（中文/英文）
- **拿到文字描述后，用你自己的语言能力继续处理**（分析、修复、重构等）

### 步骤 4：融入回答

将视觉后端返回的文字描述**融入你自己的回答**，而不是直接粘贴原始输出。

## 视觉后端速查

| 后端 | 命令 | 需要 Key |
|---|---|---|
| `mimo-v2.5`（默认） | `--model mimo-v2.5` | `MIMO_API_KEY` |
| `gpt-4o` | `--model gpt-4o` | `OPENAI_API_KEY` |
| `claude-sonnet-4-6` | `--model claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| `claude-3-5-sonnet-20241022` | `--model claude-3-5-sonnet-20241022` | `ANTHROPIC_API_KEY` |
| `gemini-1.5-pro` | `--model gemini-1.5-pro` | `GEMINI_API_KEY` |

查看完整列表：
```bash
python "<skill_dir>/mimo_vision.py" --list-models
```

## 典型场景

**场景 1：用户贴了一张 UI 截图**
```
你（文本模型）→ 看不见图 → 调用 mimo_vision.py
  → 返回 "这是一个登录页面，顶部有 Logo，中间是用户名/密码输入框..."
你 → "这是登录页面的截图。表单有两个输入框..."
```

**场景 2：用户贴了报错截图**
```
你 → 调用 mimo_vision.py
  → 返回 "终端显示 TypeError: undefined is not a function..."
你 → "报错是 TypeError，原因是 xxx 变量未定义..."
```

**场景 3：用户贴了架构图/流程图**
```
你 → 调用 mimo_vision.py --model claude-sonnet-4-6
  → 返回 "图中显示三层架构：前端 (React) → API 网关 → 微服务..."
你 → 分析架构，给建议
```

## 注意事项

- 图片上限 10MB，支持 PNG/JPG/JPEG/GIF/WebP/BMP
- 视觉后端的描述质量取决于后端模型的能力
- 将描述融入你的回答，不要原样粘贴
- `--verbose` / `-v` 可输出请求调试信息
- `--ocr` 启用 OCR 降级：当没有任何视觉 API Key 时，自动降级为 OCR 文字提取（需安装 `pip install pillow pytesseract easyocr`）
