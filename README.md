# MiMo Vision Skill

> **纯文本模型的「视觉桥接」** — 给 DeepSeek V4 Flash/Pro 等不支持多模态的模型装上「眼睛」  
> Vision bridge for text-only LLMs — let DeepSeek V4, etc. "see" images via external vision APIs

[![Reasonix Skill](https://img.shields.io/badge/Reasonix-Skill-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.8%2B-green)](mimo_vision.py)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## 为什么需要这个？

你的 AI 模型如果是纯文本模型（例如 **DeepSeek V4 Flash**、**V4 Pro**），它**看不懂图片**。
用户贴了截图、报错、设计稿……模型都只能干瞪眼。

**MiMo Vision** 的解决思路：

```
用户贴图 ──→ 纯文本模型看不见 ──→ Skill 编码图片
    ──→ 调用外部视觉 API ──→ 获得文字描述
    ──→ 纯文本模型拿到描述，「看懂了」
```

你只是**借用了外部视觉模型的眼睛**，然后用自己强大的语言能力来理解、分析、处理图片内容。

## 快速开始

### 1. 安装 & 配置

```bash
git clone https://github.com/<your-org>/mimo-vision-skill.git
cd mimo-vision-skill
```

### 2. 配置视觉后端 Key（至少一个）

```bash
# ⭐ 推荐：MiMo（性价比高，国内直连）
# PowerShell:
$env:MIMO_API_KEY = 'your-mimo-key'
# bash:
export MIMO_API_KEY='your-mimo-key'

# 或 OpenAI / Claude / Gemini（任选其一）
$env:OPENAI_API_KEY = 'your-openai-key'
```

### 3. 测试脚本

```bash
python mimo_vision.py path/to/test.png "测试：这是什么？"
```

### 4. 安装到你的 AI 编程助手

<details>
<summary><b>Claude Code</b> (Anthropic)</summary>

将 `platforms/claude-code/SKILL.md` 复制到项目的 `.claude/skills/vision/` 目录：

```bash
mkdir -p .claude/skills/vision
cp platforms/claude-code/SKILL.md .claude/skills/vision/
```

或安装到用户级（所有项目生效）：

```bash
mkdir -p ~/.claude/skills/vision
cp platforms/claude-code/SKILL.md ~/.claude/skills/vision/
```
</details>

<details>
<summary><b>Cursor</b> (Anysphere)</summary>

将 `.cursor/rules/mimo-vision.md` 复制到项目的 `.cursor/rules/` 目录：

```bash
mkdir -p .cursor/rules
cp .cursor/rules/mimo-vision.md .cursor/rules/
```

</details>

<details>
<summary><b>GitHub Copilot</b> (Microsoft)</summary>

将 `.github/copilot-instructions.md` 复制到项目的 `.github/` 目录：

```bash
mkdir -p .github
cp .github/copilot-instructions.md .github/
```
</details>

<details>
<summary><b>Reasonix</b></summary>

```bash
install-capability source="./mimo-vision-skill"
```
</details>

<details open>
<summary><b>通用 CLI / 其他 Agent 平台</b></summary>

脚本本身纯 Python 标准库，可直接在任意 Agent 中调用：

```bash
python "<repo路径>/mimo_vision.py" "<图片路径>" "<问题>" --model <后端>
```

只需要在你的 Agent 系统提示里加入类似指令即可，参考各平台的 Skill 定义文件。
</details>

## 用法

### 基本使用

```bash
# 描述图片
python mimo_vision.py screenshot.png

# 问具体问题
python mimo_vision.py screenshot.png "这个页面有哪些UI问题？"

# 使用其他模型
python mimo_vision.py diagram.png "解释这张架构图" --model gpt-4o

# 列出所有支持的模型
python mimo_vision.py --list-models
```

### 通过 Reasonix AI Agent 使用

安装成功后，当你在 Reasonix 中粘贴图片时，Agent 会自动识别并使用此 Skill 分析图片。你也可以直接说：

- "帮我看这张截图"
- "分析这个页面的布局"
- "用 GPT-4o 看这张架构图"
- "这个 UI 有什么问题？"

## 环境变量参考

| 变量 | 用途 | 视觉后端 |
|------|------|----------|
| `MIMO_API_KEY` | ⭐ 小米 MiMo (推荐) | `mimo-v2.5` |
| `MIMO_MODEL` | 切换默认视觉后端 | 所有 |
| `MIMO_BASE_URL` | 自定义 OpenAI 兼容地址 | 自定义后端 |
| `OPENAI_API_KEY` | OpenAI | `gpt-4o`, `gpt-4-turbo` |
| `OPENAI_BASE_URL` | 自定义 OpenAI 端点 | 代理/中转 |
| `ANTHROPIC_API_KEY` | Anthropic Claude | Claude 系列 |
| `ANTHROPIC_BASE_URL` | 自定义 Anthropic 端点 | 代理/中转 |
| `GEMINI_API_KEY` | Google Gemini | Gemini 系列 |
| `GEMINI_BASE_URL` | 自定义 Gemini 端点 | 代理/中转 |

## 添加自定义视觉后端

如果你有其他 OpenAI 兼容的视觉 API（如通过中转站代理），只需：

1. 设置环境变量指向你的端点：
   ```bash
   export MIMO_BASE_URL="https://your-proxy.com/v1/chat/completions"
   export MIMO_API_KEY="your-proxy-key"
   ```
2. 运行时指定后端模型名：
   ```bash
   export MIMO_MODEL="your-vision-model-name"
   python mimo_vision.py image.png "描述这张图片"
   ```

## OCR 降级（无 API Key 时使用）

当没有任何视觉 API Key 时，可以启用 OCR 模式提取图片中的文字：

```bash
# 安装 OCR 依赖（可选，不装也能用，只是少 OCR 功能）
pip install pillow pytesseract easyocr

# 使用 OCR 模式
python mimo_vision.py screenshot.png --ocr
```

**OCR 降级顺序：**

| 优先级 | 工具 | 安装 | 说明 |
|-------|------|------|------|
| 1 | easyocr | `pip install easyocr` | 纯 Python，离线，首次下载模型 (~200MB) |
| 2 | pytesseract | `pip install pytesseract` + 系统 tesseract | 需要额外装系统包 |
| 3 | Pillow | `pip install pillow` | 只能读取图片元信息（格式/尺寸/EXIF） |

**注意：** OCR 只能提取文字，不能"理解"图片内容。建议优先使用视觉 API（配 Key），OCR 作为最后的兜底方案。

## 文件结构

```
mimo-vision-skill/
├── SKILL.md                        # Reasonix Skill 定义
├── mimo_vision.py                  # 核心脚本（多模型视觉分析）
├── README.md                       # 本文件
├── LICENSE                         # MIT 许可证
├── platforms/
│   └── claude-code/
│       └── SKILL.md                # Claude Code Skill 定义
├── .cursor/
│   └── rules/
│       └── mimo-vision.md          # Cursor 规则文件
└── .github/
    └── copilot-instructions.md     # GitHub Copilot 指令
```

## 常见问题

**Q: 提示 API Key 未设置？**

A: 确保设置了对应的环境变量。使用 `python mimo_vision.py --list-models` 查看每个视觉后端需要的 Key 名称。

**Q: 调用返回 401 / 认证失败？**

A: API Key 可能无效或已过期。检查 Key 是否正确，以及账户余额是否充足。

**Q: 图片太大？**

A: 图片上限为 10MB。可以压缩后再尝试。

**Q: 可以换别的视觉后端吗？**

A: 可以，通过 `--model` 参数指定。例如 `--model gpt-4o` 用 GPT-4o，`--model claude-3-5-sonnet-20241022` 用 Claude。

## License

[MIT](LICENSE)
