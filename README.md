# VibeCode

<div align="center">

### Digital Twin Architecture for AI-Native Codebase Management

**Cryptographically-verified snapshots · Whole-program AI reasoning · Perfect restoration**

[![Powered by Gemini 3](https://img.shields.io/badge/Powered%20by-Gemini%203-4285F4?style=for-the-badge&logo=google)](https://ai.google.dev/)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-00A67E?style=for-the-badge)](https://modelcontextprotocol.io/)

<img src="https://img.shields.io/badge/Lines_of_Code-11,634-blue?style=flat-square" />
<img src="https://img.shields.io/badge/Built_During-Power_Outage-orange?style=flat-square" />
<img src="https://img.shields.io/badge/Gemini_3-Hackathon-green?style=flat-square" />

---

**[📖 Documentation](#-documentation) · [🚀 Quick Start](#-quick-start) · [✨ Features](#-the-core-innovation-digital-twin-snapshots) · [🎯 Use Cases](#-use-cases) · [🏗️ Architecture](#️-technical-architecture)**

---

</div>

## 🌟 The Revolutionary Paradigm

> **Instead of chunking code for RAG or streaming files to AI, VibeCode treats entire codebases as serializable, portable, cryptographically-verified data artifacts that can be transmitted, archived, and perfectly reconstructed — while fitting entirely into Gemini's 1M+ token context window.**

Every other AI coding tool works the same way:
- **Cursor/Copilot:** Stream open files to the AI as you edit
- **Traditional RAG:** Chunk your code, embed it, retrieve relevant pieces  
- **GitHub Copilot Workspace:** Load context from git history

**VibeCode does something fundamentally different.**

---

## 🎯 What is VibeCode?

VibeCode creates **Digital Twin snapshots** — self-contained PDF artifacts that:

```
📦 Serialize the complete codebase    🔐 Embed cryptographic manifests
✅ Enable perfect restoration          🤖 Remain AI-consumable
📧 Stay portable (2MB vs 50MB repos)   🔒 Become immutable archives
```

### The 30-Second Demo

```bash
# 1. Generate a Digital Twin snapshot
vibecode llm
# → Creates project_llm.pdf (180K tokens, SHA-256 verified)

# 2. Chat with your entire codebase
vibecode chat
# → Gemini loads ALL 180K tokens simultaneously
# → Ask: "How does authentication work?"
# → Get: Architectural explanation with [[REF: auth.py]] citations

# 3. Perfect restoration
vibecode unpack project_llm.pdf --output ./restored/
# → Bit-for-bit identical reconstruction
# → SHA-256 checksum verified
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/ajpop3y/vibecode-project.git
cd vibecode-project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install
pip install -e .

# Verify
python verify_install.py
```

### Configure API Key

```bash
# Launch GUI and click ⚙️ settings
python run_local.py

# OR set environment variable
export GOOGLE_API_KEY="your-gemini-api-key"
```

### First Snapshot

```bash
# GUI Mode (Recommended)
python run_local.py
# Click "Generate LLM PDF" → Select files → Done!

# CLI Mode
vibecode llm              # Machine-readable
vibecode human            # Human-readable (syntax-highlighted)
```

---

## ✨ The Core Innovation: Digital Twin Snapshots

### What Makes This Revolutionary

<table>
<tr>
<td width="50%">

#### 🎨 **Two Rendering Modes**

**LLM Mode** (Machine-Readable)
- Optimized for AI consumption
- Embedded JSON manifest (base64+zlib)
- SHA-256 integrity checksums
- ~180K tokens typical
- **Perfect fidelity restoration**

**Human Mode** (Human-Readable)  
- Syntax-highlighted (Monokai, Dracula, VS Code)
- Beautiful typography (WeasyPrint)
- Parallel processing (fast!)
- Perfect for code reviews

</td>
<td width="50%">

#### 🔐 **The Digital Twin Manifest**

```python
Embedded in every LLM PDF:
{
  "format": "vibecode-digital-twin-v1",
  "checksum": "sha256:abc123...",
  "files": {
    "src/main.py": "def main()...",
    "src/utils.py": "import os..."
  },
  "metadata": {
    "generated": "2026-02-11T...",
    "python_version": "3.12.10",
    "platform": "Windows 10"
  }
}
```

**Compressed:** base64 + zlib  
**Verified:** SHA-256 checksums  
**Portable:** Self-contained in PDF

</td>
</tr>
</table>

### The Restoration Process

```
PDF → pypdf reader → Extract text → Locate manifest marker
  ↓
Verify SHA-256 checksum
  ↓
Decompress base64 + zlib
  ↓
Parse JSON
  ↓
Restore files with EXACT paths/indentation/content
  ↓
✅ Bit-for-bit identical reconstruction
```

### Why This Matters

| Traditional Approach | VibeCode Digital Twins |
|---------------------|------------------------|
| 📂 Git clone (50-500MB) | 📧 Email PDF (2-10MB) |
| 🌐 Requires network access | ✈️ Works offline/air-gapped |
| 🔄 Mutable (can be changed) | 🔒 Immutable (tamper-evident) |
| 📊 Chunked for RAG | 🧠 Whole-program reasoning |
| ❓ No verification | ✅ Cryptographic checksums |
| 🗂️ Files in directories | 📦 Serialized data artifact |

---

## 🧠 Gemini 3 Integration: Multi-Agent Orchestration

### Maximizing the 1M+ Context Window

VibeCode doesn't chunk your code. It loads **the entire project** (~180K tokens) directly into Gemini Flash 2.0's context:

```python
Context Allocation Strategy:
├── 60% Reserved for code files (selected dynamically)
├── 40% Reserved for conversation history + responses
├── Full project tree ALWAYS in context (high value, low cost)
├── Stack trace auto-detection → prioritize crashed files
└── Time Travel mode → inject unified diffs for version comparison
```

### The Multi-Agent Architecture

<div align="center">

```mermaid
graph TB
    A[User Query] --> B{Agent Router}
    B --> C[VibeSelect Agent<br/>File Selection]
    B --> D[VibeContext Agent<br/>Documentation]
    B --> E[MCP Agent<br/>External Tools]
    B --> F[VibeRAG Agent<br/>Semantic Search]
    
    C --> G[Gemini Flash 2.0<br/>JSON Mode, Temp 0.1]
    D --> H[Gemini Flash 2.0<br/>Creative Mode, Temp 0.3]
    E --> I[MCP Servers<br/>GitHub, Drive, Slack]
    F --> J[gemini-embedding-001<br/>ChromaDB]
    
    G --> K[Selected Files]
    H --> L[SNAPSHOT_CONTEXT.md]
    I --> M[External Data]
    J --> N[Similar Files]
    
    K --> O[ChatEngine]
    L --> O
    M --> O
    N --> O
    
    O --> P[Response with Citations]
    
    style A fill:#4285F4,color:#fff
    style O fill:#34A853,color:#fff
    style P fill:#FBBC04,color:#000
```

</div>

#### 🎯 **Agent 1: VibeSelect** (File Selection)

```python
Input:  300 files + user intent ("Fix the login bug")
Process: Gemini analyzes dependency graphs → JSON structured output
Output: [auth.py, session.py, middleware.py, config.py] (10 files)
Model:  gemini-flash-latest, Temperature: 0.1 (deterministic)
```

**Example:**
```
User: "I need to fix the authentication bug"

VibeSelect Agent:
1. Analyzes all 300 files in project
2. Identifies dependencies: auth.py imports session.py, config.py
3. Returns: ["src/auth.py", "src/session.py", "src/middleware/auth_check.py", "config/auth.yaml"]
4. Reduces 300 files → 4 relevant files (98.7% reduction)
```

#### 📝 **Agent 2: VibeContext** (Documentation Generation)

```python
Input:  Selected files + excluded files + user intent
Process: Gemini writes architectural README
Output: SNAPSHOT_CONTEXT.md explaining scope & limitations
Model:  gemini-flash-latest, Temperature: 0.3 (creative but factual)
```

**Generated Output Example:**
```markdown
# Snapshot Context

This snapshot contains the **GUI layer** of VibeCode (PyQt6 components, 
dialogs, worker threads).

⚠️ **Missing Components:**
- Backend PDF generation logic (`renderers/`)
- CLI commands (`cli.py`)
- Configuration parsing (`config.py`)

**Key Architecture:**
The GUI uses a worker thread pattern to prevent UI freezing during 
long operations. Main components:
- `MainWindow`: Project management and file selection
- `ChatWindow`: AI conversation interface with streaming
- `Workers`: Async PDF generation, MCP calls, AI selection
```

#### 🔌 **Agent 3: MCP Integration** (External Tool Orchestration)

```python
Tools:       Google Drive, GitHub, Slack (extensible)
Process:     Function calling via Model Context Protocol
Capability:  Multi-step workflows across external services
Auto-Ingest: Results automatically indexed in RAG
```

**Workflow Example:**
```
User: "Get the design doc from Drive and analyze it against our implementation"

MCP Agent Workflow:
1. drive__search("design doc") 
   → Result: ["design_v3.pdf", "design_v2_old.pdf"]
   
2. drive__read_file("design_v3.pdf")
   → Content: "Authentication must use JWT with 15min expiry..."
   
3. RAG Auto-Ingest
   → Indexes doc content in ChromaDB
   → Makes it searchable for future queries
   
4. Main ChatEngine
   → Analyzes code + design doc
   → Response: "Gap found: Our JWT expiry is 60min, design says 15min.
                See [[REF: config/auth.yaml]] line 42"
```

#### 🔍 **Agent 4: VibeRAG** (Semantic Code Search)

```python
Embedding:   gemini-embedding-001
Vector DB:   ChromaDB (persistent across sessions)
Features:    Conceptual similarity, auto-sync on file changes
```

**Conceptual Search Example:**
```
Query: "Show me other files that do authentication"

VibeRAG Process:
1. Generate query embedding: [0.234, -0.891, 0.456, ...]
2. Compare against all file embeddings (cosine similarity)
3. Results:
   - oauth.py (0.89 similarity)
   - jwt_handler.py (0.87 similarity)  
   - permissions.py (0.82 similarity)
   - user_model.py (0.78 similarity)

Note: None of these files literally mention "authentication" in their name!
```

---

## 💬 VibeChat: Context-Grounded Conversations

### The ChatEngine Architecture

<table>
<tr>
<td width="60%">

#### Core Capabilities

✅ **Full-Project Context**  
Entire codebase loaded simultaneously (no chunking)

✅ **Citation System**  
Every claim references source: `[[REF: file.py]]`

✅ **Stack Trace Auto-Detection**  
Paste error → relevant files loaded with priority

✅ **Streaming Responses**  
Token-by-token display (no waiting)

✅ **Persistent Memory**  
ChromaDB stores conversation history across sessions

✅ **Multi-Provider Support**  
Gemini, OpenAI, Anthropic, Ollama, Custom APIs

</td>
<td width="40%">

#### Smart Context Selection

```python
Priority Hierarchy:
1. Project tree (always)
2. Stack trace files
3. Files mentioned in query
4. Semantically similar files
5. Recent conversation context
6. Time Travel diffs

Token Allocation:
├ 60% Code files
├ 30% Conversation
└ 10% System prompts
```

</td>
</tr>
</table>

### Advanced Features

#### 🤔 **Extended Thinking Mode**

Gemini can emit `<think>...</think>` blocks for transparent reasoning:

```xml
<think>
The user is experiencing an AttributeError on line 1042.
This suggests self.provider is None, which happens when 
initialization fails in _init_provider().

Let me check:
1. Is GOOGLE_API_KEY set? (need to verify)
2. Did the GoogleProvider constructor succeed?
3. Was there an exception caught silently?

Most likely: API key not configured.
</think>

The issue is in your ChatEngine initialization. The `provider` 
is None because the API key isn't configured. You can fix this by...
```

**Collapsible in GUI** - Click to expand/hide reasoning process

#### 🔧 **Implementation Drafter**

Gemini proposes code changes as patches:

```xml
<patch file="auth.py">
def login(username, password):
    # ADDED: Input validation
    if not username or not password:
        raise ValueError("Credentials required")
    
    # ADDED: Rate limiting check
    if is_rate_limited(username):
        raise RateLimitError("Too many attempts")
    
    session = create_session(username)
    return session
</patch>
```

**GUI Features:**
- Syntax-highlighted diff view
- "Apply" button → writes to disk with backup
- "Preview" shows exact changes
- One-click rollback via `.bak` files

#### 📊 **Stack Trace Auto-Recovery**

```python
User pastes:
Traceback (most recent call last):
  File "src/chat/engine.py", line 1042, in send_message
    response = self.provider.send_message()
AttributeError: 'NoneType' object has no attribute 'send_message'

ChatEngine Response:
!!! CRASH DETECTED IN chat/engine.py AT LINE 1042 !!!

Auto-loaded files:
✓ chat/engine.py (crash site)
✓ chat/models.py (provider definition)
✓ settings.py (API key configuration)

Analysis:
The crash occurs because self.provider is None. This happens when:
1. API key not configured → _init_provider() fails
2. Exception caught but provider stays None
3. send_message() called on None object

Fix: Configure your API key in settings or environment.
See [[REF: settings.py]] for configuration options.
```

---

## 🔒 Security: Automated Secret Quarantine

### The VibeAudit System

Before generating any PDF, VibeCode scans for:

<table>
<tr>
<td width="50%">

**Detected Patterns:**
- 🔑 API keys (AWS, Google, Stripe, OpenAI, etc.)
- 🗝️ Database credentials (PostgreSQL, MySQL, MongoDB)
- 🎫 JWT tokens and session secrets
- 🔐 Private keys (RSA, SSH, GPG)
- 🔓 OAuth tokens and client secrets
- 💳 Payment gateway credentials
- 🌐 Webhook secrets and signing keys

</td>
<td width="50%">

**Security Features:**
- ✅ Pre-generation scanning (not post-facto)
- ✅ Interactive review (user maintains control)
- ✅ Context preview (see surrounding code)
- ✅ Individual decisions (not bulk auto-redact)
- ✅ Confidence scoring (High/Medium/Low)
- ✅ File and line number tracking
- ✅ Compliance-ready output

</td>
</tr>
</table>

### Interactive Review Process

When secrets are detected:

```
╔══════════════════════════════════════════════════════════════╗
║  🔒 Security Quarantine: Potential Secrets Detected          ║
╠══════════════════════════════════════════════════════════════╣
║  ⚠️ Found 3 potential secret(s). Please review each item.    ║
║                                                               ║
║  🔴 Redact = Replace with [REDACTED SECRET]                  ║
║  🟢 Ignore = Keep original value                             ║
╚══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ API Key (Stripe) - HIGH CONFIDENCE                          │
├─────────────────────────────────────────────────────────────┤
│ 📄 config/settings.py : Line 42                             │
│ Context: STRIPE_API_KEY = "sk_live_abc123def456..."         │
│ Value: sk_live_abc...def456                                 │
│                                                              │
│ [🔴 Redact]  [🟢 Ignore]                                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Database Password - MEDIUM CONFIDENCE                        │
├─────────────────────────────────────────────────────────────┤
│ 📄 config/database.py : Line 15                             │
│ Context: DB_URL = "postgresql://user:secret@localhost..."   │
│ Value: secret                                                │
│                                                              │
│ [🔴 Redact]  [🟢 Ignore]                                     │
└─────────────────────────────────────────────────────────────┘

Actions: [🔴 Redact All] [🟢 Ignore All] [✅ Proceed with Generation]
```

**Compliance-Grade:**
- PDFs can be safely emailed to consultants
- Uploaded to public code review platforms
- Archived for regulatory compliance
- Shared with non-technical stakeholders

---

## ⏰ Time Travel: Version Comparison with AI Explanations

### Dual-Snapshot Analysis

Load two PDF snapshots and let AI explain what changed:

<table>
<tr>
<td width="50%">

#### The Workflow

```bash
# 1. Load current state
vibecode chat

# 2. Enable Time Travel
Menu → Time Travel → Load Reference

# 3. Select old snapshot
production_v1.0.pdf

# 4. Ask questions
"What broke between v1.0 and v2.0?"
```

</td>
<td width="50%">

#### Under The Hood

```python
1. Load current snapshot (v2.0)
2. Load reference snapshot (v1.0)
3. For each file:
   - Compute unified diff
   - Inject into context
4. Gemini analyzes changes
5. Provides architectural explanation
```

</td>
</tr>
</table>

### Example Conversation

```
User: "What changed in the authentication system?"

ChatEngine (Time Travel Mode):
!!! TIME TRAVEL MODE ACTIVE !!!
Comparing: v2.0 (current) vs v1.0 (reference)

=== DIFF DETECTED: auth.py ===
@@ -45,7 +45,3 @@
 def create_session(user):
-    # Cache session for faster lookups
-    self.session_cache[user.id] = session
-    logger.debug(f"Cached session for {user.id}")
     return session

Response:
The authentication flow changed significantly in v2.0. The session cache 
(lines 45-52 in v1.0) was removed, which is causing the logout bug you're 
experiencing.

In v1.0, sessions were cached:
```python
self.session_cache[user.id] = session
```

v2.0 removed this entirely, so `logout()` can't find active sessions when 
it tries to invalidate them. This is why users aren't being logged out 
properly.

Recommendation: Either restore the cache or refactor logout() to not 
depend on it. See [[REF: auth.py]] lines 45-52 (v1.0) for the old 
implementation.
```

### Use Cases

- 🐛 **Regression Debugging:** "Why did this break after the refactor?"
- 👀 **Code Review:** "What changed since the last snapshot?"
- 📚 **Learning:** "How did we solve this before?"
- 📋 **Compliance:** "Show me what changed in the security layer"

---

## 🔌 Bidirectional MCP: Universal AI Socket

VibeCode doesn't just *use* MCP tools — **it can BE an MCP server**, creating a multiplier effect in the AI tool ecosystem.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Tool Ecosystem                         │
│                                                              │
│  Claude Desktop ──┐                                          │
│  Cursor ─────────┼──→ [MCP Protocol] ──→ VibeCode (Server)  │
│  Custom Agent ────┘                            │             │
│                                                │             │
│                                    VibeCode (Client) ────┐   │
│                                                │         │   │
│                                                ↓         ↓   │
│                                          GitHub API  Drive   │
└─────────────────────────────────────────────────────────────┘

Multi-hop workflow:
Claude → uses VibeCode → which uses GitHub → creates a tool chain
```

### VibeCode as MCP Client

**Configuration:** `config/mcp_servers.json`

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "drive": {
      "command": "python",
      "args": ["src/vibecode/mcp_server_gdrive_real.py"],
      "env": {
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    }
  }
}
```

**Available Actions:**
- `github__create_issue` - File bugs directly from chat
- `github__search_code` - Search across repositories  
- `drive__search` - Find Google Drive documents
- `drive__read_file` - Read file contents
- `slack__send_message` - Post to Slack channels

**Extension 5 - RAG Auto-Ingest:**  
When MCP tools return substantial text (>100 chars), VibeCode automatically indexes it in ChromaDB for future semantic search.

### VibeCode as MCP Server

**Start the server:**

```bash
vibecode serve --port 8080 --project /path/to/project
```

**Exposed Tools** (for Claude Desktop, Cursor, etc.):

| Tool | Description | Example |
|------|-------------|---------|
| `snapshot_codebase` | Generate Digital Twin PDFs | `snapshot_codebase(path=".", output_type="llm")` |
| `search_files` | Pattern-based file search | `search_files(query="auth", extensions=[".py"])` |
| `read_file` | Read file contents (1MB limit) | `read_file(file_path="src/main.py")` |
| `list_files` | Browse directory structure | `list_files(path="src", max_depth=3)` |
| `get_project_summary` | Get project statistics | `get_project_summary(path=".")` |

**Integration Example - Claude Desktop:**

```json
// ~/.config/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "vibecode": {
      "command": "vibecode",
      "args": ["serve", "--project", "/Users/me/my-react-app"]
    }
  }
}
```

**Now Claude can:**

```
User: "Create a snapshot of my React app and analyze its architecture"

Claude:
[Calls vibecode__snapshot_codebase(path="/Users/me/my-react-app")]
→ Response: "Snapshot created: /Users/me/my-react-app/snapshot_llm.pdf"

[Reads the 180K token PDF]

Analysis: "Your React app follows a standard component architecture with:
- 45 components in src/components/
- Redux state management (store/ directory)
- API layer abstracted in src/services/
- TypeScript for type safety

Key findings:
- No error boundaries in components/ 
- API calls lack retry logic
- Some components exceed 500 lines (should be split)

Would you like me to file GitHub issues for these improvements?"

User: "Yes please"

[Claude calls github__create_issue for each finding]
```

---

## 🎨 Advanced Features

### 1. 🎭 Persona System

Switch AI behavior modes for different tasks:

<table>
<tr>
<th>Persona</th>
<th>Focus</th>
<th>Use Case</th>
</tr>
<tr>
<td><b>Code Reviewer</b></td>
<td>Security, best practices, bug detection</td>
<td>Pre-commit review, security audits</td>
</tr>
<tr>
<td><b>Debugger</b></td>
<td>Aggressive crash analysis, hypothesis generation</td>
<td>Production incidents, stack trace analysis</td>
</tr>
<tr>
<td><b>Architect</b></td>
<td>High-level design, system thinking, trade-offs</td>
<td>Refactoring plans, technology decisions</td>
</tr>
<tr>
<td><b>Explainer</b></td>
<td>Beginner-friendly, step-by-step, analogies</td>
<td>Onboarding, documentation, teaching</td>
</tr>
</table>

### 2. 📚 Project Registry

- 💾 Save favorite projects with colors and tags
- ⚡ Quick-switch between codebases
- 🔍 Auto-discovery via `.vibecode.yaml` scanning
- 📊 Tracks file counts, last access, custom metadata

### 3. 🎨 Extension Manager

- 📝 Configure file types (`.py`, `.js`, `.cpp`, `.vue`, etc.)
- 📦 Presets: "Python", "Web", "C++", "Rust", "All"
- ➕ Add custom extensions for domain-specific languages
- ✨ Smart defaults with override capability

### 4. 📊 Diff View

- 🔍 See what changed since last snapshot
- 📁 File-level change tracking
- 🎨 Unified diff display
- 🟢🔴 Color-coded additions/deletions

### 5. ⚡ Batch Export

- 📦 Generate snapshots for multiple projects simultaneously
- 🚀 Parallel processing for speed
- 📝 Consistent naming and organization
- 👥 Perfect for team synchronization

### 6. 📝 Markdown Export

- 📄 Alternative to PDF for copy-paste workflows
- 🌳 Tree structure + file contents in `.md` format
- 🐙 GitHub-compatible formatting
- 💨 Lighter weight for quick sharing

### 7. 💾 Persistent Memory (ChromaDB)

- 🔄 Conversation history survives app restarts
- 🔍 Semantic search across past discussions
- 📁 File embeddings cached for instant retrieval
- 🔁 Auto-sync when files change

### 8. 🎯 Smart Scan

- 🤖 AI-powered file discovery
- 🙈 Respects `.gitignore` patterns
- ⚙️ Configurable ignore rules (venv, cache, node_modules)
- 🎛️ Extension-based filtering

### 9. ❄️ Frozen State Injection (ECR #008)

- 📸 Captures runtime environment (Python version, platform, packages)
- 📦 Embeds in snapshot for reproducibility
- ⏰ Timestamped `pip freeze` output
- 🔧 Helps future debugging ("What packages were installed?")

### 10. 🔄 Multi-Provider Support

```python
Supported LLM Providers:
├── Google Gemini (primary)
│   ├── gemini-3-flash-preview
│   ├── gemini-flash-latest
│   ├── gemini-1.5-pro
│   └── gemini-embedding-001
│
├── OpenAI
│   ├── gpt-4o
│   ├── gpt-4o-mini
│   └── text-embedding-3-small
│
├── Anthropic
│   └── claude-3-5-sonnet-20241022
│
├── Ollama (Local/Offline)
│   ├── llama3.2
│   ├── codellama
│   └── nomic-embed-text
│
└── Custom (Any OpenAI-compatible API)
    ├── NVIDIA NIM
    ├── OpenRouter
    ├── Groq
    └── Together AI
```

**Provider-Specific Optimizations:**
- **Gemini:** Structured outputs, function calling, 1M+ context
- **OpenAI:** Streaming, embeddings, fine-tuning compatible
- **Ollama:** Offline operation, privacy-first, zero API costs
- **Custom:** Flexible base URL configuration

---

## 🏗️ Technical Architecture

### Stack

<table>
<tr>
<td width="50%">

#### Frontend
- **PyQt6** - Production-grade GUI framework
- **Custom Widgets:**
  - `ChatBubble` - Markdown-rendered messages
  - `ThinkingWidget` - Collapsible reasoning blocks
  - `PatchWidget` - Code diff viewer with apply
- **Async Workers** - Prevent UI freezing
- **Dark Theme** - Optimized for coding sessions

</td>
<td width="50%">

#### Backend
- **Python 3.9+** with type hints
- **FastMCP** for server mode
- **ChromaDB** for vector storage
- **pypdf** for PDF parsing
- **fpdf2** (LLM) + **WeasyPrint** (Human)
- **Model Context Protocol SDK**
- **python-dotenv** for env management

</td>
</tr>
</table>

### AI Integration

```python
google-genai          # New unified Gemini SDK
├── generate_content  # Chat completions
├── embed_content     # Embeddings (gemini-embedding-001)
├── stream_content    # Streaming responses
└── function_calling  # MCP tool integration

Multi-Provider Support:
├── GoogleProvider    # Gemini (primary)
├── OpenAIProvider    # GPT-4 (fallback)
├── AnthropicProvider # Claude (optional)
└── OllamaProvider    # Local models (offline)
```

### Architecture Patterns

- **Singleton** - `MCPHost`, global state management
- **Factory** - LLM provider selection
- **Observer** - GUI event handling, streaming updates
- **Worker Thread** - Async operations (PDF generation, MCP calls)
- **Strategy** - LLM vs Human rendering modes
- **Repository** - Project registry, persistence

### Project Structure

```
vibecode-project/
│
├── src/vibecode/
│   │
│   ├── chat/                    # VibeChat Engine
│   │   ├── engine.py           # ChatEngine (context management)
│   │   ├── gui.py              # PyQt6 chat interface
│   │   ├── mcp_host.py         # MCP client integration
│   │   ├── memory.py           # Conversation history
│   │   ├── models.py           # Multi-provider LLM support
│   │   ├── ingest.py           # PDF parsing & context loading
│   │   ├── knowledge.py        # RAG knowledge base
│   │   └── persistence.py      # SQLite content storage
│   │
│   ├── agents/
│   │   └── mcp_agent.py        # Specialized MCP tool agent
│   │
│   ├── renderers/
│   │   ├── llm.py              # Machine-readable PDF generator
│   │   ├── human.py            # Human-readable PDF generator
│   │   ├── secrets.py          # Security scanner
│   │   └── markdown.py         # Markdown export
│   │
│   ├── gui/                     # Main Application
│   │   ├── main_window.py      # Project management
│   │   ├── dialogs.py          # Settings, MCP config, Time Travel
│   │   ├── workers.py          # Async operation handlers
│   │   └── utils.py            # GUI utilities
│   │
│   ├── config/
│   │   └── mcp_servers.json    # MCP server configuration
│   │
│   ├── ai.py                    # VibeSelect & VibeContext agents
│   ├── rag.py                   # VibeRAG (embeddings, similarity)
│   ├── mcp_server.py           # MCP server mode (Extension 6)
│   ├── engine.py               # ProjectEngine (snapshot generation)
│   ├── discovery.py            # File scanning & filtering
│   ├── cli.py                  # Command-line interface
│   ├── settings.py             # User settings & API keys
│   ├── registry.py             # Project registry
│   └── config.py               # Configuration management
│
├── pyproject.toml              # Dependencies & metadata
├── README.md                   # This file
├── LICENSE                     # MIT License
├── verify_install.py           # Installation verification
├── run_local.py                # GUI launcher
├── launch.bat                  # Windows launcher
└── unpack.py                   # Standalone PDF restoration tool
```

### Code Metrics

| Metric | Value |
|--------|-------|
| **Total Lines** | ~11,634 |
| **Core Engine** | ~3,000 lines |
| **GUI** | ~4,000 lines |
| **Renderers** | ~2,500 lines |
| **MCP Integration** | ~1,000 lines |
| **RAG/AI Features** | ~1,134 lines |
| **Languages** | Python 3.9+ |
| **Test Coverage** | Manual QA (production-tested) |

---

## 🎯 Use Cases

### For Individual Developers

#### 1. 📧 Code Review Preparation

```bash
# Before opening PR
vibecode human --output code_review.pdf

# Share with senior dev
# ✅ No repo access needed
# ✅ Syntax highlighted
# ✅ No secrets leaked
```

#### 2. 📚 Learning New Codebases

```
You: "Explain how authentication works in this project"

VibeChat:
[Analyzes all 180K tokens]

"Authentication flows through 3 layers:

1. **Middleware Layer** [[REF: middleware/auth_check.py]]
   - Intercepts all requests
   - Validates JWT tokens
   - Attaches user object to request

2. **Session Layer** [[REF: auth/session.py]]
   - Manages session lifecycle
   - 15-minute token expiry
   - Refresh token rotation

3. **Permission Layer** [[REF: auth/permissions.py]]
   - Role-based access control
   - Resource-level permissions
   - Admin/User/Guest roles

Click any [[REF: ...]] to see exact implementation."
```

#### 3. 🐛 Debugging Production Issues

```
[Paste stack trace from production]

Traceback (most recent call last):
  File "src/api/payment.py", line 89, in process_payment
    stripe.charge.create(amount=total)
stripe.error.CardError: Your card was declined

VibeChat:
!!! CRASH DETECTED IN api/payment.py AT LINE 89 !!!

Auto-loaded files:
✓ api/payment.py (crash site)
✓ models/transaction.py (payment model)
✓ config/stripe.py (Stripe configuration)

Analysis:
The error occurs in process_payment() when calling stripe.charge.create().
CardError is a user-facing error (card declined), not a code bug.

However, I notice a potential issue in your error handling:
[[REF: api/payment.py]] lines 92-95 don't log failed transactions.

Recommendation: Add transaction logging before the Stripe call:
```python
logger.info(f"Attempting payment: {transaction.id} amount={total}")
try:
    stripe.charge.create(...)
except stripe.error.CardError as e:
    logger.warning(f"Card declined: {transaction.id} reason={e}")
    # Save failed transaction for retry
    transaction.mark_failed(reason=str(e))
```

This will help you track and retry failed payments."
```

---

### For Teams

#### 4. 📦 Compliance Archiving

```bash
# End of sprint/quarter
vibecode llm --output Q1_2026_sprint_42.pdf

# Store in compliance folder
cp Q1_2026_sprint_42.pdf /archive/compliance/2026/

# Benefits:
# ✅ Immutable record (PDF/A format)
# ✅ Tamper-evident (SHA-256 checksums)
# ✅ Self-contained (no external dependencies)
# ✅ Searchable (for audits)
```

#### 5. 🤝 Consultant Onboarding

```bash
# Scenario: Hiring a consultant for security audit
# Problem: Don't want to give them full repo access

# Solution:
vibecode human --output security_audit_snapshot.pdf

# Email the 2MB PDF
# ✅ No git access required
# ✅ No secrets (scanned & redacted)
# ✅ Beautiful formatting
# ✅ Consultant can search & analyze

# They can even restore it locally:
vibecode unpack security_audit_snapshot.pdf
```

#### 6. ⏰ Regression Analysis

```
Load: production_v1.0.pdf (before bug)
Load: production_v2.0.pdf (after bug)

You: "What changed in the payment processing flow?"

VibeChat (Time Travel):
=== DIFF DETECTED: api/payment.py ===
@@ -67,3 +67,1 @@
-    if not validate_card(card_number):
-        raise InvalidCardError()
     
     stripe.charge.create(...)

Response:
"Critical change found! v2.0 removed card validation (lines 67-69 in v1.0) 
before calling Stripe. This means invalid cards now reach Stripe, causing:

1. Higher processing fees (Stripe charges for failed attempts)
2. Degraded UX (slower error responses)
3. Security risk (exposes API to card testing attacks)

Recommendation: Restore the validation logic from v1.0 [[REF: api/payment.py]]"
```

---

### For Companies

#### 7. 🔄 Cross-Team Knowledge Sharing

```
Backend Team:
vibecode llm --output api_v2.pdf
# Share with frontend team

Frontend Team receives pdf:
"How does the new authentication API work?"

VibeChat:
[Analyzes backend snapshot]

"The v2 API uses JWT with these endpoints:

POST /api/v2/auth/login
  Request: {username, password}
  Response: {access_token, refresh_token, expires_in}

POST /api/v2/auth/refresh  
  Request: {refresh_token}
  Response: {access_token, expires_in}

Key changes from v1:
- Added refresh tokens (15min access, 7day refresh)
- Removed session cookies
- All endpoints require Authorization: Bearer <token>

See [[REF: api/v2/auth/routes.py]] for implementation details."
```

#### 8. 🚨 Incident Response

```bash
# Production is down!

# 1. Snapshot current broken state
vibecode llm --output prod_incident_2026_02_11.pdf

# 2. Load last known good snapshot
production_2026_02_10_working.pdf

# 3. Time Travel comparison
You: "What changed in the last 24 hours that could cause the outage?"

VibeChat:
"Found critical infrastructure change in config/database.py:

=== DIFF ===
-    CONNECTION_POOL_SIZE = 10
+    CONNECTION_POOL_SIZE = 100

This 10x increase in connection pool size likely exhausted database 
resources. Current RDS instance supports max 200 connections but you 
now have 10 workers × 100 = 1000 attempted connections.

Immediate fix: Revert to POOL_SIZE = 10
Long-term: Upgrade RDS instance or implement connection pooling"
```

#### 9. ✅ Code Quality Gates (CI/CD)

```bash
# .github/workflows/quality-gate.yml

- name: Generate Snapshot
  run: vibecode llm --output ${{ github.sha }}.pdf

- name: Security Scan
  run: |
    python -c "
    from vibecode.renderers.secrets import SecretScanner
    scanner = SecretScanner()
    # Load file data...
    candidates = scanner.scan_files(file_data)
    if candidates:
        print(f'❌ FAILED: {len(candidates)} secrets detected')
        exit(1)
    "

- name: Upload Artifact
  uses: actions/upload-artifact@v3
  with:
    name: code-snapshot
    path: ${{ github.sha }}.pdf
```

---

### For AI Agents

#### 10. 🤖 Claude Desktop Integration

**Setup:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "vibecode": {
      "command": "vibecode",
      "args": ["serve", "--project", "/Users/me/projects/myapp"]
    }
  }
}
```

**Workflow:**

```
You: "Analyze this codebase and create GitHub issues for technical debt"

Claude:
[Calls vibecode__snapshot_codebase(path="/Users/me/projects/myapp")]
→ "Snapshot created: snapshot_llm.pdf"

[Reads & analyzes 180K tokens]

"I've identified 5 areas of technical debt:

1. **No Error Boundaries in React Components**
   - 12 components lack error handling
   - Could crash entire app on component failure
   
2. **API Calls Missing Retry Logic**
   - 8 API endpoints in services/ have no retry
   - Single network blip causes failures
   
3. **Large Components Need Splitting**
   - UserProfile.tsx (847 lines) should be 3 components
   - Dashboard.tsx (623 lines) violates SRP

4. **Missing TypeScript Strict Mode**
   - tsconfig.json has strict: false
   - Losing type safety benefits

5. **No API Response Caching**
   - Repeated calls to /api/user fetch same data
   - Could use React Query or SWR

Would you like me to file GitHub issues for these?"

You: "Yes, do it"

[Claude calls github__create_issue 5 times with detailed descriptions]

"Done! Created 5 issues:
- #245: Add error boundaries to React components
- #246: Implement retry logic for API calls  
- #247: Refactor UserProfile component
- #248: Enable TypeScript strict mode
- #249: Add API response caching

All tagged with 'technical-debt' and assigned to the 'refactoring' milestone."
```

#### 11. 🔄 Multi-Codebase Analysis

```python
# Custom AI Agent Workflow

async def analyze_microservices():
    """Compare architecture across microservices"""
    
    services = ["user-service", "payment-service", "notification-service"]
    summaries = []
    
    for service in services:
        # Get project summary
        summary = await vibecode__get_project_summary(
            path=f"/company/microservices/{service}"
        )
        summaries.append(json.loads(summary))
        
        # Create snapshot for detailed analysis
        snapshot = await vibecode__snapshot_codebase(
            path=f"/company/microservices/{service}",
            output_type="llm"
        )
    
    # AI analyzes all summaries
    analysis = await llm.analyze(f"""
    Compare these microservice architectures:
    {json.dumps(summaries, indent=2)}
    
    Find inconsistencies in:
    - Error handling patterns
    - Logging strategies  
    - Database connection management
    - API versioning
    """)
    
    return analysis

# Result:
"""
Architectural Inconsistencies Found:

1. **Error Handling:**
   - user-service: Uses custom exceptions
   - payment-service: Uses standard HTTP status codes
   - notification-service: Mix of both
   → Recommendation: Standardize on HTTP status codes

2. **Logging:**
   - user-service: structlog (JSON)
   - payment-service: Python logging (text)
   - notification-service: No structured logging
   → Recommendation: Migrate all to structlog

3. **Database Connections:**
   - user-service: Connection pool size 10
   - payment-service: Connection pool size 50  
   - notification-service: No pooling
   → Recommendation: Standardize pool size based on load
"""
```

---

## 🏆 Why VibeCode is Revolutionary

### The Problem with Traditional Approaches

<table>
<tr>
<th>Tool</th>
<th>Approach</th>
<th>Limitations</th>
</tr>
<tr>
<td><b>Cursor / Copilot</b></td>
<td>Stream open files to AI</td>
<td>
❌ Only sees currently open files<br>
❌ No whole-program reasoning<br>
❌ Can't compare versions<br>
❌ No portability (requires git)
</td>
</tr>
<tr>
<td><b>Traditional RAG</b></td>
<td>Chunk + embed + retrieve</td>
<td>
❌ Chunks lose context boundaries<br>
❌ Retrieval is probabilistic<br>
❌ No guarantee of completeness<br>
❌ Hard to version/archive
</td>
</tr>
<tr>
<td><b>Git-based tools</b></td>
<td>Clone repo, analyze files</td>
<td>
❌ Requires clone (50-500MB)<br>
❌ Needs network access<br>
❌ Can't email or archive easily<br>
❌ Git history noise
</td>
</tr>
</table>

### VibeCode's Paradigm Shift

#### ✅ **1. Treat Code as Data**

Instead of asking *"How do we feed code to AI?"*, VibeCode asks:

> **"What if code were a first-class data type that could be serialized, transmitted, and cryptographically verified?"**

**The Result:**

```
Traditional:          VibeCode Digital Twins:
───────────          ─────────────────────
Git clone            → Email PDF
  50-500MB             2-10MB
  
Requires network     → Works offline
  git fetch            Air-gapped OK
  
Mutable             → Immutable  
  can be modified      Tamper-evident
  
Chunked for AI      → Whole-program
  RAG retrieval        Full context
  
No verification     → Verified
  trust-based          SHA-256 checksums
```

#### ✅ **2. Whole-Program Reasoning**

Gemini sees the **ENTIRE** project simultaneously (up to 1M tokens):

- ✅ Understands cross-file dependencies
- ✅ Spots architectural patterns across modules
- ✅ Detects inconsistencies in coding style
- ✅ Provides holistic insights (not just local suggestions)
- ✅ Compares versions with semantic understanding

**Example:**

```
Traditional RAG:
Query: "How does auth work?"
→ Retrieves: auth.py (maybe misses session.py, middleware.py)
→ Incomplete answer

VibeCode:
Query: "How does auth work?"
→ Has: ALL files in context
→ Finds: auth.py, session.py, middleware.py, permissions.py
→ Response: "Authentication flows through 3 layers..." (complete)
```

#### ✅ **3. Bidirectional MCP Integration**

**Most tools are clients OR servers. VibeCode is BOTH:**

```
As Client:                     As Server:
VibeCode → GitHub             Claude Desktop → VibeCode
VibeCode → Google Drive       Cursor → VibeCode
VibeCode → Slack              Custom Agent → VibeCode

Creates a multiplier effect:
Claude → VibeCode → GitHub → Creates multi-hop workflows
```

**Unique Capabilities:**
- Other AI agents can use Digital Twin technology
- Tool chain composition (Agent A uses Agent B uses Agent C)
- Network effects in the AI tool ecosystem

#### ✅ **4. Security-First Design**

Not an afterthought:

- 🔒 Pre-generation secret scanning
- 👤 Interactive quarantine (user maintains control)
- ✅ Compliance-ready output (safe to share)
- 🔐 Cryptographic verification (tamper-evident)

#### ✅ **5. Perfect Restoration**

**No other tool can do this:**

```bash
vibecode llm                           # Create snapshot
rm -rf *                               # Delete everything
vibecode unpack snapshot.pdf           # Perfect restoration
diff -r original/ restored/            # Zero differences
```

SHA-256 verified, bit-for-bit identical.

---

## 📊 Competitive Analysis

| Feature | VibeCode | Cursor | Copilot | Aider | Cody |
|---------|----------|--------|---------|-------|------|
| **Whole codebase in context** | ✅ 180K tokens | ❌ Open files only | ❌ Open files only | ❌ Git-based | ❌ Limited |
| **Perfect restoration** | ✅ SHA-256 | ❌ | ❌ | ❌ | ❌ |
| **Portable snapshots** | ✅ PDF | ❌ | ❌ | ❌ | ❌ |
| **Version comparison** | ✅ Time Travel | Partial | ❌ | ❌ | ❌ |
| **Secret scanning** | ✅ Pre-generation | ❌ | ❌ | ❌ | ❌ |
| **Offline capable** | ✅ Ollama | ❌ | ❌ | ❌ | ❌ |
| **Multi-provider** | ✅ 4+ providers | ❌ Single | ❌ Single | Limited | Limited |
| **Human-readable output** | ✅ Syntax PDF | ❌ | ❌ | ❌ | ❌ |
| **Semantic search** | ✅ RAG | Basic | ❌ | ❌ | ✅ |
| **MCP server mode** | ✅ Exposes tools | ❌ | ❌ | ❌ | ❌ |
| **MCP client mode** | ✅ Uses external tools | ❌ | ❌ | ❌ | ❌ |
| **Compliance archives** | ✅ Immutable PDFs | ❌ | ❌ | ❌ | ❌ |
| **Citation system** | ✅ [[REF: file.py]] | Partial | ❌ | ❌ | Partial |
| **Extended thinking** | ✅ <think> blocks | ❌ | ❌ | ❌ | ❌ |
| **Code patches** | ✅ <patch> GUI | ❌ | ❌ | ✅ Direct edit | ❌ |

---

## 📈 Performance & Scale

### What VibeCode Handles

| Metric | Typical | Maximum Tested |
|--------|---------|----------------|
| **Projects** | 50-200 files | 500+ files |
| **Tokens** | 180K | 500K+ |
| **PDF Size** | 2-5MB | 10MB |
| **Restoration Time** | <5 seconds | <30 seconds |
| **Generation Speed** | 30 seconds | 2 minutes |
| **Context Window** | 1M tokens (Gemini) | 2M tokens (Gemini Pro) |
| **Supported Languages** | Python-focused | Any text-based |
| **Concurrent Chats** | 5+ sessions | Limited by RAM |

### Performance Optimizations

**PDF Generation:**
- ✅ ProcessPoolExecutor (multi-core parallelization)
- ✅ Lazy loading (stream files from disk)
- ✅ Incremental rendering (progress updates)

**Embedding:**
- ✅ Batched API calls (reduce latency)
- ✅ Persistent cache (ChromaDB)
- ✅ Auto-sync on file changes only

**Streaming:**
- ✅ Token-by-token display (no waiting)
- ✅ Async worker threads (UI never freezes)
- ✅ Cancellable operations

**Memory:**
- ✅ ~500MB typical usage
- ✅ Lazy context loading
- ✅ SQLite for cold storage (ECR #007)

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.9 or higher
- 500MB free disk space
- Internet connection (for API access)
- Optional: Ollama (for offline models)

### Step-by-Step Installation

#### 1. Clone Repository

```bash
git clone https://github.com/ajpop3y/vibecode-project.git
cd vibecode-project
```

#### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install -e .
```

This installs:
- Core: `typer`, `pyyaml`, `pathspec`, `pydantic`
- PDF: `fpdf2`, `weasyprint`, `pypdf`
- GUI: `PyQt6`
- AI: `google-genai`, `openai`, `anthropic` (optional)
- RAG: `chromadb`
- MCP: `mcp>=1.20.0`

#### 4. Verify Installation

```bash
python verify_install.py
```

Expected output:
```
=== Vibecode Diagnostic Tool ===

[1/2] Testing LLM Renderer (Auto-Healing Font)...
   ✅ SUCCESS: Font located at ~/.vibecode/fonts/DejaVuSans.ttf
   ✅ SUCCESS: UTF-8 mode is ENABLED.
   ✅ SUCCESS: generated 'test_llm_output.pdf'

[2/2] Testing Human Renderer (Parallel Processing)...
   ✅ SUCCESS: Rendered in 2.34 seconds.

==============================
🎉 SYSTEM READY: All renderers are operational.
   You can now run 'vibecode gui' or 'vibecode llm'
==============================
```

#### 5. Configure API Key

**Option A: GUI (Recommended)**

```bash
python run_local.py
# Click ⚙️ → Enter Google API Key → Save
```

**Option B: Environment Variable**

```bash
# macOS/Linux
export GOOGLE_API_KEY="your-api-key-here"

# Windows
set GOOGLE_API_KEY=your-api-key-here
```

**Option C: .env File**

```bash
echo "GOOGLE_API_KEY=your-api-key-here" > .env
```

#### 6. Optional: MCP Server Setup

**For Google Drive:**

```bash
# 1. Get OAuth credentials from Google Cloud Console
# 2. Save as src/vibecode/secrets/credentials.json
# 3. Run authentication helper
python -m vibecode.auth_helper
```

**For GitHub:**

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

---

## 📖 Documentation

### Command-Line Interface

```bash
# Generate snapshots
vibecode llm                    # Machine-readable PDF
vibecode human                  # Human-readable PDF
vibecode llm --output custom.pdf  # Custom filename

# Chat with codebase
vibecode chat                   # Interactive chat
vibecode chat --pdf snapshot.pdf  # Use specific snapshot

# Restoration
vibecode unpack snapshot.pdf    # Restore to current directory
vibecode unpack snapshot.pdf --output ./restored/

# MCP Server Mode
vibecode serve                  # Start MCP server
vibecode serve --port 8080      # Custom port
vibecode serve --project /path  # Specific project

# Project management
vibecode gui                    # Launch GUI application
```

### GUI Application

```bash
python run_local.py

# Or on Windows
launch.bat
```

**Features:**
- 📁 Project management with registry
- 🎨 Smart file selection
- 🤖 AI-powered VibeSelect
- 💬 VibeChat interface
- ⏰ Time Travel comparison
- 🔒 Secret scanning review
- ⚙️ Settings management

### Python API

```python
from vibecode.engine import ProjectEngine
from vibecode.chat.engine import ChatEngine

# Generate snapshot
engine = ProjectEngine(".vibecode.yaml")
engine.render("llm", "output.pdf")

# Chat with codebase
chat = ChatEngine(pdf_path="output.pdf")
response = chat.send_message("How does auth work?")
print(response)

# Streaming
for chunk in chat.stream_message("Explain the architecture"):
    print(chunk, end="", flush=True)
```

---

## 🛠️ Configuration

### Project Configuration (`.vibecode.yaml`)

```yaml
# Project metadata
name: "My Awesome Project"
version: "1.0.0"

# Files to include
files:
  - "src/**/*.py"
  - "tests/**/*.py"
  - "README.md"
  - "pyproject.toml"

# Files to exclude  
exclude:
  - "**/__pycache__/**"
  - "**/*.pyc"
  - ".git/**"
  - ".venv/**"
  - "node_modules/**"

# Extensions to scan
extensions:
  - ".py"
  - ".js"
  - ".ts"
  - ".md"
  - ".yaml"
  - ".json"

# Custom settings
settings:
  max_file_size: 1048576  # 1MB
  follow_symlinks: false
  ignore_hidden: true
```

### MCP Configuration (`config/mcp_servers.json`)

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "drive": {
      "command": "python",
      "args": ["src/vibecode/mcp_server_gdrive_real.py"],
      "env": {
        "GOOGLE_APPLICATION_CREDENTIALS": "${GOOGLE_APPLICATION_CREDENTIALS}"
      }
    },
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}"
      }
    }
  }
}
```

---

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

### Development Setup

```bash
# Fork & clone
git clone https://github.com/YOUR_USERNAME/vibecode-project.git
cd vibecode-project

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
isort src/
```

### Contribution Areas

- 🐛 **Bug Reports:** File issues with reproduction steps
- ✨ **Feature Requests:** Describe use cases and benefits
- 📝 **Documentation:** Improve READMEs, add examples
- 🔌 **MCP Servers:** Add new integrations (Jira, Notion, etc.)
- 🎨 **UI/UX:** Enhance GUI, add themes
- 🧪 **Testing:** Add unit tests, integration tests
- 🌍 **Internationalization:** Add language support

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

```
Copyright (c) 2026 Ajpop3y

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 🙏 Acknowledgments

