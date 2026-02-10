# VibeCode 🚀

**Digital Twin Snapshots for AI-Native Codebase Management**

> Transform your entire codebase into a portable, AI-consumable PDF with perfect restoration capability. Built for the Gemini 3 Hackathon.

[![Gemini 3](https://img.shields.io/badge/Powered%20by-Gemini%203-blue)](https://ai.google.dev/)
[![Python](https://img.shields.io/badge/Python-3.9+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

## 🎯 What is VibeCode?

VibeCode creates **Digital Twin snapshots** of your codebase as immutable PDF artifacts that can be:

- 📧 **Emailed** (2MB PDF vs 50MB git repo)
- 🤖 **Fed to AI** (Gemini loads 180K tokens without chunking)
- ✅ **Perfectly restored** (SHA-256 verified, bit-perfect reconstruction)
- 🔒 **Archived forever** (immutable, compliance-ready)
- ⏰ **Time-traveled** (compare version snapshots with AI-explained diffs)

**The Innovation:** Unlike traditional RAG systems that chunk code, VibeCode treats your codebase as serializable data that fits entirely into Gemini's 1M+ context window.

---

## ✨ Key Features

### 🎨 Dual Rendering Modes
- **LLM Mode**: Machine-readable PDFs optimized for AI consumption
  - Embedded JSON manifest (base64 + zlib compressed)
  - SHA-256 integrity checksums
  - ~180K tokens for typical projects
  
- **Human Mode**: Beautiful, syntax-highlighted PDFs
  - Color schemes: Monokai, Dracula, GitHub, VS Code
  - Perfect for code reviews and documentation
  - Parallel processing for speed

### 💬 VibeChat - AI Codebase Assistant
- **Full-project context**: Entire codebase loaded into Gemini
- **Smart RAG**: Semantic file search with `gemini-embedding-001`
- **Stack trace detection**: Automatic crash debugging
- **Citation system**: `[[REF: file.py]]` links to source files
- **Streaming responses**: Real-time answers

### 🔧 Advanced Capabilities

**VibeSelect** - AI File Selection
```bash
# Gemini analyzes 300 files → returns 10 relevant ones
Intent: "Fix the login bug"
Output: [auth.py, session.py, middleware.py, config.py]
```

**VibeContext** - Auto-Generated Documentation
```markdown
# Snapshot Context
This snapshot contains the GUI layer. 
⚠️ Missing: Backend API logic in `api/` directory.
```

**Time Travel** - Version Comparison
```bash
# Load two snapshots, get AI-explained diffs
"What broke between v1.0 and v2.0?"
→ Unified diffs + architectural explanations
```

**MCP Integration** - External Tools
- Google Drive (search, read documents)
- GitHub (clone repos, read code)
- Extensible via Model Context Protocol

**Implementation Drafter** - Code Patches
```xml
<patch file="auth.py">
# Gemini suggests changes
# Click "Apply" → writes to disk with backup
</patch>
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/vibecode.git
cd vibecode

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Verify installation
python verify_install.py
```

### Configure API Key

```bash
# Launch GUI and click the ⚙️ settings button
# OR set environment variable
export GOOGLE_API_KEY="your-gemini-api-key"
```

### Basic Usage

**1. Generate a Snapshot**
```bash
# Launch GUI
python run_local.py
# OR use CLI
vibecode llm              # Create LLM-optimized PDF
vibecode human            # Create human-readable PDF
```

**2. Chat with Your Code**
```bash
# In GUI: Click "Chat" button
# Loads PDF → Ask questions → Get answers with citations
```

**3. Restore from PDF**
```bash
vibecode unpack project_llm.pdf --output ./restored/
# Perfect restoration with SHA-256 verification
```

---

## 🧠 How Gemini 3 Powers VibeCode

### Large Context Window Exploitation
VibeCode loads **entire project snapshots (~180K tokens)** into Gemini Flash 2.0's 1M+ context window. Unlike traditional RAG that chunks and retrieves, the complete codebase lives in context simultaneously, enabling whole-program reasoning.

### Multi-Agent Architecture

**1. Snapshot Generation Agent**
- Analyzes file lists with Gemini
- Generates AI-optimized metadata headers
- Creates scope documentation

**2. File Selection Agent** (`VibeSelect`)
- JSON-mode structured output (temp 0.1)
- Dependency graph analysis
- Filters 300+ files → ~10 relevant ones

**3. MCP Integration Agent**
- Function calling for external tools
- Retrieves Google Drive docs, GitHub repos
- Merges external context into snapshots

**4. RAG Agent** (`VibeRAG`)
- Uses `gemini-embedding-001` for semantic indexing
- Similarity search across codebase
- "Find files like this" queries

### Advanced Features
- **Stack trace auto-detection** with priority context injection
- **Time Travel** snapshot comparison with unified diffs
- **Extended thinking** via `<think>` block parsing
- **Code generation** with `<patch>` XML tags
- **Persistent memory** with ChromaDB across sessions

---

## 📁 Project Structure

```
vibecode/
├── src/vibecode/
│   ├── chat/               # VibeChat engine
│   │   ├── engine.py       # ChatEngine core
│   │   ├── gui.py          # PyQt6 interface
│   │   ├── mcp_host.py     # MCP integration
│   │   └── memory.py       # Conversation history
│   ├── agents/
│   │   └── mcp_agent.py    # External tool agent
│   ├── renderers/
│   │   ├── llm.py          # LLM PDF renderer
│   │   └── human.py        # Human PDF renderer
│   ├── ai.py               # VibeSelect/VibeContext
│   ├── rag.py              # VibeRAG embedding search
│   ├── cli.py              # Command-line interface
│   └── gui/                # Main GUI application
├── pyproject.toml          # Dependencies
└── README.md               # This file
```

---

## 🎬 Demo Video

[Watch the 3-minute demo →](YOUR_VIDEO_URL_HERE)

---

## 🏆 Use Cases

### For Developers
- 📧 Email your codebase to consultants without git access
- 🔍 Code review with beautiful syntax-highlighted PDFs
- 🤖 Chat with your code using natural language
- 🐛 Debug crashes with automatic stack trace detection

### For Teams
- 📚 Archive project versions forever (PDF/A compliant)
- 🌍 Share with teammates in restricted networks
- ⏰ Compare versions with AI-explained diffs
- 📊 Generate documentation automatically

### For AI Systems
- 🚀 Feed entire projects to LLMs without chunking
- 🔗 Integrate external data via MCP servers
- 💾 Portable knowledge artifacts for AI agents
- 🎯 Context-grounded responses with citations

---

## 🛠️ Tech Stack

- **AI Models**: Gemini Flash 2.0, Gemini Embedding 001
- **GUI**: PyQt6
- **PDF Generation**: fpdf2 (LLM), WeasyPrint (Human)
- **Vector Store**: ChromaDB
- **MCP**: Model Context Protocol SDK
- **Language**: Python 3.9+

## 🙏 Acknowledgments

Built for the **Gemini 3 Hackathon** by Ajpop3y

Powered by Google's Gemini 3 API

---

## 🔗 Links

- [Gemini 3 Hackathon](https://gemini3.devpost.com/)
- [Google AI Studio](https://aistudio.google.com/)
- [Model Context Protocol](https://modelcontextprotocol.io/)

---

**⭐ Star this repo if you find it useful!**
