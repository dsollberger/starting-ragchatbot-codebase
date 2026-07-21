import os
import sys
import pathlib

import pytest

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]  # .../backend
CHROMA_DB_PATH = BACKEND_DIR / "chroma_db"  # real, pre-populated, read-only for these tests

# Defensive fallback in case pytest is ever invoked without the pyproject.toml pythonpath setting picked up.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def real_chroma_path() -> str:
    """Absolute path to the existing, already-ingested chroma_db, independent of pytest's invocation cwd."""
    assert CHROMA_DB_PATH.is_dir(), f"expected existing chroma_db at {CHROMA_DB_PATH}"
    return str(CHROMA_DB_PATH)


@pytest.fixture
def real_vector_store(real_chroma_path):
    """A VectorStore wired to the REAL on-disk data. Read-only usage only in tests (never call add_*/clear_*)."""
    from vector_store import VectorStore
    return VectorStore(chroma_path=real_chroma_path, embedding_model="all-MiniLM-L6-v2", max_results=5)


@pytest.fixture
def mock_vector_store(mocker):
    """A fully mocked VectorStore for deterministic edge-case tests (no ChromaDB involved)."""
    from vector_store import VectorStore
    return mocker.create_autospec(VectorStore, instance=True)


@pytest.fixture
def anthropic_response_factory():
    """Builds minimal stand-ins for anthropic Message/content-block objects (attribute access only, no network)."""

    class _TextBlock:
        def __init__(self, text):
            self.type = "text"
            self.text = text

    class _ToolUseBlock:
        def __init__(self, id, name, input):
            self.type = "tool_use"
            self.id = id
            self.name = name
            self.input = input

    class _Message:
        def __init__(self, content, stop_reason):
            self.content = content
            self.stop_reason = stop_reason

    def _make(*, text=None, tool_calls=None, stop_reason):
        blocks = []
        if tool_calls:
            blocks.extend(_ToolUseBlock(**tc) for tc in tool_calls)
        if text is not None:
            blocks.append(_TextBlock(text))
        return _Message(blocks, stop_reason)

    return _make


@pytest.fixture
def mock_anthropic_client(mocker):
    """Patches anthropic.Anthropic used inside ai_generator so no real SDK client is constructed."""
    mock_client = mocker.MagicMock()
    mocker.patch("ai_generator.anthropic.Anthropic", return_value=mock_client)
    return mock_client


@pytest.fixture
def app_client():
    """
    TestClient for the real FastAPI app, importing it only after chdir'ing into backend/.

    This mirrors production (run.sh does `cd backend && uvicorn app:app`) and avoids the
    RuntimeError from StaticFiles(directory="../frontend") when pytest's cwd is the repo root.

    Deliberately NOT using `with TestClient(app) as client:` -- that form triggers the
    `@app.on_event("startup")` handler, which calls rag_system.add_course_folder("../docs", ...)
    against the REAL chroma_db. Skipping the context-manager form means startup never runs,
    so this fixture cannot mutate the shared database.
    """
    original_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        if str(BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(BACKEND_DIR))
        from app import app as fastapi_app
        from fastapi.testclient import TestClient
        yield TestClient(fastapi_app)
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def mock_rag_system(mocker):
    """
    RAGSystem double with sensible defaults, for deterministic endpoint tests.

    Not autospec'd: RAGSystem.session_manager is an instance attribute assigned in __init__
    (not visible on the class), so mocker.create_autospec(RAGSystem, instance=True) can't see
    it and raises AttributeError on access. A plain MagicMock allows it while still matching
    the attributes app.py actually calls (.query, .session_manager.*, .get_course_analytics).
    """
    mock = mocker.MagicMock()
    mock.session_manager.create_session.return_value = "test_session_1"
    mock.query.return_value = (
        "This is a test answer.",
        [{"text": "Course A - Lesson 1", "link": "https://example.com/lesson1"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    return mock


@pytest.fixture
def client(mock_rag_system):
    """
    TestClient for the real FastAPI app with its global `rag_system` swapped for a mock.

    Same chdir workaround as `app_client` (see its docstring), so the real static-file mount
    still resolves. Unlike `app_client`, requests here never reach the real ChromaDB or the
    Anthropic API, so endpoint tests can assert exact request/response contracts quickly and
    deterministically. Use `mock_rag_system` to control what the endpoints see per test.
    """
    original_cwd = os.getcwd()
    os.chdir(BACKEND_DIR)
    try:
        if str(BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(BACKEND_DIR))
        import app as app_module
        app_module.rag_system = mock_rag_system
        from fastapi.testclient import TestClient
        yield TestClient(app_module.app)
    finally:
        os.chdir(original_cwd)
