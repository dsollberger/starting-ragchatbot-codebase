import pytest

from config import config
from rag_system import RAGSystem


@pytest.fixture
def rag(mocker):
    """Real RAGSystem (real vector store, real empty-key AIGenerator client -- but never calls it directly)."""
    return RAGSystem(config)


def test_query_builds_prompt_and_calls_generator(rag, mocker):
    mock_generate = mocker.MagicMock(return_value="an answer")
    mocker.patch.object(rag.ai_generator, "generate_response", mock_generate)

    rag.query("what is MCP?")

    mock_generate.assert_called_once()
    call_kwargs = mock_generate.call_args.kwargs
    assert call_kwargs["query"] == "Answer this question about course materials: what is MCP?"
    assert call_kwargs["tools"] == rag.tool_manager.get_tool_definitions()
    assert call_kwargs["tool_manager"] is rag.tool_manager


def test_query_retrieves_and_resets_sources(rag, mocker):
    mocker.patch.object(rag.ai_generator, "generate_response", return_value="an answer")
    rag.search_tool.last_sources = [{"text": "t", "link": "l"}]

    _, sources = rag.query("what is MCP?")

    assert sources == [{"text": "t", "link": "l"}]
    assert rag.search_tool.last_sources == []


def test_query_updates_session_history(rag, mocker):
    mocker.patch.object(rag.ai_generator, "generate_response", return_value="the answer")
    session_id = rag.session_manager.create_session()

    rag.query("my question", session_id=session_id)

    history = rag.session_manager.get_conversation_history(session_id)
    assert "User: my question" in history
    assert "Assistant: the answer" in history


def test_query_without_session_id_skips_history(rag, mocker):
    mocker.patch.object(rag.ai_generator, "generate_response", return_value="the answer")

    answer, sources = rag.query("my question", session_id=None)

    assert answer == "the answer"
    assert rag.session_manager.sessions == {}


def test_rag_system_construction_uses_real_configured_key(rag):
    """Ties this layer back to the root cause without calling the Anthropic client."""
    assert rag.ai_generator.client.api_key == config.ANTHROPIC_API_KEY


@pytest.mark.live
def test_e2e_content_query_via_api_reproduces_query_failed(app_client):
    """
    Direct reproduction of the user-visible bug: a real content question through the
    real API, with the real (currently empty) API key. Isolated to the backend so it's
    clear this is a backend failure the frontend's hardcoded 'Query failed' string then
    compounds, not something caused by the frontend itself.
    """
    response = app_client.post("/api/query", json={"query": "What is covered in lesson 1?"})

    assert response.status_code == 200, (
        f"expected a successful answer but got {response.status_code}: {response.text}"
    )
    assert response.json()["answer"]
