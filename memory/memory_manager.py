"""Memory manager for short-term and long-term memory."""

import json
from typing import Any, Dict, List, Optional

import redis
import tiktoken

from config import get_settings
from memory.vector_store import VectorStore
from observability.logger import LoggerMixin, get_logger

logger = get_logger(__name__)


class MemoryManager(LoggerMixin):
    """
    Manages agent memory with short-term (Redis) and long-term (vector DB) storage.

    Short-term memory: Session-specific data, conversation history
    Long-term memory: Semantic search over historical interactions
    """

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        vector_store: Optional[VectorStore] = None,
        max_context_tokens: int = 8000,
    ):
        """
        Initialize memory manager.

        Args:
            redis_client: Redis client for short-term memory
            vector_store: Vector store for long-term memory
            max_context_tokens: Maximum tokens for context window
        """
        self.settings = get_settings()
        self.max_context_tokens = max_context_tokens

        # Initialize short-term memory (Redis)
        if redis_client:
            self.redis = redis_client
        else:
            try:
                self.redis = redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                )
                self.logger.info("Redis connected for short-term memory")
            except Exception as e:
                self.logger.warning(f"Redis connection failed: {e}. Using in-memory fallback.")
                self.redis = None
                self._memory_fallback: Dict[str, Dict[str, Any]] = {}

        # Initialize long-term memory (Vector DB)
        self.vector_store = vector_store or VectorStore()

        # Initialize tokenizer for context management
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.logger.warning("Tiktoken not available, using approximate token counting")
            self.tokenizer = None

    def _get_session_key(self, session_id: str, key: str) -> str:
        """Generate Redis key for session data."""
        return f"session:{session_id}:{key}"

    def store_short_term(
        self, session_id: str, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """
        Store data in short-term memory.

        Args:
            session_id: Session identifier
            key: Data key
            value: Data value (will be JSON serialized)
            ttl: Time to live in seconds (optional)
        """
        redis_key = self._get_session_key(session_id, key)
        serialized_value = json.dumps(value)

        if self.redis:
            try:
                self.redis.set(redis_key, serialized_value, ex=ttl)
                self.logger.debug("Stored in short-term memory", session_id=session_id, key=key)
            except Exception as e:
                self.logger.error("Failed to store in Redis", error=str(e))
                # Fallback to in-memory
                if session_id not in self._memory_fallback:
                    self._memory_fallback[session_id] = {}
                self._memory_fallback[session_id][key] = value
        else:
            # Use in-memory fallback
            if session_id not in self._memory_fallback:
                self._memory_fallback[session_id] = {}
            self._memory_fallback[session_id][key] = value

    def retrieve_short_term(self, session_id: str, key: str) -> Optional[Any]:
        """
        Retrieve data from short-term memory.

        Args:
            session_id: Session identifier
            key: Data key

        Returns:
            Stored value or None if not found
        """
        redis_key = self._get_session_key(session_id, key)

        if self.redis:
            try:
                value = self.redis.get(redis_key)
                if value:
                    return json.loads(value)
            except Exception as e:
                self.logger.error("Failed to retrieve from Redis", error=str(e))

        # Try fallback
        if hasattr(self, "_memory_fallback"):
            return self._memory_fallback.get(session_id, {}).get(key)

        return None

    def delete_short_term(self, session_id: str, key: str) -> None:
        """
        Delete data from short-term memory.

        Args:
            session_id: Session identifier
            key: Data key
        """
        redis_key = self._get_session_key(session_id, key)

        if self.redis:
            try:
                self.redis.delete(redis_key)
            except Exception as e:
                self.logger.error("Failed to delete from Redis", error=str(e))

        # Also delete from fallback
        if hasattr(self, "_memory_fallback") and session_id in self._memory_fallback:
            self._memory_fallback[session_id].pop(key, None)

    def store_long_term(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store data in long-term memory with semantic indexing.

        Args:
            session_id: Session identifier
            content: Content to store
            metadata: Optional metadata

        Returns:
            Document ID
        """
        metadata = metadata or {}
        metadata["session_id"] = session_id

        doc_id = self.vector_store.add_document(content, metadata)
        self.logger.debug("Stored in long-term memory", session_id=session_id, doc_id=doc_id)

        return doc_id

    def retrieve_long_term(
        self, query: str, top_k: int = 5, filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant data from long-term memory.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters

        Returns:
            List of relevant documents with scores
        """
        results = self.vector_store.search(query, top_k=top_k, filter_metadata=filter_metadata)
        self.logger.debug("Retrieved from long-term memory", query=query, results_count=len(results))

        return results

    def add_to_conversation_history(
        self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add message to conversation history.

        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
        """
        history_key = "conversation_history"
        history = self.retrieve_short_term(session_id, history_key) or []

        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": str(tiktoken.get_encoding("cl100k_base")),  # Placeholder
        }

        history.append(message)

        # Prune history if it exceeds token limit
        history = self._prune_conversation_history(history)

        self.store_short_term(session_id, history_key, history)

    def get_conversation_history(
        self, session_id: str, max_messages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session.

        Args:
            session_id: Session identifier
            max_messages: Maximum number of messages to return

        Returns:
            List of conversation messages
        """
        history = self.retrieve_short_term(session_id, "conversation_history") or []

        if max_messages:
            history = history[-max_messages:]

        return history

    def _prune_conversation_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prune conversation history to fit within token limit.

        Args:
            history: Conversation history

        Returns:
            Pruned history
        """
        if not self.tokenizer:
            # Simple pruning: keep last 20 messages
            return history[-20:]

        total_tokens = 0
        pruned_history = []

        # Iterate from most recent to oldest
        for message in reversed(history):
            content = message.get("content", "")
            tokens = len(self.tokenizer.encode(content))

            if total_tokens + tokens > self.max_context_tokens:
                break

            pruned_history.insert(0, message)
            total_tokens += tokens

        return pruned_history

    def summarize_and_store(self, session_id: str) -> None:
        """
        Summarize conversation history and store in long-term memory.

        Args:
            session_id: Session identifier
        """
        history = self.get_conversation_history(session_id)

        if not history:
            return

        # Create summary (in production, use LLM for summarization)
        summary = f"Conversation with {len(history)} messages"

        # Store in long-term memory
        self.store_long_term(
            session_id=session_id,
            content=summary,
            metadata={"type": "conversation_summary", "message_count": len(history)},
        )

        self.logger.info("Conversation summarized and stored", session_id=session_id)

    def clear_session(self, session_id: str) -> None:
        """
        Clear all short-term memory for a session.

        Args:
            session_id: Session identifier
        """
        if self.redis:
            try:
                pattern = self._get_session_key(session_id, "*")
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
            except Exception as e:
                self.logger.error("Failed to clear session from Redis", error=str(e))

        # Clear fallback
        if hasattr(self, "_memory_fallback") and session_id in self._memory_fallback:
            del self._memory_fallback[session_id]

        self.logger.info("Session cleared", session_id=session_id)

