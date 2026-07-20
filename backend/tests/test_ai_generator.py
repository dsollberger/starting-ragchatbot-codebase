import pytest

from ai_generator import AIGenerator
from config import config


@pytest.fixture
def generator(mock_anthropic_client):
    gen = AIGenerator(api_key="test-key", model="claude-test-model")
    gen.client = mock_anthropic_client  # ensure the instance uses the patched client
    return gen


def test_generate_response_no_tool_use_returns_text(generator, mock_anthropic_client, anthropic_response_factory):
    mock_anthropic_client.messages.create.return_value = anthropic_response_factory(
        text="a direct answer", stop_reason="end_turn"
    )

    result = generator.generate_response("what is 2+2?")

    assert result == "a direct answer"
    mock_anthropic_client.messages.create.assert_called_once()


def test_generate_response_no_tools_manager_never_called(generator, mock_anthropic_client, anthropic_response_factory, mocker):
    mock_anthropic_client.messages.create.return_value = anthropic_response_factory(
        text="a direct answer", stop_reason="end_turn"
    )
    tool_manager = mocker.MagicMock()

    generator.generate_response("what is 2+2?", tool_manager=tool_manager)

    tool_manager.execute_tool.assert_not_called()


def test_generate_response_invokes_correct_tool(generator, mock_anthropic_client, anthropic_response_factory, mocker):
    tool_use_response = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "MCP basics"}}],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="final answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [tool_use_response, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.return_value = "tool result text"

    result = generator.generate_response(
        "what does MCP cover?", tools=[{"name": "search_course_content"}], tool_manager=tool_manager
    )

    tool_manager.execute_tool.assert_called_once_with("search_course_content", query="MCP basics")
    assert result == "final answer"


def test_generate_response_round_two_still_offers_tools(generator, mock_anthropic_client, anthropic_response_factory, mocker):
    """Round 2 is a legitimate second tool-calling round, so tools must still be offered."""
    tool_use_response = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}}],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="final answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [tool_use_response, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.return_value = "tool result text"

    generator.generate_response("q", tools=[{"name": "search_course_content"}], tool_manager=tool_manager)

    second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    assert "tools" in second_call_kwargs
    assert second_call_kwargs["tool_choice"] == {"type": "auto"}


def test_generate_response_builds_correct_message_structure(generator, mock_anthropic_client, anthropic_response_factory, mocker):
    tool_use_response = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}}],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="final answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [tool_use_response, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.return_value = "tool result text"

    generator.generate_response("original query", tools=[{"name": "search_course_content"}], tool_manager=tool_manager)

    second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    messages = second_call_kwargs["messages"]

    assert messages[0] == {"role": "user", "content": "original query"}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == tool_use_response.content
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "tool result text"}
    ]


def test_generate_response_returns_final_text_after_tool_use(generator, mock_anthropic_client, anthropic_response_factory, mocker):
    tool_use_response = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}}],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="the real final answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [tool_use_response, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.return_value = "tool result text"

    result = generator.generate_response("q", tools=[{"name": "search_course_content"}], tool_manager=tool_manager)

    assert result == "the real final answer"


