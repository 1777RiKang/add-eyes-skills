---
name: add-eyes
description: Vision bridge for text-only models ONLY. DO NOT use this skill if your model natively supports multimodal/vision (like GPT-4o, Claude 3.5, Gemini, MiMo V2.5). Only use when your model cannot see images at all.
run_as: inline
---

# Add Eyes — 纯文本模型的视觉桥接

## ⚠️ 重要：你是否需要这个 Skill？

**如果你的模型原生支持多模态（能直接看图），请不要使用这个 Skill。**

| 模型 | 能原生看图？ | 是否需要此 Skill |
|------|------------|-----------------|
| MiMo V2.5 | ✅ 是 | ❌ 不需要 |
| GPT-4o | ✅ 是 | ❌ 不需要 |
| Claude 3.5 Sonnet | ✅ 是 | ❌ 不需要 |
| Gemini 1.5 Pro | ✅ 是 | ❌ 不需要 |
| DeepSeek V4 Flash/Pro | ❌ 否 | ✅ 需要 |
| MiMo V2.5 Pro | ❌ 否 | ✅ 需要 |

**判断方法：** 如果用户贴图后你发现自己"看不见"图片，才使用这个 Skill。

## 这是什么？

如果你的 AI 模型**不支持多模态**（例如 DeepSeek V4 Flash、V4 Pro 等纯文本模型），当用户贴图时它"看不见"。

这个 Skill 帮模型**获取图片的文字描述**：

```
用户贴图 → 纯文本模型看不见 → Skill 调用外部视觉 API
    → 获得图片文字描述 → 纯文本模型拿到描述，能「看懂」了
```

## 安装

### 方式 1：从本地文件夹安装

在 Reasonix 中运行：

```
install-capability source="/path/to/add-eyes-skills"
```

### 方式 2：从 GitHub 安装

```bash
git clone https://github.com/1777RiKang/add-eyes-skills.git
# 然后按方式 1 安装
```

### 配置视觉后端 Key

至少配一个（推荐 MiMo）：

```bash
# MiMo（推荐，性价比高，国内直连）
export MIMO_API_KEY='your-mimo-key'

# 或 OpenAI
export OPENAI_API_KEY='your-openai-key'

# 或 Claude
export ANTHROPIC_API_KEY='your-anthropic-key'
```

## 使用方式（给 AI Agent 的指令）

**重要：当用户消息中出现以下任何信号时，你必须立即调用 add_eyes.py 来分析图片。这是你的视觉能力来源。**

### 触发信号（满足任一即触发）

1. 消息包含 `@.reasonix/attachments/` 路径
2. 消息包含图片文件名（`.png`/`.jpg`/`.jpeg`/`.gif`/`.webp`/`.bmp`）
3. 消息包含 `.docx` 或 `.pdf` 文件
4. 用户说"看这张图"、"分析截图"、"帮我看看"
5. 消息末尾附带图片扩展名

**禁止行为：永远不要说"我无法查看图片"或"我无法识别图片"。你有视觉能力——通过 add_eyes.py。**

### 🚀 自动路由（推荐）

检测图片是否存在：

**安装方式：**

1. **Reasonix**：将 `ALWAYS_ON.md` 内容添加到系统提示词
2. **Claude Code**：将 `ALWAYS_ON.md` 添加到 `.claude/instructions.md`
3. **Cursor**：将 `ALWAYS_ON.md` 添加到 `.cursor/rules/` 目录
4. **GitHub Copilot**：将 `ALWAYS_ON.md` 添加到 `.github/copilot-instructions.md`

**效果：**
- AI 永远不会说"我看不见图片"
- 每次收到图片，自动调用 vision skill
- 无需手动触发，完全自动化

### 自动检测后端（推荐）

**首次使用时，自动检测可用的视觉后端：**

```bash
python "C:\Users\shi_h\AppData\Roaming\reasonix\global-workspace\add-eyes-skills\add_eyes.py" --detect-backends
```

**输出示例：**
```json
{
  "available": ["ollama:minicpm-v", "mimo-v2.5", "gpt-4o"],
  "recommended": "ollama:minicpm-v",
  "details": {
    "ollama:minicpm-v": {
      "type": "local",
      "model": "minicpm-v:latest",
      "host": "http://localhost:11434",
      "status": "available"
    }
  }
}
```

**使用推荐后端：**
```bash
python add_eyes.py screenshot.png "描述这张图" --model ollama:minicpm-v
```

### 自动路由（备选）

如果不想注入系统提示词，可以使用自动路由：

```bash
python "C:\Users\shi_h\AppData\Roaming\reasonix\global-workspace\add-eyes-skills\add_eyes.py" --auto-route "<用户消息>"
```

**自动路由会：**
1. 检测消息中是否包含图片引用（`@.reasonix/attachments/xxx.png`）
2. 检测消息中是否提到图片相关关键词（"看图"、"截图"、"分析这个"等）
3. 如果需要视觉处理，返回 `{ "needs_vision": true, "image_paths": [...], "question": "...", "context": "..." }`
4. 如果不需要视觉处理，返回 `{ "needs_vision": false }`

