# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Retrieval-Augmented Generation (RAG) chatbot that answers questions about course materials. FastAPI backend, vanilla JS frontend, ChromaDB for vector storage, Anthropic Claude for generation via tool-calling.

## Commands

Package manager is `uv` (not pip). Python >=3.13. **Always use `uv` for everything — installing dependencies, adding/removing packages, running the server, and running any standalone Python file. Never invoke `pip`, a bare `python`, or a bare `uvicorn` directly, and never hand-edit `pyproject.toml`/`uv.lock` dependency entries.**

```bash
# Install dependencies
uv sync

# Add/remove a dependency
uv add <package>
uv remove <package>

# Run the app (from repo root) — requires Git Bash on Windows since it's a shell script
./run.sh

# Equivalent manual start
cd backend && uv run uvicorn app:app --reload --port 8000

# Run any Python script/file
uv run <file.py>
```

App serves at `http://localhost:8000` (chat UI) and `http://localhost:8000/docs` (FastAPI Swagger).

Required env var in a `.env` file at repo root: `ANTHROPIC_API_KEY`.

There is no test suite, linter, or build step configured in this repo.

## Architecture

Request flow: `frontend/script.js` → `POST /api/query` (`backend/app.py`) → `RAGSystem.query()` (`backend/rag_system.py`) → `AIGenerator` (`backend/ai_generator.py`), which calls Claude with a single tool, `search_course_content`.

- **Tool-driven search, not always-on RAG**: Claude itself decides per query whether to call the search tool (course-specific questions) or answer from its own knowledge (general questions). This is governed entirely by the system prompt in `AIGenerator.SYSTEM_PROMPT`, not by code branching.
- **One tool round-trip only**: `AIGenerator._handle_tool_execution()` executes tool calls once and makes a second Claude call *without* the `tools` param, so Claude cannot chain further searches within a single query. "One search per query" is a prompt instruction, not an enforced limit.
- **Two ChromaDB collections** (`backend/vector_store.py`): `course_catalog` holds course/lesson metadata and is used only to fuzzy-resolve a user-supplied course name (e.g. "MCP") to an exact stored title via semantic search; `course_content` holds the actual chunked text and is what gets searched for answers. A search first resolves the course name (if given), then queries content filtered by resolved title/lesson number.
- **Sources are a side channel**: `CourseSearchTool` stashes source labels (course + lesson) on `self.last_sources` as a side effect of `execute()`. `RAGSystem.query()` pulls them via `ToolManager.get_last_sources()` after generation completes and resets them — they never flow through Claude's response text, so they're returned to the frontend as a separate `sources` list alongside `answer`.
- **Sessions are in-memory only** (`backend/session_manager.py`): keyed by an incrementing `session_N` string, no persistence across restarts, history truncated to the last `MAX_HISTORY` exchanges (config default 2).
- **Document ingestion** (`backend/document_processor.py`): runs automatically on startup against `../docs` relative to `backend/` (see `app.py` startup event), skipping any course whose title already exists in the vector store — so re-adding a file with the same `Course Title:` is a no-op, not an update. Expects a specific text format:
  ```
  Course Title: [title]
  Course Link: [url]
  Course Instructor: [instructor]

  Lesson 0: Introduction
  Lesson Link: [url]
  [content...]

  Lesson 1: ...
  ```
  Lessons are split into sentence-aware overlapping chunks (`CHUNK_SIZE`/`CHUNK_OVERLAP` in `config.py`, defaults 800/100 chars). Note: chunk-context prefixing differs between the last lesson in a file and all preceding lessons (last lesson prefixes every chunk with `"Course {title} Lesson {n} content: ..."`; earlier lessons only prefix the first chunk of each lesson with `"Lesson {n} content: ..."`) — this looks like a divergence between the in-loop and post-loop code paths rather than an intentional design choice, worth being careful around if touching chunking logic.
- **Config** (`backend/config.py`): single dataclass instance (`config`) imported wherever settings are needed — model name, embedding model (`all-MiniLM-L6-v2`), chunk size/overlap, max search results, max history, ChromaDB path. Change defaults here rather than passing overrides through call sites.

## Notes for local dev

- CORS and trusted-host middleware are wide open (`allow_origins=["*"]`, `allowed_hosts=["*"]`) — fine for local dev, not hardened for deployment.
- No authentication on any endpoint.
- Static frontend files are served with no-cache headers (`DevStaticFiles` in `app.py`) so browser caching won't mask frontend edits during development.