- **Gemini 3 Hackathon** - For inspiring this innovation
- **Google DeepMind** - For the incredible Gemini API
- **Model Context Protocol** - For the universal tool integration standard
- **PyQt6** - For the robust GUI framework
- **ChromaDB** - For the persistent vector database
- **Nigerian Power Grid** - For the challenge that proved resilience 😅

---

## 🔗 Links & Resources

### Project Links
- 🌐 [GitHub Repository](https://github.com/ajpop3y/vibecode-project)
- 📝 [Documentation](https://github.com/ajpop3y/vibecode-project/wiki)
- 🐛 [Issue Tracker](https://github.com/ajpop3y/vibecode-project/issues)
- 💬 [Discussions](https://github.com/ajpop3y/vibecode-project/discussions)

### Related Links
- 🎯 [Gemini 3 Hackathon](https://gemini3.devpost.com/)
- 🤖 [Google AI Studio](https://aistudio.google.com/)
- 🔌 [Model Context Protocol](https://modelcontextprotocol.io/)
- 📚 [Gemini API Docs](https://ai.google.dev/docs)

### Community
- 🐦 Twitter: [@VibeCodeDev](https://twitter.com/vibecodedev)
- 💼 LinkedIn: [Ajpop3y](https://linkedin.com/in/ajpop3y)
- 📧 Email: ajpop3y@gmail.com

---

## ⭐ Star History

If you find VibeCode useful, please consider starring the repository!

[![Star History](https://api.star-history.com/svg?repos=ajpop3y/vibecode-project&type=Date)](https://star-history.com/#ajpop3y/vibecode-project&Date)

---

<div align="center">

### 🚀 Built with determination during a Nigerian power outage for the Gemini 3 Hackathon

**VibeCode isn't just a tool — it's a new paradigm for treating code as serializable data in the AI era.**

---

**Made with ❤️ by [Ajpop3y](https://github.com/ajpop3y)**

**Powered by [Gemini 3](https://ai.google.dev/)**

---

</div>
