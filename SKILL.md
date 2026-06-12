---
name: vision
description: Vision bridge for text-only models (DeepSeek V4, etc.). Invoke when user pastes an image and your model cannot see it — this skill delegates to external vision APIs and returns a description.
run_as: inline
---

# MiMo Vision — 纯文本模型的「视觉桥接」Skill

## 这是什么？

如果你的 AI 模型**不支持多模态**（例如 DeepSeek V4 Flash、V4 Pro 等纯文本模型），当用户贴图时它"看不见"。

这个 Skill 就是给模型配一副**外挂眼睛**：

```
用户贴图 → 纯文本模型看不见 → Skill 调用外部视觉 API
    → 获得图片文字描述 → 纯文本模型拿到描述，能「看懂」了
```

## 安装

### 方式 1：从本地文件夹安装

在 Reasonix 中运行：

```
install-capability source="/path/to/mimo-vision-skill"
```

### 方式 2：从 GitHub 安装

```bash
git clone https://github.com/<your-org>/mimo-vision-skill.git
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

当用户粘贴/拖放了一张图片，而**你正在运行的模型不支持多模态**时：

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
python "<skill_dir>/mimo_vision.py" "<absolute_image_path>" "<question>" [--model <vision_backend>]
```

- 如果用户没有具体问题，默认：`"请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"`
- 如果是 UI/前端截图，可以用：`"分析这个页面的布局结构"`
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

查看完整列表：
```bash
python "<skill_dir>/mimo_vision.py" --list-models
```

## 典型场景

**场景 1：用户贴了一张 UI 截图**
```
你（文本模型）→ 看不见图 → 调用 Skill → 视觉后端返回
  "这是一个登录页面，顶部有 Logo，中间是用户名/密码输入框..."
你 → "这是登录页面的截图。表单有两个输入框..."
```

**场景 2：用户贴了报错截图**
```
你 → 调用 Skill → "控制台显示 TypeError: undefined is not a function..."
你 → "报错是 TypeError，原因是 xxx 变量未定义..."
```

## 注意事项

- 图片上限 10MB，支持 PNG/JPG/JPEG/GIF/WebP/BMP
- 视觉后端的文字描述质量取决于后端模型的能力
- 这不是让你的模型本身支持多模态——而是通过外部 API 获取图片描述
- 将描述融入你的回答，不要原样粘贴
- `--verbose` / `-v` 可输出请求调试信息
- `--ocr` 启用 OCR 降级：当没有任何视觉 API Key 时，自动降级为 OCR 文字提取（需安装 `pip install pillow pytesseract easyocr`，按优先级逐个尝试）
