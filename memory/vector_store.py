"""Vector store for semantic search and long-term memory."""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from config import get_settings
from observability.logger import LoggerMixin, get_logger

logger = get_logger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""

    OPENAI = "openai"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"


class VectorStore(LoggerMixin):
    """
    Vector store for semantic search using configurable backends.

    Supports: Chroma, Pinecone, FAISS
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        """
        Initialize vector store.

        Args:
            embedding_provider: Embedding provider to use
        """
        self.settings = get_settings()
        self.embedding_provider = embedding_provider or EmbeddingProvider.OPENAI
        self.embeddings = self._initialize_embeddings()
        self.vector_db = self._initialize_vector_db()

    def _initialize_embeddings(self) -> Any:
        """Initialize embedding model based on provider."""
        try:
            if self.embedding_provider == EmbeddingProvider.OPENAI:
                from langchain_openai import OpenAIEmbeddings

                embeddings = OpenAIEmbeddings(
                    openai_api_key=self.settings.openai_api_key,
                    model="text-embedding-3-small",
                )
                self.logger.info("OpenAI embeddings initialized")
                return embeddings

            elif self.embedding_provider == EmbeddingProvider.COHERE:
                from langchain_community.embeddings import CohereEmbeddings

                embeddings = CohereEmbeddings()
                self.logger.info("Cohere embeddings initialized")
                return embeddings

            elif self.embedding_provider == EmbeddingProvider.HUGGINGFACE:
                from langchain_community.embeddings import HuggingFaceEmbeddings

                embeddings = HuggingFaceEmbeddings()
                self.logger.info("HuggingFace embeddings initialized")
                return embeddings

        except ImportError as e:
            self.logger.error(f"Failed to import embedding provider: {e}")
            raise

    def _initialize_vector_db(self) -> Any:
        """Initialize vector database based on configuration."""
        provider = self.settings.vector_db_provider

        try:
            if provider == "chroma":
                return self._initialize_chroma()
            elif provider == "pinecone":
                return self._initialize_pinecone()
            elif provider == "faiss":
                return self._initialize_faiss()
            else:
                raise ValueError(f"Unsupported vector DB provider: {provider}")

        except Exception as e:
            self.logger.error(f"Failed to initialize vector DB: {e}")
            raise

    def _initialize_chroma(self) -> Any:
        """Initialize ChromaDB."""
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.HttpClient(
            host=self.settings.chroma_host,
            port=self.settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        collection = client.get_or_create_collection(
            name="agent_memory",
            metadata={"description": "Long-term memory for agents"},
        )

        self.logger.info("ChromaDB initialized", host=self.settings.chroma_host)
        return collection

    def _initialize_pinecone(self) -> Any:
        """Initialize Pinecone."""
        from pinecone import Pinecone

        if not self.settings.pinecone_api_key:
            raise ValueError("Pinecone API key not configured")

        pc = Pinecone(api_key=self.settings.pinecone_api_key)

        # Get or create index
        index_name = "agent-memory"
        if index_name not in pc.list_indexes().names():
            pc.create_index(
                name=index_name,
                dimension=1536,  # OpenAI embedding dimension
                metric="cosine",
            )

        index = pc.Index(index_name)
        self.logger.info("Pinecone initialized", index=index_name)
        return index

    def _initialize_faiss(self) -> Any:
        """Initialize FAISS."""
        import faiss
        import numpy as np

        # Create FAISS index (in-memory)
        dimension = 1536  # OpenAI embedding dimension
        index = faiss.IndexFlatL2(dimension)

        self.logger.info("FAISS initialized", dimension=dimension)

        # Store documents separately for FAISS (it only stores vectors)
        self._faiss_documents: Dict[int, Dict[str, Any]] = {}

        return index

    def add_document(
        self, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Add document to vector store.

        Args:
            content: Document content
            metadata: Optional metadata

        Returns:
            Document ID
        """
        doc_id = str(uuid4())
        metadata = metadata or {}
        metadata["doc_id"] = doc_id

        try:
            # Generate embedding
            embedding = self.embeddings.embed_query(content)

            # Store based on provider
            if self.settings.vector_db_provider == "chroma":
                self.vector_db.add(
                    ids=[doc_id],
                    documents=[content],
                    metadatas=[metadata],
                    embeddings=[embedding],
                )

            elif self.settings.vector_db_provider == "pinecone":
                self.vector_db.upsert(
                    vectors=[(doc_id, embedding, metadata)],
                )

            elif self.settings.vector_db_provider == "faiss":
                import numpy as np

                # Add to FAISS index
                vector = np.array([embedding], dtype=np.float32)
                idx = self.vector_db.ntotal
                self.vector_db.add(vector)

                # Store document metadata
                self._faiss_documents[idx] = {
                    "id": doc_id,
                    "content": content,
                    "metadata": metadata,
                }

            self.logger.debug("Document added to vector store", doc_id=doc_id)
            return doc_id

        except Exception as e:
            self.logger.error("Failed to add document to vector store", error=str(e))
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters

        Returns:
            List of results with content, metadata, and scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embeddings.embed_query(query)

            # Search based on provider
            if self.settings.vector_db_provider == "chroma":
                results = self.vector_db.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    where=filter_metadata,
                )

                return [
                    {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "score": results["distances"][0][i],
                    }
                    for i in range(len(results["ids"][0]))
                ]

            elif self.settings.vector_db_provider == "pinecone":
                results = self.vector_db.query(
                    vector=query_embedding,
                    top_k=top_k,
                    filter=filter_metadata,
                    include_metadata=True,
                )

                return [
                    {
                        "id": match.id,
                        "content": match.metadata.get("content", ""),
                        "metadata": match.metadata,
                        "score": match.score,
                    }
                    for match in results.matches
                ]

            elif self.settings.vector_db_provider == "faiss":
                import numpy as np

                # Search FAISS index
                query_vector = np.array([query_embedding], dtype=np.float32)
                distances, indices = self.vector_db.search(query_vector, top_k)

                results = []
                for i, idx in enumerate(indices[0]):
                    if idx in self._faiss_documents:
                        doc = self._faiss_documents[idx]
                        results.append(
                            {
                                "id": doc["id"],
                                "content": doc["content"],
                                "metadata": doc["metadata"],
                                "score": float(distances[0][i]),
                            }
                        )

                return results

            return []

        except Exception as e:
            self.logger.error("Failed to search vector store", error=str(e))
            return []

    def delete_document(self, doc_id: str) -> None:
        """
        Delete document from vector store.

        Args:
            doc_id: Document ID to delete
        """
        try:
            if self.settings.vector_db_provider == "chroma":
                self.vector_db.delete(ids=[doc_id])

            elif self.settings.vector_db_provider == "pinecone":
                self.vector_db.delete(ids=[doc_id])

            elif self.settings.vector_db_provider == "faiss":
                # FAISS doesn't support deletion, would need to rebuild index
                self.logger.warning("FAISS doesn't support deletion, document marked as deleted")

            self.logger.debug("Document deleted from vector store", doc_id=doc_id)

        except Exception as e:
            self.logger.error("Failed to delete document from vector store", error=str(e))

    def clear(self) -> None:
        """Clear all documents from vector store."""
        try:
            if self.settings.vector_db_provider == "chroma":
                # Delete and recreate collection
                import chromadb

                client = chromadb.HttpClient(
                    host=self.settings.chroma_host,
                    port=self.settings.chroma_port,
                )
                client.delete_collection("agent_memory")
                self.vector_db = client.create_collection("agent_memory")

            elif self.settings.vector_db_provider == "pinecone":
                self.vector_db.delete(delete_all=True)

            elif self.settings.vector_db_provider == "faiss":
                # Recreate FAISS index
                self.vector_db = self._initialize_faiss()
                self._faiss_documents = {}

            self.logger.info("Vector store cleared")

        except Exception as e:
            self.logger.error("Failed to clear vector store", error=str(e))

