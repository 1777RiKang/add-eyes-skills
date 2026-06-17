# Add Eyes Skills 👁️

> **帮纯文本模型获取图片描述** — 让 DeepSeek V4、MiMo V2.5 Pro 等不支持多模态的模型也能"看懂"图片  
> Vision bridge for text-only LLMs — let DeepSeek V4, etc. "see" images via external vision APIs

[![Reasonix Skill](https://img.shields.io/badge/Reasonix-Skill-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green)](add_eyes.py)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 这是什么？

纯文本模型看不懂图片。这个工具帮你调用外部视觉 API 获取图片的文字描述，然后交给你的模型处理。

```
用户贴图 → 你的模型看不见 → 本工具调用视觉 API
    → 返回文字描述 → 你的模型拿到描述继续推理
```

**注意：** 这不是"能力融合"，是"视觉桥接"——你的模型拿到的是文字描述，不是真正的视觉感知。描述质量取决于视觉后端。

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 🚀 **Always-on 模式** | 注入系统提示词，AI 永远不会说"我看不见图片" |
| 🔍 **自动检测后端** | 启动时自动检测可用的视觉后端，无需手动配置 |
| 🧠 **智能提问** | 根据对话上下文自动优化提问（代码/UI/数据/错误场景） |
| 🎯 **自动路由** | 自动检测消息是否需要视觉处理 |
| 🖼️ **13 个视觉后端** | 云端 + 本地，覆盖 MiMo/GPT/Claude/Gemini/Ollama |
| 🏠 **本地模型** | Ollama (MiniCPM-V/LLaVA/Moondream)，免费+隐私 |
| 📝 **OCR 降级** | 无 API Key 时自动降级为 OCR 文字提取 |
| 🔄 **自动重试** | 指数退避重试，5xx/网络错误自动恢复 |
| 🌐 **多平台** | Reasonix、Claude Code、Cursor、GitHub Copilot |
| 🔒 **核心零依赖** | 纯 Python 标准库即可运行（高级功能如 OCR/区域聚焦需可选依赖） |

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/1777RiKang/add-eyes-skills.git
cd add-eyes-skills
```

### 2. 配置视觉后端（至少一个）

**方案 A：本地模型（推荐，免费，隐私，无地域限制）**

```bash
# 安装 Ollama：https://ollama.ai
ollama pull minicpm-v
```

**方案 B：云端 API**

> ⚠️ 默认后端 MiMo 需要国内网络访问。海外用户请配置 OpenAI、Claude 或 Gemini Key。

```bash
# MiMo（国内直连，性价比高）
# PowerShell:
$env:MIMO_API_KEY = 'your-mimo-key'
# bash:
export MIMO_API_KEY='your-mimo-key'

# 海外用户推荐 OpenAI / Claude / Gemini
export OPENAI_API_KEY='your-openai-key'
```

### 3. 检测可用后端

```bash
python add_eyes.py --detect-backends
```

输出示例：
```json
{
  "available": ["ollama:minicpm-v", "mimo-v2.5"],
  "recommended": "ollama:minicpm-v"
}
```

### 4. 测试

```bash
python add_eyes.py test.png "描述这张图片"
```

### 5. 安装到你的 AI 编程助手

<details open>
<summary><b>Reasonix</b></summary>

```bash
cp SKILL.md ~/.reasonix/skills/add-eyes.md
cp ALWAYS_ON.md ~/.reasonix/skills/ALWAYS_ON.md
```
</details>

<details>
<summary><b>Claude Code</b></summary>

```bash
mkdir -p ~/.claude/skills/vision
cp platforms/claude-code/SKILL.md ~/.claude/skills/vision/
```
</details>

<details>
<summary><b>Cursor</b></summary>

```bash
mkdir -p .cursor/rules
cp .cursor/rules/mimo-vision.md .cursor/rules/
```
</details>

<details>
<summary><b>GitHub Copilot</b></summary>

```bash
cp .github/copilot-instructions.md .github/
```
</details>

---

## MCP 服务器（推荐）✨

通过 MCP（Model Context Protocol）让纯文本模型**自动发现**视觉能力：

### 安装后配置

```json
{
  "mcpServers": {
    "add-eyes": {
      "command": "add-eyes-mcp",
      "env": {
        "MIMO_API_KEY": "your-key"
      }
    }
  }
}
```

或直接用 Python：

```json
{
  "mcpServers": {
    "add-eyes": {
      "command": "python",
      "args": ["path/to/mcp_server.py"]
    }
  }
}
```

### MCP 工具

| 工具 | 用途 |
|------|------|
| **see_image** | 分析图片，返回文字描述。模型自动发现并调用 |
| **detect_backends** | 检测可用的视觉后端 |

### 为什么用 MCP？

| 方式 | 模型视角 | 可靠性 |
|------|---------|--------|
| CLI + 系统提示词 | "有人告诉我可以用这个" | 模型可能忽略 |
| **MCP 工具** | **"我看到我有这个工具"** | **模型按需调用** |

---

## 用法

### 基本使用

```bash
# 描述图片
python add_eyes.py screenshot.png

# 问具体问题
python add_eyes.py screenshot.png "这个页面有哪些UI问题？"

# 使用其他后端
python add_eyes.py diagram.png "解释这张架构图" --model gpt-4o

# 使用本地模型
python add_eyes.py screenshot.png "分析这个界面" --model ollama:minicpm-v
```

### 区域聚焦分析 ✨

分析图片中特定区域，提高精度：

```bash
# 聚焦左上角
python add_eyes.py screenshot.png "这是什么？" --focus 左上

# 聚焦右下角
python add_eyes.py screenshot.png "分析这个区域" --focus 右下

# 聚焦中间区域
python add_eyes.py screenshot.png "这是什么内容？" --focus 中间

# 使用坐标精确裁剪（像素）
python add_eyes.py screenshot.png "分析这个按钮" --region "100,200,300,250"

# 使用百分比坐标（0-1）
python add_eyes.py screenshot.png "分析左侧区域" --region "0,0,0.5,1"
```

**支持的聚焦关键词：**

| 中文 | 英文 | 区域 |
|------|------|------|
| 左上/左上角 | top-left | 左上 1/4 |
| 右上/右上角 | top-right | 右上 1/4 |
| 左下/左下角 | bottom-left | 左下 1/4 |
| 右下/右下角 | bottom-right | 右下 1/4 |
| 顶部 | top | 上 1/3 |
| 底部 | bottom | 下 1/3 |
| 左侧 | left | 左半边 |
| 右侧 | right | 右半边 |
| 中间 | center | 中心 1/2 |

### 智能聚焦（自动检测）✨

无需手动指定 `--focus`，根据对话上下文自动判断是否聚焦以及聚焦哪里：

```bash
# 自动聚焦：检测到"导航栏"→聚焦顶部
python add_eyes.py screenshot.png "导航栏有问题" --context "我在设计一个网页"

# 自动聚焦：检测到"报错"→聚焦底部
python add_eyes.py screenshot.png "看下面的报错"

# 自动聚焦：检测到"输入框"→聚焦中间
python add_eyes.py screenshot.png "这个输入框是什么"

# 不聚焦：没有区域线索→全图分析
python add_eyes.py screenshot.png "分析整个页面"
```

**自动聚焦规则：**

| 关键词 | 自动聚焦到 |
|-------|-----------|
| 左上角/右上角/左下角/右下角 | 对应 1/4 区域 |
| 导航栏/nav/header/logo/菜单/标题 | 顶部 |
| footer/页脚/底部导航 | 底部 |
| 错误信息/报错/控制台/console | 底部 |
| 按钮/button/提交/submit | 底部 |
| 输入框/input/表单/form | 中间 |
| 侧边栏/sidebar | 左侧 |

### 智能提问（带上下文）

```bash
# 根据对话上下文自动优化提问
python add_eyes.py screenshot.png "帮我看看" --context "我在调试登录功能，出现了 TypeError"
# → 自动问："请分析这张图片中的错误信息、异常堆栈或问题描述..."
```

### 自动路由

```bash
# 检测消息是否需要视觉处理
python add_eyes.py --auto-route "帮我看看这个截图 @.reasonix/attachments/screenshot.png"
# → {"needs_vision": true, "image_paths": [...], "question": "..."}
```

### 自动检测后端

```bash
# 检测所有可用的视觉后端
python add_eyes.py --detect-backends
```

### OCR 降级（无 API Key 时）

```bash
# 安装 OCR 依赖（可选，不装也能用）
# 注意：easyocr 首次运行会下载约 200MB 模型，pytesseract 需要额外安装系统级 tesseract
pip install pillow pytesseract easyocr

# 使用 OCR 模式
python add_eyes.py screenshot.png --ocr
```

---

## 支持的视觉后端

| 后端 | 类型 | 需要 Key | 推荐场景 |
|------|------|---------|----------|
| **ollama:minicpm-v** | 本地 | 🆓 无需 | ⭐ 日常使用，隐私优先 |
| **ollama:llava** | 本地 | 🆓 无需 | 备选本地模型 |
| **ollama:moondream** | 本地 | 🆓 无需 | 轻量快速 |
| **mimo-v2.5** | 云端 | `MIMO_API_KEY` | 国内用户，性价比高 |
| **gpt-4o** | 云端 | `OPENAI_API_KEY` | 最高质量需求 |
| **gpt-4-turbo** | 云端 | `OPENAI_API_KEY` | GPT-4o 备选 |
| **claude-3-5-sonnet** | 云端 | `ANTHROPIC_API_KEY` | 细节理解出色 |
| **claude-sonnet-4-6** | 云端 | `ANTHROPIC_API_KEY` | 最新 Claude |
| **gemini-1.5-pro** | 云端 | `GEMINI_API_KEY` | 长上下文 |
| **gemini-1.5-flash** | 云端 | `GEMINI_API_KEY` | 快速便宜 |

---

## 环境变量参考

| 变量 | 用途 |
|------|------|
| `MIMO_API_KEY` | MiMo API Key |
| `MIMO_MODEL` | 切换默认视觉后端（默认: `mimo-v2.5`） |
| `MIMO_BASE_URL` | 自定义 OpenAI 兼容地址 |
| `OPENAI_API_KEY` | OpenAI API Key |
| `OPENAI_BASE_URL` | 自定义 OpenAI 端点 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key |
| `ANTHROPIC_BASE_URL` | 自定义 Anthropic 端点 |
| `GEMINI_API_KEY` | Google Gemini API Key |
| `OLLAMA_HOST` | 自定义 Ollama 地址（默认: `http://localhost:11434`） |

---

## Always-on 模式

将 `ALWAYS_ON.md` 注入系统提示词，让 AI **永远不会说"我看不见图片"**：

```bash
# Reasonix
cp ALWAYS_ON.md ~/.reasonix/skills/ALWAYS_ON.md

# Claude Code
cat ALWAYS_ON.md >> ~/.claude/instructions.md

# Cursor
cp ALWAYS_ON.md .cursor/rules/
```

---

## 文件结构

```
add-eyes-skills/
├── SKILL.md                        # Reasonix Skill 定义
├── ALWAYS_ON.md                    # Always-on 模式指令
├── add_eyes.py                  # 核心脚本（零外部依赖，高级功能需可选依赖）
├── README.md                       # 本文件
├── LICENSE                         # MIT 许可证
├── .gitignore
├── platforms/
│   └── claude-code/
│       └── SKILL.md                # Claude Code Skill
├── .cursor/
│   └── rules/
│       └── mimo-vision.md          # Cursor Rule
└── .github/
    └── copilot-instructions.md     # GitHub Copilot 指令
```

---

## 常见问题

**Q: MCP 配置后模型还是说"看不见图片"？**
A: 确保 MCP 服务器路径正确，重启 AI 客户端。MCP 工具需要客户端启动时加载。

**Q: Ollama 安装后检测不到？**
A: 确保 Ollama 已启动（`ollama serve`），然后运行 `python add_eyes.py --detect-backends`。

**Q: 图片太大？**
A: 图片上限 10MB，支持 PNG/JPG/JPEG/GIF/WebP/BMP。

**Q: 可以换视觉后端吗？**
A: 可以，`--model ollama:minicpm-v`（本地）或 `--model gpt-4o`（云端）。

**Q: 支持视频吗？**
A: 当前仅支持图片，视频支持计划中。

**Q: OCR 降级需要什么？**
A: `pip install pillow pytesseract easyocr`（可选，不装也不影响核心功能）。

---

## License

[MIT](LICENSE)
