"""
Vector Memory System using Qdrant
Enables semantic search and retrieval of past conversations, skills, and knowledge
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from loguru import logger
import uuid
import atexit
import sys

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

from config import cfg

@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    timestamp: Optional[datetime] = None

class VectorMemory:
    """
    Vector-based semantic memory system
    
    Features:
    - Semantic search across all past interactions
    - Automatic embedding generation
    - Thread isolation (using metadata filtering)
    - Efficient similarity retrieval
    """

    def __init__(self, persist_directory: Optional[Path] = None):
        """Initialize vector memory with Qdrant"""
        self.persist_dir = persist_directory or Path(".qdrant_data")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.url = cfg.qdrant_url
        self.api_key = cfg.qdrant_api_key
        
        # Initialize Qdrant client
        try:
            if self.url and self.url != "http://localhost:6333":
                logger.info(f"Connecting to remote Qdrant at {self.url}")
                self.client = QdrantClient(url=self.url, api_key=self.api_key)
            else:
                logger.info(f"Using local Qdrant at {self.persist_dir}")
                self.client = QdrantClient(path=str(self.persist_dir))
            
            # Register explicit close on exit to avoid meta_path None errors
            atexit.register(self.close)
        except Exception as e:
            if "already accessed by another instance" in str(e):
                logger.warning("Qdrant storage locked. Using in-memory fallback for this session.")
                self.client = QdrantClient(location=":memory:")
            else:
                raise e

        # Initialize embedding model (384-dimensional, fast)
        logger.info("Loading sentence transformer model...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_size = 384
        logger.info("Embedding model loaded")

        # Collections for different memory types
        self._ensure_collection("conversations")
        self._ensure_collection("skills")
        self._ensure_collection("knowledge")
        self._ensure_collection("threads")

    def _ensure_collection(self, name: str):
        """Get or create a Qdrant collection"""
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if name not in collections:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.error(f"Failed to ensure collection {name}: {e}")

    def add_conversation(
        self,
        content: str,
        role: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add a conversation turn to memory"""
        entry_id = str(uuid.uuid4())
        embedding = self.embedder.encode(content).tolist()

        meta = metadata or {}
        meta.update({
            "role": role,
            "timestamp": datetime.now().isoformat(),
            "type": "conversation",
            "content": content
        })

        self.client.upsert(
            collection_name="conversations",
            points=[
                PointStruct(
                    id=entry_id,
                    vector=embedding,
                    payload=meta
                )
            ]
        )

        logger.debug(f"Added conversation memory: {entry_id}")
        return entry_id

    def add_skill(
        self,
        name: str,
        description: str,
        workflow: List[Dict],
        success_rate: float = 0.0
    ) -> str:
        """Add a learned skill to memory"""
        # Create a deterministic UUID for the skill based on its name
        import hashlib
        m = hashlib.md5()
        m.update(name.encode('utf-8'))
        entry_id = str(uuid.UUID(m.hexdigest()))

        content = f"{name}: {description}\nWorkflow: {workflow}"
        embedding = self.embedder.encode(content).tolist()

        meta = {
            "name": name,
            "description": description,
            "success_rate": success_rate,
            "timestamp": datetime.now().isoformat(),
            "type": "skill",
            "content": content
        }

        self.client.upsert(
            collection_name="skills",
            points=[
                PointStruct(
                    id=entry_id,
                    vector=embedding,
                    payload=meta
                )
            ]
        )

        logger.info(f"Added/updated skill: {name}")
        return entry_id

    def add_knowledge(
        self,
        content: str,
        category: str,
        source: Optional[str] = None
    ) -> str:
        """Add knowledge/fact to memory"""
        entry_id = str(uuid.uuid4())
        embedding = self.embedder.encode(content).tolist()

        meta = {
            "category": category,
            "source": source or "unknown",
            "timestamp": datetime.now().isoformat(),
            "type": "knowledge",
            "content": content
        }

        self.client.upsert(
            collection_name="knowledge",
            points=[
                PointStruct(
                    id=entry_id,
                    vector=embedding,
                    payload=meta
                )
            ]
        )

        logger.debug(f"Added knowledge: {category}")
        return entry_id

    def add_to_thread(
        self,
        thread_name: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Add memory to a specific thread"""
        entry_id = str(uuid.uuid4())
        embedding = self.embedder.encode(content).tolist()

        meta = metadata or {}
        meta.update({
            "thread": thread_name,
            "timestamp": datetime.now().isoformat(),
            "content": content
        })

        self.client.upsert(
            collection_name="threads",
            points=[
                PointStruct(
                    id=entry_id,
                    vector=embedding,
                    payload=meta
                )
            ]
        )

        logger.debug(f"Added to thread '{thread_name}': {entry_id}")
        return entry_id

    def search_conversations(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """Semantic search across conversation history"""
        query_embedding = self.embedder.encode(query).tolist()
        
        query_filter = None
        if filter_metadata:
            must_conds = []
            for k, v in filter_metadata.items():
                must_conds.append(FieldCondition(key=k, match=MatchValue(value=v)))
            query_filter = Filter(must=must_conds)

        results = self.client.query_points(
            collection_name="conversations",
            query=query_embedding,
            query_filter=query_filter,
            limit=n_results
        ).points

        return self._format_results(results)

    def search_skills(
        self,
        query: str,
        n_results: int = 3
    ) -> List[Dict]:
        """Find relevant skills for a task"""
        query_embedding = self.embedder.encode(query).tolist()

        results = self.client.query_points(
            collection_name="skills",
            query=query_embedding,
            limit=n_results
        ).points

        return self._format_results(results)

    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """Search knowledge base"""
        query_embedding = self.embedder.encode(query).tolist()

        query_filter = None
        if category:
            query_filter = Filter(
                must=[FieldCondition(key="category", match=MatchValue(value=category))]
            )

        results = self.client.query_points(
            collection_name="knowledge",
            query=query_embedding,
            query_filter=query_filter,
            limit=n_results
        ).points

        return self._format_results(results)

    def search_thread(
        self,
        thread_name: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict]:
        """Search within a specific thread"""
        query_embedding = self.embedder.encode(query).tolist()
        query_filter = Filter(
            must=[FieldCondition(key="thread", match=MatchValue(value=thread_name))]
        )

        results = self.client.query_points(
            collection_name="threads",
            query=query_embedding,
            query_filter=query_filter,
            limit=n_results
        ).points

        return self._format_results(results)

    def _format_results(self, qdrant_results: List[Any]) -> List[Dict]:
        """Format Qdrant results into clean list of dicts"""
        formatted = []
        for point in qdrant_results:
            formatted.append({
                "id": str(point.id),
                "content": point.payload.get("content", ""),
                "metadata": point.payload,
                "distance": point.score
            })
        return formatted

    def get_recent_context(
        self,
        limit: int = 10,
        thread: Optional[str] = None
    ) -> List[Dict]:
        """Get recent conversation context"""
        collection = "threads" if thread else "conversations"
        
        query_filter = None
        if thread:
            query_filter = Filter(must=[FieldCondition(key="thread", match=MatchValue(value=thread))])
            
        # Qdrant scroll gets points without search
        results, _ = self.client.scroll(
            collection_name=collection,
            scroll_filter=query_filter,
            limit=limit * 10,  # Get more to sort by timestamp
            with_payload=True
        )

        if not results:
            return []

        entries = [
            {
                "id": str(p.id),
                "content": p.payload.get("content", ""),
                "metadata": p.payload
            }
            for p in results
        ]

        entries.sort(
            key=lambda x: x["metadata"].get("timestamp", ""),
            reverse=True
        )

        return entries[:limit]

    def clear_thread(self, thread_name: str):
        """Clear all memories from a specific thread"""
        try:
            self.client.delete(
                collection_name="threads",
                points_selector=Filter(
                    must=[FieldCondition(key="thread", match=MatchValue(value=thread_name))]
                )
            )
            logger.info(f"Cleared thread: {thread_name}")
        except Exception as e:
            logger.error(f"Failed to clear thread {thread_name}: {e}")

    def close(self):
        """Explicitly close the Qdrant client."""
        if hasattr(self, "client") and self.client:
            try:
                # Only close if we're not in the middle of a shutdown crash
                if sys.meta_path is not None:
                    self.client.close()
            except Exception:
                pass

    def get_stats(self) -> Dict:
        """Get memory statistics"""
        try:
            conv_count = self.client.count(collection_name="conversations").count
            skill_count = self.client.count(collection_name="skills").count
            know_count = self.client.count(collection_name="knowledge").count
            thread_count = self.client.count(collection_name="threads").count
            
            return {
                "conversations": conv_count,
                "skills": skill_count,
                "knowledge": know_count,
                "threads": thread_count,
                "total_entries": conv_count + skill_count + know_count + thread_count
            }
        except Exception:
            return {}

# Global vector memory instance
_vector_memory_instance: Optional[VectorMemory] = None

def get_vector_memory() -> VectorMemory:
    """Get the shared VectorMemory instance, creating it on first use."""
    global _vector_memory_instance
    if _vector_memory_instance is None:
        _vector_memory_instance = VectorMemory()
    return _vector_memory_instance

class _LazyVectorMemoryProxy:
    """Proxy that defers VectorMemory initialization until first attribute access."""
    def __getattr__(self, name: str):
        return getattr(get_vector_memory(), name)

vector_memory = _LazyVectorMemoryProxy()
