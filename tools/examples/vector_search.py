"""Vector search tool for semantic search over long-term memory."""

from typing import Any, Dict, List, Optional

from tools.tool_manager import BaseTool
from memory.memory_manager import MemoryManager
from config import get_settings


class VectorSearchTool(BaseTool):
    """Tool for semantic search over agent's long-term memory."""

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        default_top_k: int = 5,
    ) -> None:
        """
        Initialize vector search tool.

        Args:
            memory_manager: MemoryManager instance (creates default if None)
            default_top_k: Default number of results to return
        """
        super().__init__(
            name="vector_search",
            description="Search long-term memory using semantic similarity. Finds relevant past conversations, documents, and knowledge.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for semantic search",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return",
                        "default": 5,
                    },
                    "filter_metadata": {
                        "type": "object",
                        "description": "Metadata filters (e.g., session_id, type)",
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Limit search to specific session",
                    },
                },
                "required": ["query"],
            },
            returns={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "content": {"type": "string"},
                                "metadata": {"type": "object"},
                                "score": {"type": "number"},
                            },
                        },
                    },
                    "query": {"type": "string"},
                    "total_results": {"type": "integer"},
                },
            },
            category="memory",
            tags=["search", "vector", "memory", "semantic", "rag"],
            timeout=30,
        )
        self.memory_manager = memory_manager
        self.default_top_k = default_top_k
        self._own_memory_manager = memory_manager is None

    def _get_memory_manager(self) -> MemoryManager:
        """Get or create memory manager."""
        if self.memory_manager:
            return self.memory_manager
        if not hasattr(self, "_created_memory_manager"):
            self.memory_manager = MemoryManager()
            self._created_memory_manager = True
        return self.memory_manager  # type: ignore

    def _execute(self, **kwargs: Any) -> Any:
        """Execute vector search."""
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", self.default_top_k)
        filter_metadata = kwargs.get("filter_metadata")
        session_id = kwargs.get("session_id")

        memory = self._get_memory_manager()

        # Build filter
        if session_id and not filter_metadata:
            filter_metadata = {"session_id": session_id}
        elif session_id and filter_metadata:
            filter_metadata = {**filter_metadata, "session_id": session_id}

        try:
            results = memory.retrieve_long_term(
                query=query,
                top_k=top_k,
                filter_metadata=filter_metadata,
            )

            return {
                "results": results,
                "query": query,
                "total_results": len(results),
            }
        except Exception as e:
            self.logger.error("Vector search failed", error=str(e))
            return {
                "results": [],
                "query": query,
                "total_results": 0,
                "error": str(e),
            }

    async def _aexecute(self, **kwargs: Any) -> Any:
        """Async version - runs in thread pool."""
        import asyncio
        return await asyncio.to_thread(self._execute, **kwargs)