from search_tools import CourseSearchTool
from vector_store import SearchResults


# --- Real vector store: proves the retrieval layer itself is healthy ---


def test_search_real_data_returns_relevant_content(real_vector_store):
    tool = CourseSearchTool(real_vector_store)
    result = tool.execute(query="what is MCP")

    assert result
    assert "No relevant content found" not in result
    assert "[" in result and "]" in result  # course/lesson header


def test_search_real_data_with_course_name_filter(real_vector_store):
    titles = real_vector_store.get_existing_course_titles()
    assert titles, "expected at least one ingested course in backend/chroma_db"

    partial_name = titles[0].split(":")[0].split(" ")[0]  # a short fragment of a real title
    tool = CourseSearchTool(real_vector_store)
    result = tool.execute(query="overview", course_name=partial_name)

    assert "No course found matching" not in result


def test_search_real_data_invalid_course_name(real_vector_store):
    tool = CourseSearchTool(real_vector_store)
    result = tool.execute(query="anything", course_name="Nonexistent Course Zzzqqq123")

    assert "No course found matching" in result


# --- Mocked vector store: deterministic edge cases ---


def test_search_mock_empty_results_message(mock_vector_store):
    mock_vector_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
    tool = CourseSearchTool(mock_vector_store)

    result = tool.execute(query="anything")

    assert "No relevant content found" in result


def test_search_mock_error_passthrough(mock_vector_store):
    mock_vector_store.search.return_value = SearchResults.empty("Search error: boom")
    tool = CourseSearchTool(mock_vector_store)

    result = tool.execute(query="anything")

    assert result == "Search error: boom"


def test_search_mock_tracks_last_sources(mock_vector_store):
    mock_vector_store.search.return_value = SearchResults(
        documents=["some lesson content"],
        metadata=[{"course_title": "Course A", "lesson_number": 2}],
        distances=[0.1],
    )
    mock_vector_store.get_lesson_link.return_value = "https://example.com/lesson2"
    tool = CourseSearchTool(mock_vector_store)

    tool.execute(query="anything")

    assert tool.last_sources == [{"text": "Course A - Lesson 2", "link": "https://example.com/lesson2"}]
    mock_vector_store.get_lesson_link.assert_called_once_with("Course A", 2)


def test_search_mock_formats_multiple_results(mock_vector_store):
    mock_vector_store.search.return_value = SearchResults(
        documents=["doc one", "doc two"],
        metadata=[
            {"course_title": "Course A", "lesson_number": 1},
            {"course_title": "Course B", "lesson_number": None},
        ],
        distances=[0.1, 0.2],
    )
    mock_vector_store.get_lesson_link.return_value = "link1"
    mock_vector_store.get_course_link.return_value = "link2"
    tool = CourseSearchTool(mock_vector_store)

    result = tool.execute(query="anything")

    assert "[Course A - Lesson 1]\ndoc one" in result
    assert "[Course B]\ndoc two" in result
    assert "\n\n" in result
