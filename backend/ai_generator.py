import anthropic
from typing import List, Optional, Dict, Any

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Search Tool Usage (search_course_content):
- Use this tool for questions about specific course content or detailed educational materials (what a lesson covers, explanations, examples within a lesson)
- You may call this tool more than once for a single question when it genuinely requires separate lookups — for example, comparing content across two different courses or lessons, or answering a multi-part question
- Don't repeat an identical search that already returned results; if a search comes back empty, either try a meaningfully different query/filter or move on to answering with what you have

Course Outline Tool Usage (get_course_outline):
- Use this tool for questions about a course's structure, syllabus, outline, or lesson list (e.g. "what lessons are in the MCP course", "show me the outline for X", "how many lessons does Y have")
- Do NOT use this tool for questions about the content within a specific lesson — use search_course_content for that instead
- When you use this tool, your answer must include: the course title, the course link, and the complete lesson list (lesson number and lesson title for every lesson returned by the tool)
- You can chain tools: look up the outline first to find the right lesson number or title, then call search_course_content to get the content within it

Multi-step tool use:
- You have up to two sequential rounds of tool calls available before you must give your final answer. After seeing the results of a first tool call, you may make one more round of tool call(s) if needed, then you must answer
- Use the second round only when the first round's results are genuinely insufficient — e.g. the question spans multiple courses/lessons, needs an outline lookup before a targeted search, or has multiple distinct parts
- Once you've gathered what you need (or reached the two-round limit), answer directly — do not ask permission to search further and do not narrate your search process

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course content questions**: Use search_course_content, then answer
- **Course structure/outline questions**: Use get_course_outline first, then answer, including title/link/full lesson list as noted above
- **Comparisons or multi-part questions**: Use tools once per distinct course/lesson/topic involved (up to the two-round limit), then synthesize one combined answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results" or "based on the tool output"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response, allowing Claude up to MAX_TOOL_ROUNDS sequential rounds
        of tool calls before it must give a final answer.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages: List[Dict[str, Any]] = [{"role": "user", "content": query}]
        can_use_tools = bool(tools and tool_manager)

        for _ in range(self.MAX_TOOL_ROUNDS):
            api_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content
            }
            if can_use_tools:
                api_params["tools"] = tools
                api_params["tool_choice"] = {"type": "auto"}

            response = self.client.messages.create(**api_params)

            tool_use_blocks = [
                block for block in response.content
                if getattr(block, "type", None) == "tool_use"
            ]
            if not tool_use_blocks:
                return self._extract_text(response)

            messages.append({"role": "assistant", "content": response.content})
            tool_results, had_error = self._execute_tool_round(tool_use_blocks, tool_manager)
            messages.append({"role": "user", "content": tool_results})

            if had_error:
                break

        # Either the round budget is exhausted or a tool call failed -- either way,
        # Claude has unanswered tool_results in its context. Make one final call
        # without tools so it must produce a text answer instead of requesting more.
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content
        }
        final_response = self.client.messages.create(**final_params)
        return self._extract_text(final_response)

    def _extract_text(self, response) -> str:
        """Return the first text block's content, or '' if there is none"""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""

    def _execute_tool_round(self, tool_use_blocks, tool_manager):
        """
        Execute every tool_use block from a single round, returning a tool_result
        for each (required by the API even on failure) plus whether any failed.

        Args:
            tool_use_blocks: The tool_use content blocks from one Claude response
            tool_manager: Manager to execute tools

        Returns:
            Tuple of (list of tool_result dicts, whether any tool call raised)
        """
        results = []
        had_error = False
        for block in tool_use_blocks:
            try:
                output = tool_manager.execute_tool(block.name, **block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output
                })
            except Exception as exc:
                had_error = True
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Tool execution failed: {exc}",
                    "is_error": True
                })
        return results, had_error
