#!/usr/bin/env python3
"""
Add Eyes MCP Server — 给纯文本模型提供视觉能力的标准 MCP 工具。

使用方式：
    python mcp_server.py                    # stdio 模式（默认）
    python mcp_server.py --transport http   # HTTP 模式
    python mcp_server.py --transport sse    # SSE 模式

MCP 客户端配置示例：
{
  "mcpServers": {
    "add-eyes": {
      "command": "python",
      "args": ["path/to/mcp_server.py"],
      "env": {
        "MIMO_API_KEY": "your-key"
      }
    }
  }
}
"""

import sys
import os
import json
import base64
import urllib.request
import urllib.error

# ── UTF-8 encoding fix for Windows ──────────────────────────────────
if sys.platform == "win32":
    import io
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ── Import core logic from add_eyes.py ──────────────────────────────
# Try to import from the same directory first
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from add_eyes import (
        ask_with_image,
        auto_detect_backends,
        encode_image,
        ocr_fallback,
    )
except ImportError:
    print("Error: add_eyes.py not found in the same directory as mcp_server.py", file=sys.stderr)
    sys.exit(1)


# ── MCP Protocol Implementation (minimal, no external deps) ─────────

class MCPServer:
    """Minimal MCP stdio server — no mcp package required."""

    def __init__(self):
        self.tools = []
        self._handlers = {}

    def tool(self, name, description, input_schema):
        """Decorator to register a tool."""
        def decorator(func):
            self.tools.append({
                "name": name,
                "description": description,
                "inputSchema": input_schema,
            })
            self._handlers[name] = func
            return func
        return decorator

    def run_stdio(self):
        """Run the MCP server over stdio."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self._handle(request)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                continue
            except Exception as e:
                sys.stderr.write(f"MCP error: {e}\n")
                sys.stderr.flush()

    def _handle(self, request):
        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "add-eyes",
                        "version": "2.1.0",
                    },
                },
            }

        elif method == "notifications/initialized":
            return None  # No response for notifications

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.tools},
            }

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            handler = self._handlers.get(tool_name)
            if not handler:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                        "isError": True,
                    },
                }
            try:
                result = handler(**arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result}],
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {e}"}],
                        "isError": True,
                    },
                }

        elif method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }


# ── Create MCP server instance ──────────────────────────────────────
server = MCPServer()


# ── Tool: see_image ─────────────────────────────────────────────────
@server.tool(
    name="see_image",
    description=(
        "Analyze an image and return a text description. "
        "Use this tool whenever the user shares an image, screenshot, photo, diagram, "
        "UI mockup, chart, error screenshot, or any visual content that needs to be understood. "
        "Supports PNG, JPG, JPEG, GIF, WebP, BMP formats. "
        "Returns a detailed text description that you can use to answer the user's question. "
        "Never say 'I cannot view images' — always call this tool instead."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Absolute path to the image file on disk",
            },
            "question": {
                "type": "string",
                "description": "What to analyze in the image. Be specific based on context: "
                               "'describe the UI layout', 'what error is shown', "
                               "'read all text in the image', 'analyze the chart data'",
                "default": "请详细描述这张图片的内容。",
            },
            "model": {
                "type": "string",
                "description": "Vision backend to use (default: auto-detect best available). "
                               "Options: ollama:minicpm-v, mimo-v2.5, gpt-4o, claude-3-5-sonnet-20241022",
                "default": "",
            },
            "focus": {
                "type": "string",
                "description": "Focus on a specific region: 左上/右上/左下/右下/顶部/底部/中间/左侧/右侧 "
                               "(or English: top-left/bottom-right/center etc.)",
                "default": "",
            },
            "context": {
                "type": "string",
                "description": "Conversation context for smart question enhancement. "
                               "E.g. 'debugging a login page with TypeError' or 'analyzing a UI design'. "
                               "This helps generate a more targeted analysis.",
                "default": "",
            },
        },
        "required": ["image_path"],
    },
)
def see_image(image_path: str, question: str = "", model: str = "", focus: str = "", context: str = "") -> str:
    """Analyze an image and return text description."""
    if not question:
        question = "请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"
    if not model:
        model = os.environ.get("MIMO_MODEL", "ollama:minicpm-v")
    if not focus:
        focus = None

    # Validate file exists
    if not os.path.isfile(image_path):
        return f"Error: Image file not found: {image_path}"

    try:
        result = ask_with_image(
            image_path=image_path,
            question=question,
            model_name=model,
            focus=focus,
            context=context if context else None,
        )
        return result
    except EnvironmentError as e:
        return f"Error: {e}\nTip: Set MIMO_API_KEY or configure Ollama with minicpm-v model."
    except Exception as e:
        return f"Error analyzing image: {e}"


# ── Tool: detect_backends ───────────────────────────────────────────
@server.tool(
    name="detect_backends",
    description=(
        "Detect available vision backends (local Ollama models, cloud API keys). "
        "Use this to check which vision models are available before calling see_image. "
        "Returns JSON with available backends and recommended choice."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "format": {
                "type": "string",
                "enum": ["json", "text"],
                "description": "Output format: 'json' for machine-readable, 'text' for human-readable",
                "default": "json",
            },
        },
    },
)
def detect_backends_tool(format: str = "json") -> str:
    """Detect available vision backends."""
    try:
        result = auto_detect_backends()
        available = result.get("available", [])
        recommended = result.get("recommended", "none")

        if format == "json":
            return json.dumps({
                "available": available,
                "recommended": recommended,
                "count": len(available),
            }, ensure_ascii=False, indent=2)

        # Text format
        if not available:
            return "No vision backends available. Install Ollama and pull minicpm-v, or set an API key."
        lines = [f"Available backends ({len(available)}):"]
        for b in available:
            marker = " * recommended" if b == recommended else ""
            lines.append(f"  - {b}{marker}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error detecting backends: {e}"


# ── Helper: extract images from documents ───────────────────────────
def _extract_images_from_docx(docx_path):
    """Extract images from a .docx file."""
    import zipfile
    import tempfile
    images = []
    with zipfile.ZipFile(docx_path, 'r') as z:
        for f in z.namelist():
            if f.startswith('word/media/') and any(f.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                ext = os.path.splitext(f)[1]
                with tempfile.NamedTemporaryFile(suffix=ext, prefix="add_eyes_doc_", delete=False) as tmp:
                    tmp.write(z.read(f))
                    images.append(tmp.name)
    return images


def _extract_images_from_pdf(pdf_path):
    """Extract images from a PDF file (requires PyMuPDF)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None  # None = PyMuPDF not installed (distinct from [] = no images found)
    
    doc = fitz.open(pdf_path)
    images = []
    import tempfile
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            ext = base_image["ext"]
            with tempfile.NamedTemporaryFile(suffix=f".{ext}", prefix="add_eyes_pdf_", delete=False) as tmp:
                tmp.write(base_image["image"])
                images.append(tmp.name)
    
    return images  # Empty list = PDF has no images


