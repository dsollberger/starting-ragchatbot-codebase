"""
Endpoint tests for backend/app.py, exercised through the real FastAPI app (`client` fixture)
with `rag_system` swapped for a mock (`mock_rag_system` fixture, see conftest.py). These hit
real request validation and response serialization, but never the real ChromaDB or Anthropic API.
"""


# --- POST /api/query ---


def test_query_with_session_id_returns_answer_and_sources(client, mock_rag_system):
    response = client.post(
        "/api/query", json={"query": "What is MCP?", "session_id": "existing_session"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "This is a test answer."
    assert body["sources"] == [
        {"text": "Course A - Lesson 1", "link": "https://example.com/lesson1"}
    ]
    assert body["session_id"] == "existing_session"
    mock_rag_system.query.assert_called_once_with("What is MCP?", "existing_session")
    mock_rag_system.session_manager.create_session.assert_not_called()


def test_query_without_session_id_creates_new_session(client, mock_rag_system):
    response = client.post("/api/query", json={"query": "What is MCP?"})

    assert response.status_code == 200
    assert response.json()["session_id"] == "test_session_1"
    mock_rag_system.session_manager.create_session.assert_called_once()
    mock_rag_system.query.assert_called_once_with("What is MCP?", "test_session_1")


def test_query_missing_query_field_returns_422(client):
    response = client.post("/api/query", json={"session_id": "s1"})

    assert response.status_code == 422


def test_query_propagates_rag_system_failure_as_500(client, mock_rag_system):
    mock_rag_system.query.side_effect = RuntimeError("boom")

    response = client.post("/api/query", json={"query": "What is MCP?"})

    assert response.status_code == 500
    assert response.json()["detail"] == "boom"


# --- GET /api/courses ---


def test_get_courses_returns_stats(client, mock_rag_system):
    response = client.get("/api/courses")

    assert response.status_code == 200
    assert response.json() == {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    mock_rag_system.get_course_analytics.assert_called_once()


def test_get_courses_propagates_failure_as_500(client, mock_rag_system):
    mock_rag_system.get_course_analytics.side_effect = RuntimeError("analytics down")

    response = client.get("/api/courses")

    assert response.status_code == 500
    assert response.json()["detail"] == "analytics down"


# --- POST /api/session/new ---


def test_new_session_without_existing_id(client, mock_rag_system):
    response = client.post("/api/session/new", json={})

    assert response.status_code == 200
    assert response.json() == {"session_id": "test_session_1"}
    mock_rag_system.session_manager.clear_session.assert_not_called()
    mock_rag_system.session_manager.create_session.assert_called_once()


def test_new_session_clears_existing_session_when_provided(client, mock_rag_system):
    response = client.post("/api/session/new", json={"session_id": "old_session"})

    assert response.status_code == 200
    mock_rag_system.session_manager.clear_session.assert_called_once_with("old_session")
    mock_rag_system.session_manager.create_session.assert_called_once()


# --- GET / (static frontend) ---


def test_root_serves_frontend_index(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