def test_generate_response_two_full_tool_rounds(generator, mock_anthropic_client, anthropic_response_factory, mocker):
    round1 = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "MCP basics"}}],
        stop_reason="tool_use",
    )
    round2 = anthropic_response_factory(
        tool_calls=[{"id": "toolu_2", "name": "get_course_outline", "input": {"course_name": "MCP"}}],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="combined answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [round1, round2, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.side_effect = ["search result", "outline result"]

    result = generator.generate_response(
        "compare topics", tools=[{"name": "search_course_content"}, {"name": "get_course_outline"}], tool_manager=tool_manager
    )

    assert mock_anthropic_client.messages.create.call_count == 3
    tool_manager.execute_tool.assert_has_calls([
        mocker.call("search_course_content", query="MCP basics"),
        mocker.call("get_course_outline", course_name="MCP"),
    ])
    assert result == "combined answer"


def test_generate_response_stops_after_max_rounds_third_tool_request_ignored(
    generator, mock_anthropic_client, anthropic_response_factory, mocker
):
    round1 = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}}],
        stop_reason="tool_use",
    )
    round2 = anthropic_response_factory(
        tool_calls=[{"id": "toolu_2", "name": "search_course_content", "input": {"query": "y"}}],
        stop_reason="tool_use",
    )
    # No tools are offered on the 3rd call, so Claude cannot request tool_use again -- it answers.
    final_response = anthropic_response_factory(text="final answer despite wanting more", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [round1, round2, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.side_effect = ["result 1", "result 2"]

    result = generator.generate_response(
        "q", tools=[{"name": "search_course_content"}], tool_manager=tool_manager
    )

    assert mock_anthropic_client.messages.create.call_count == 3
    third_call_kwargs = mock_anthropic_client.messages.create.call_args_list[2].kwargs
    assert "tools" not in third_call_kwargs
    assert tool_manager.execute_tool.call_count == 2
    assert result == "final answer despite wanting more"


def test_generate_response_terminates_early_when_no_tool_use_in_round_two(
    generator, mock_anthropic_client, anthropic_response_factory, mocker
):
    round1 = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}}],
        stop_reason="tool_use",
    )
    round2 = anthropic_response_factory(text="round 2 final answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [round1, round2]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.return_value = "result 1"

    result = generator.generate_response(
        "q", tools=[{"name": "search_course_content"}], tool_manager=tool_manager
    )

    assert mock_anthropic_client.messages.create.call_count == 2
    tool_manager.execute_tool.assert_called_once()
    assert result == "round 2 final answer"


def test_generate_response_tool_execution_exception_handled_gracefully(
    generator, mock_anthropic_client, anthropic_response_factory, mocker
):
    round1 = anthropic_response_factory(
        tool_calls=[{"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}}],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="I couldn't retrieve that information.", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [round1, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.side_effect = RuntimeError("boom")

    result = generator.generate_response(
        "q", tools=[{"name": "search_course_content"}], tool_manager=tool_manager
    )

    assert mock_anthropic_client.messages.create.call_count == 2
    second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    assert "tools" not in second_call_kwargs
    tool_result = second_call_kwargs["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert "boom" in tool_result["content"]
    assert result == "I couldn't retrieve that information."


def test_generate_response_partial_tool_failure_in_same_round_still_gets_all_results(
    generator, mock_anthropic_client, anthropic_response_factory, mocker
):
    round1 = anthropic_response_factory(
        tool_calls=[
            {"id": "toolu_1", "name": "search_course_content", "input": {"query": "x"}},
            {"id": "toolu_2", "name": "get_course_outline", "input": {"course_name": "y"}},
        ],
        stop_reason="tool_use",
    )
    final_response = anthropic_response_factory(text="final answer", stop_reason="end_turn")
    mock_anthropic_client.messages.create.side_effect = [round1, final_response]

    tool_manager = mocker.MagicMock()
    tool_manager.execute_tool.side_effect = ["ok result", Exception("bad")]

    result = generator.generate_response(
        "q", tools=[{"name": "search_course_content"}, {"name": "get_course_outline"}], tool_manager=tool_manager
    )

    assert mock_anthropic_client.messages.create.call_count == 2
    second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    tool_results = second_call_kwargs["messages"][-1]["content"]
    assert len(tool_results) == 2
    assert tool_results[0] == {"type": "tool_result", "tool_use_id": "toolu_1", "content": "ok result"}
    assert tool_results[1]["tool_use_id"] == "toolu_2"
    assert tool_results[1]["is_error"] is True
    assert result == "final answer"


def test_generate_response_empty_content_block_returns_empty_string_not_crash(
    generator, mock_anthropic_client, anthropic_response_factory
):
    empty_response = anthropic_response_factory(stop_reason="end_turn")

    result = generator.generate_response("q")

    assert result == ""


@pytest.mark.skipif(bool(config.ANTHROPIC_API_KEY), reason="a real key is configured; this diagnostic only applies when the key is empty")
def test_real_client_empty_api_key_raises():
    """
    Not mocked: reproduces the production root cause at the exact call site.
    No network call occurs -- anthropic's SDK raises this TypeError while building
    request headers, before any HTTP request is sent.
    """
    real_generator = AIGenerator(api_key=config.ANTHROPIC_API_KEY, model=config.ANTHROPIC_MODEL)

    with pytest.raises(TypeError, match="Could not resolve authentication method"):
        real_generator.generate_response("what is covered in lesson 1?")
