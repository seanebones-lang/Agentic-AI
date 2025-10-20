"""Unit tests for tool system."""

import pytest

from tools.tool_manager import ToolManager, BaseTool, ToolExecutionError


class MockTool(BaseTool):
    """Mock tool for testing."""

    def __init__(self) -> None:
        super().__init__(
            name="mock_tool",
            description="A mock tool for testing",
            category="test",
        )

    def _execute(self, **kwargs: any) -> dict:
        """Execute mock tool."""
        return {"status": "success", "input": kwargs}


class FailingTool(BaseTool):
    """Tool that always fails."""

    def __init__(self) -> None:
        super().__init__(
            name="failing_tool",
            description="A tool that fails",
            category="test",
        )

    def _execute(self, **kwargs: any) -> dict:
        """Execute and fail."""
        raise ValueError("Tool execution failed")


class TestToolManager:
    """Test ToolManager."""

    def test_tool_registration(self) -> None:
        """Test registering tools."""
        manager = ToolManager(enable_semantic_search=False)
        tool = MockTool()

        manager.register_tool(tool)

        assert "mock_tool" in manager.tools
        assert manager.get_tool("mock_tool") == tool

    def test_tool_execution(self) -> None:
        """Test executing tools."""
        manager = ToolManager(enable_semantic_search=False)
        tool = MockTool()
        manager.register_tool(tool)

        result = manager.execute_tool("mock_tool", test_param="value")

        assert result["status"] == "success"
        assert result["input"]["test_param"] == "value"

    def test_tool_not_found(self) -> None:
        """Test executing non-existent tool."""
        manager = ToolManager(enable_semantic_search=False)

        with pytest.raises(ToolExecutionError):
            manager.execute_tool("nonexistent_tool")

    def test_tool_failure_handling(self) -> None:
        """Test tool failure handling."""
        manager = ToolManager(enable_semantic_search=False)
        tool = FailingTool()
        manager.register_tool(tool)

        with pytest.raises(ToolExecutionError):
            manager.execute_tool("failing_tool")

    def test_list_tools(self) -> None:
        """Test listing tools."""
        manager = ToolManager(enable_semantic_search=False)
        tool1 = MockTool()
        manager.register_tool(tool1)

        tools = manager.list_tools()

        assert len(tools) == 1
        assert tools[0].name == "mock_tool"

    def test_tool_schemas(self) -> None:
        """Test getting tool schemas."""
        manager = ToolManager(enable_semantic_search=False)
        tool = MockTool()
        manager.register_tool(tool)

        schemas = manager.get_tool_schemas()

        assert len(schemas) == 1
        assert schemas[0]["name"] == "mock_tool"
        assert "description" in schemas[0]


class TestBaseTool:
    """Test BaseTool."""

    def test_tool_execution(self) -> None:
        """Test tool execution."""
        tool = MockTool()

        result = tool.execute(test_param="value")

        assert result["status"] == "success"

    def test_tool_schema(self) -> None:
        """Test tool schema."""
        tool = MockTool()

        assert tool.schema.name == "mock_tool"
        assert tool.schema.description == "A mock tool for testing"
        assert tool.schema.category == "test"

