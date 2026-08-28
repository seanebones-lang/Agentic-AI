"""Tool manager with registry, semantic search, and execution management."""

import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from observability.logger import LoggerMixin, get_logger
from observability.metrics import get_metrics_collector

logger = get_logger(__name__)


class ToolExecutionError(Exception):
    """Exception raised when tool execution fails."""

    pass


class ToolSchema(BaseModel):
    """Schema for tool definition."""

    name: str = Field(..., description="Unique tool name")
    description: str = Field(..., description="Description of what the tool does")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for tool parameters"
    )
    returns: Dict[str, Any] = Field(
        default_factory=dict, description="JSON schema for return value"
    )
    category: str = Field(default="general", description="Tool category")
    tags: List[str] = Field(default_factory=list, description="Tags for semantic search")


class BaseTool(ABC, LoggerMixin):
    """
    Base class for all tools.

    Tools are functions that agents can use to interact with external systems.
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        returns: Optional[Dict[str, Any]] = None,
        category: str = "general",
        tags: Optional[List[str]] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize base tool.

        Args:
            name: Unique tool name
            description: Tool description
            parameters: JSON schema for parameters
            returns: JSON schema for return value
            category: Tool category
            tags: Tags for semantic search
            timeout: Execution timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.schema = ToolSchema(
            name=name,
            description=description,
            parameters=parameters or {},
            returns=returns or {},
            category=category,
            tags=tags or [],
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.metrics = get_metrics_collector()

    @abstractmethod
    def _execute(self, **kwargs: Any) -> Any:
        """
        Execute the tool logic.

        This method should be implemented by subclasses.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def execute(self, **kwargs: Any) -> Any:
        """
        Execute the tool with error handling and retries.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result

        Raises:
            ToolExecutionError: If execution fails after retries
        """
        start_time = time.time()
        self.logger.info("Executing tool", tool=self.schema.name, parameters=kwargs)

        try:
            result = self._execute(**kwargs)
            duration = time.time() - start_time

            self.metrics.record_tool_usage(
                tool_name=self.schema.name,
                success=True,
                duration_seconds=duration,
            )

            self.logger.info(
                "Tool execution successful",
                tool=self.schema.name,
                duration_seconds=duration,
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                "Tool execution failed",
                tool=self.schema.name,
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=duration,
            )

            self.metrics.record_tool_usage(
                tool_name=self.schema.name,
                success=False,
                duration_seconds=duration,
            )

            self.metrics.record_error(
                error_type=type(e).__name__,
                component=f"Tool_{self.schema.name}",
            )

            raise ToolExecutionError(f"Tool {self.schema.name} failed: {str(e)}") from e

    async def aexecute(self, **kwargs: Any) -> Any:
        """
        Async execution of the tool.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool execution result
        """
        start_time = time.time()
        self.logger.info("Executing tool (async)", tool=self.schema.name, parameters=kwargs)

        try:
            # If the tool has an async implementation, use it
            if hasattr(self, "_aexecute"):
                result = await self._aexecute(**kwargs)
            else:
                # Fall back to sync execution
                result = self._execute(**kwargs)

            duration = time.time() - start_time
            self.metrics.record_tool_usage(
                tool_name=self.schema.name,
                success=True,
                duration_seconds=duration,
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error("Tool execution failed (async)", tool=self.schema.name, error=str(e))
            self.metrics.record_tool_usage(
                tool_name=self.schema.name,
                success=False,
                duration_seconds=duration,
            )
            raise ToolExecutionError(f"Tool {self.schema.name} failed: {str(e)}") from e


class ToolManager(LoggerMixin):
    """
    Manages tool registry, discovery, and execution.

    Provides semantic search for tool discovery using embeddings.
    """

    def __init__(self, enable_semantic_search: bool = True):
        """
        Initialize tool manager.

        Args:
            enable_semantic_search: Whether to enable semantic search for tools
        """
        self.tools: Dict[str, BaseTool] = {}
        self.enable_semantic_search = enable_semantic_search
        self.vector_store: Optional[Any] = None

        if enable_semantic_search:
            try:
                import chromadb

                self.chroma_client = chromadb.Client()
                self.vector_store = self.chroma_client.get_or_create_collection("tools")
                self.logger.info("Semantic search enabled for tools")
            except ImportError:
                self.logger.warning(
                    "ChromaDB not available, semantic search disabled. Install with: pip install chromadb"
                )
                self.enable_semantic_search = False

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool in the manager.

        Args:
            tool: Tool instance to register
        """
        if tool.schema.name in self.tools:
            self.logger.warning("Tool already registered, overwriting", tool=tool.schema.name)

        self.tools[tool.schema.name] = tool

        # Add to vector store for semantic search
        if self.enable_semantic_search and self.vector_store:
            try:
                # Create searchable text from tool metadata
                searchable_text = (
                    f"{tool.schema.name} {tool.schema.description} "
                    f"{tool.schema.category} {' '.join(tool.schema.tags)}"
                )

                # Use a unique ID that includes a hash to prevent collisions
                tool_id = f"{tool.schema.name}_{hash(searchable_text)}"

                self.vector_store.add(
                    documents=[searchable_text],
                    ids=[tool_id],
                    metadatas=[{"category": tool.schema.category, "tags": tool.schema.tags, "name": tool.schema.name}],
                )
            except Exception as e:
                self.logger.error("Failed to add tool to vector store", error=str(e))

        self.logger.info("Tool registered", tool=tool.schema.name, category=tool.schema.category)

    def unregister_tool(self, tool_name: str) -> None:
        """
        Unregister a tool from the manager.

        Args:
            tool_name: Name of the tool to unregister
        """
        if tool_name in self.tools:
            del self.tools[tool_name]

            if self.enable_semantic_search and self.vector_store:
                try:
                    self.vector_store.delete(ids=[tool_name])
                except Exception as e:
                    self.logger.error("Failed to remove tool from vector store", error=str(e))

            self.logger.info("Tool unregistered", tool=tool_name)

    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(tool_name)

    def list_tools(self, category: Optional[str] = None) -> List[ToolSchema]:
        """
        List all registered tools.

        Args:
            category: Optional category filter

        Returns:
            List of tool schemas
        """
        tools = self.tools.values()
        if category:
            tools = [t for t in tools if t.schema.category == category]
        return [tool.schema for tool in tools]

    def discover_tools(self, query: str, top_k: int = 3) -> List[str]:
        """
        Discover tools using semantic search.

        Args:
            query: Search query describing the desired functionality
            top_k: Number of tools to return

        Returns:
            List of tool names ranked by relevance
        """
        if not self.enable_semantic_search or not self.vector_store:
            self.logger.warning("Semantic search not available, returning all tools")
            return list(self.tools.keys())[:top_k]

        try:
            results = self.vector_store.query(query_texts=[query], n_results=top_k)

            if results and results.get("ids"):
                tool_names = results["ids"][0]
                self.logger.info("Tools discovered", query=query, tools=tool_names)
                return tool_names

            return []

        except Exception as e:
            self.logger.error("Tool discovery failed", error=str(e))
            return []

    def execute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ToolExecutionError: If tool not found or execution fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ToolExecutionError(f"Tool not found: {tool_name}")

        return tool.execute(**kwargs)

    async def aexecute_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Execute a tool asynchronously by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ToolExecutionError(f"Tool not found: {tool_name}")

        return await tool.aexecute(**kwargs)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        Get JSON schemas for all tools (useful for LLM function calling).

        Returns:
            List of tool schemas in OpenAI function format
        """
        schemas = []
        for tool in self.tools.values():
            schema = {
                "name": tool.schema.name,
                "description": tool.schema.description,
                "parameters": tool.schema.parameters,
            }
            schemas.append(schema)
        return schemas