# ── Tool: analyze_document ──────────────────────────────────────────
@server.tool(
    name="analyze_document",
    description=(
        "Analyze a document file (Word .docx or PDF). "
        "ALWAYS call this tool when the user shares a .docx or .pdf file, "
        "regardless of whether they mention images, charts, or screenshots. "
        "When calling, fill the 'context' field with: "
        "1. Any information the user provided about the document "
        "2. Inferences from the filename (e.g. 'Q2 产品评审报告' → 'product review report') "
        "3. If no context is available, leave it empty (the tool will use a default question). "
        "This tool extracts and analyzes any images, charts, diagrams, or visual content "
        "found in the document. If no images are found, it returns that information too. "
        "Never say 'I cannot read document files' — always call this tool instead."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the document file (.docx or .pdf)",
            },
            "question": {
                "type": "string",
                "description": "What to analyze in the document images",
                "default": "请详细描述这张图片的内容，包括布局、颜色、文字、元素等。",
            },
            "model": {
                "type": "string",
                "description": "Vision backend to use (default: auto-detect)",
                "default": "",
            },
            "context": {
                "type": "string",
                "description": "Conversation context for smart question enhancement. "
                               "E.g. 'analyzing a data science report with charts' or 'reviewing a technical architecture document'.",
                "default": "",
            },
            "max_images": {
                "type": "integer",
                "description": "Maximum number of images to analyze (default: 10)",
                "default": 10,
            },
        },
        "required": ["file_path"],
    },
)
def analyze_document(file_path: str, question: str = "", model: str = "", context: str = "", max_images: int = 10) -> str:
    """Extract and analyze images from a document."""
    if not question:
        question = "请详细描述这张图片的内容，包括布局、颜色、文字、元素等。"
    if not model:
        model = os.environ.get("MIMO_MODEL", "ollama:minicpm-v")

    if not os.path.isfile(file_path):
        return f"Error: File not found: {file_path}"

    ext = os.path.splitext(file_path)[1].lower()

    # Extract images
    if ext == '.docx':
        images = _extract_images_from_docx(file_path)
    elif ext == '.pdf':
        images = _extract_images_from_pdf(file_path)
        if images is None:
            return "Error: PyMuPDF not installed. Install it: pip install pymupdf"
        if not images:
            return f"PDF {os.path.basename(file_path)} has no embedded images."
    else:
        return f"Error: Unsupported format '{ext}'. Supported: .docx, .pdf"

    if not images:
        return f"No images found in {os.path.basename(file_path)}"

    # Limit images
    images = images[:max_images]

    # Analyze each image
    results = []
    for i, img_path in enumerate(images):
        try:
            result = ask_with_image(
                image_path=img_path,
                question=question,
                model_name=model,
                context=context if context else None,
            )
            results.append(f"## 图片 {i+1}/{len(images)}\n{result}")
        except Exception as e:
            results.append(f"## 图片 {i+1}/{len(images)}\nError: {e}")
        finally:
            # Clean up temp file
            try:
                os.unlink(img_path)
            except OSError:
                pass

    return f"文档 {os.path.basename(file_path)} 共提取 {len(images)} 张图片:\n\n" + "\n\n".join(results)


# ── Entry point ─────────────────────────────────────────────────────
def main():
    """Run the MCP server."""
    import argparse
    parser = argparse.ArgumentParser(description="Add Eyes MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http", "sse"], default="stdio",
                        help="Transport mode (default: stdio; http/sse not yet implemented)")
    parser.add_argument("--port", type=int, default=8765,
                        help="Port for HTTP/SSE transport (default: 8765)")
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run_stdio()
    else:
        print(f"HTTP/SSE transport not yet implemented. Use stdio.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