**自动路由规则：**

| 检测项 | 示例 | 触发 |
|-------|------|------|
| 图片引用 | `@.reasonix/attachments/screenshot.png` | ✅ |
| 图片文件名 | `image.png`, `photo.jpg` | ✅ |
| 视觉关键词 | "看这张图"、"分析截图"、"look at this" | ✅ |
| 纯文本 | "帮我写个函数" | ❌ |

### 手动调用（备选）

如果自动路由返回 `needs_vision: true`，使用以下命令：

### 步骤 1：定位图片

按以下优先级快速找到：

1. **用户提供了路径** → 直接用
2. **检查 `~/Pictures/Screenshots/` 下最新文件** → `ls -lt ~/Pictures/Screenshots/*.png | head -3`
3. **搜一轮就停**：只在截图目录和当前 session temp 目录搜一次
4. **找不到就立即问用户** → ❌ **禁止全盘反复搜索！** 贴图可能被 IDE 直接内嵌在消息里不落盘。

### 步骤 2：决定视觉后端

按此优先级：
1. 用户明确指定（如"用 GPT-4o 看"）
2. 环境变量 `MIMO_MODEL`
3. 默认 `mimo-v2.5`

如果用户没说，直接使用默认即可。

### 步骤 3：执行视觉分析

```bash
python "C:\Users\shi_h\AppData\Roaming\reasonix\global-workspace\add-eyes-skills\add_eyes.py" "<absolute_image_path>" "<question>" --model ollama:minicpm-v --context "<对话上下文>"
```

**重要：使用 `--context` 参数传递对话上下文，启用智能提问！**

- `--context` 会根据对话内容自动优化提问方式：
  - 如果上下文涉及代码/编程 → 自动问"分析代码内容、语法错误、逻辑问题"
  - 如果上下文涉及 UI/界面 → 自动问"分析布局结构、组件组成、交互元素"
  - 如果上下文涉及数据/图表 → 自动问"分析数据类型、趋势、关键指标"
  - 如果上下文涉及错误/调试 → 自动问"分析错误信息、异常堆栈、解决方案"
- 如果没有 `--context`，使用默认问题
- 用用户的交流语言提问（中文/英文）
- **拿到文字描述后，用你自己的语言能力继续处理它**（比如分析、修复、重构等）

### 步骤 4：返回结果

将视觉后端返回的文字描述**融入你自己的回答**，而不是直接丢给用户原始输出。你的角色是用纯文本模型的语言能力来"理解"这张图。

## 视觉后端列表（外挂眼睛）

| 后端标识符 | API | 需要 Key |
|-----------|-----|---------|
| `mimo-v2.5` | 小米 MiMo | `MIMO_API_KEY` |
| `gpt-4o` | OpenAI | `OPENAI_API_KEY` |
| `gpt-4-turbo` | OpenAI | `OPENAI_API_KEY` |
| `claude-3-5-sonnet-20241022` | Anthropic | `ANTHROPIC_API_KEY` |
| `claude-3-opus-20240229` | Anthropic | `ANTHROPIC_API_KEY` |
| `gemini-1.5-pro` | Google | `GEMINI_API_KEY` |
| `gemini-1.5-flash` | Google | `GEMINI_API_KEY` |
| `ollama:minicpm-v` | 本地 Ollama | 无需 Key |
| `ollama:llava` | 本地 Ollama | 无需 Key |
| `ollama:moondream` | 本地 Ollama | 无需 Key |

查看完整列表：
```bash
python "C:\Users\shi_h\AppData\Roaming\reasonix\global-workspace\add-eyes-skills\add_eyes.py" --list-models
```

## 典型场景

**场景 1：用户在讨论代码问题，然后贴了一张截图**
```bash
python add_eyes.py screenshot.png "帮我看看" --context "我在写一个 Python 函数，但是出现了 TypeError"
# 智能提问 → "请分析这张图片中的错误信息、异常堆栈或问题描述..."
```

**场景 2：用户在讨论 UI 设计，然后贴了一张界面截图**
```bash
python add_eyes.py screenshot.png "帮我看看" --context "我在设计一个登录页面，但是布局有问题"
# 智能提问 → "请分析这个界面的布局结构、组件组成、颜色搭配..."
```

**场景 3：用户在分析数据，然后贴了一张图表**
```bash
python add_eyes.py chart.png "帮我看看" --context "我在分析用户行为数据，但是图表看不懂"
# 智能提问 → "请分析这张图片中的数据、图表或统计信息..."
```

## 注意事项

- 图片上限 10MB，支持 PNG/JPG/JPEG/GIF/WebP/BMP
- 视觉后端的文字描述质量取决于后端模型的能力
- 这不是让你的模型本身支持多模态——而是通过外部 API 获取图片描述
- 将描述融入你的回答，不要原样粘贴
- `--verbose` / `-v` 可输出请求调试信息
- `--ocr` 启用 OCR 降级：当没有任何视觉 API Key 时，自动降级为 OCR 文字提取（需安装 `pip install pillow pytesseract easyocr`，按优先级逐个尝试）
