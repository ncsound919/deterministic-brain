"""
Vector Memory System using ChromaDB
Enables semantic search and retrieval of past conversations, skills, and knowledge
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from loguru import logger
from config import settings

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
    - Thread isolation (separate collections per context)
    - Efficient similarity retrieval
    """

    def __init__(self, persist_directory: Optional[Path] = None):
        """Initialize vector memory with ChromaDB"""

        self.persist_dir = persist_directory or settings._normalize_path(settings.vector_db_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Initialize embedding model (384-dimensional, fast)
        logger.info("Loading sentence transformer model...")
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Embedding model loaded")

        # Collections for different memory types
        self.conversations = self._get_or_create_collection("conversations")
        self.skills = self._get_or_create_collection("skills")
        self.knowledge = self._get_or_create_collection("knowledge")

        # Thread-specific collections (created on demand)
        self.threads: Dict[str, Any] = {}

    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection"""
        try:
            return self.client.get_collection(name=name)
        except Exception:
            return self.client.create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )

    def get_thread_collection(self, thread_name: str):
        """Get or create a thread-specific collection"""
        if thread_name not in self.threads:
            collection_name = f"thread_{thread_name}"
            self.threads[thread_name] = self._get_or_create_collection(collection_name)
        return self.threads[thread_name]

    def add_conversation(
        self,
        content: str,
        role: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add a conversation turn to memory

        Args:
            content: The message content
            role: user, assistant, or system
            metadata: Additional metadata (task_type, cost, etc.)

        Returns:
            Memory entry ID
        """
        entry_id = f"conv_{datetime.now().timestamp()}"

        # Generate embedding
        embedding = self.embedder.encode(content).tolist()

        # Prepare metadata
        meta = metadata or {}
        meta.update({
            "role": role,
            "timestamp": datetime.now().isoformat(),
            "type": "conversation"
        })

        # Store in ChromaDB
        self.conversations.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta]
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
        """
        Add a learned skill to memory

        Args:
            name: Skill name
            description: What the skill does
            workflow: Sequence of steps
            success_rate: Historical success rate

        Returns:
            Memory entry ID
        """
        entry_id = f"skill_{name}"

        # Create searchable content
        content = f"{name}: {description}\nWorkflow: {workflow}"

        # Generate embedding
        embedding = self.embedder.encode(content).tolist()

        # Store metadata
        meta = {
            "name": name,
            "description": description,
            "success_rate": success_rate,
            "timestamp": datetime.now().isoformat(),
            "type": "skill"
        }

        self.skills.upsert(  # Upsert to update existing skills
            ids=[entry_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta]
        )

        logger.info(f"Added/updated skill: {name}")
        return entry_id

    def add_knowledge(
        self,
        content: str,
        category: str,
        source: Optional[str] = None
    ) -> str:
        """
        Add knowledge/fact to memory

        Args:
            content: The knowledge content
            category: Category (e.g., "finance", "coding", "user_preference")
            source: Where this knowledge came from

        Returns:
            Memory entry ID
        """
        entry_id = f"knowledge_{datetime.now().timestamp()}"

        # Generate embedding
        embedding = self.embedder.encode(content).tolist()

        # Store metadata
        meta = {
            "category": category,
            "source": source or "unknown",
            "timestamp": datetime.now().isoformat(),
            "type": "knowledge"
        }

        self.knowledge.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta]
        )

        logger.debug(f"Added knowledge: {category}")
        return entry_id

    def add_to_thread(
        self,
        thread_name: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add memory to a specific thread (e.g., "coding", "research", "logistics")

        Thread isolation ensures different contexts don't pollute each other
        """
        collection = self.get_thread_collection(thread_name)
        entry_id = f"{thread_name}_{datetime.now().timestamp()}"

        embedding = self.embedder.encode(content).tolist()

        meta = metadata or {}
        meta.update({
            "thread": thread_name,
            "timestamp": datetime.now().isoformat()
        })

        collection.add(
            ids=[entry_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[meta]
        )

        logger.debug(f"Added to thread '{thread_name}': {entry_id}")
        return entry_id

    def search_conversations(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Semantic search across conversation history

        Args:
            query: Search query
            n_results: Number of results to return
            filter_metadata: Filter by metadata (e.g., {"role": "assistant"})

        Returns:
            List of matching conversation entries
        """
        query_embedding = self.embedder.encode(query).tolist()

        results = self.conversations.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata
        )

        return self._format_results(results)

    def search_skills(
        self,
        query: str,
        n_results: int = 3
    ) -> List[Dict]:
        """
        Find relevant skills for a task

        Args:
            query: Task description
            n_results: Number of skills to return

        Returns:
            List of relevant skills with success rates
        """
        query_embedding = self.embedder.encode(query).tolist()

        results = self.skills.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        return self._format_results(results)

    def search_knowledge(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Search knowledge base

        Args:
            query: What to search for
            category: Optional category filter
            n_results: Number of results

        Returns:
            List of relevant knowledge entries
        """
        query_embedding = self.embedder.encode(query).tolist()

        where = {"category": category} if category else None

        results = self.knowledge.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )

        return self._format_results(results)

    def search_thread(
        self,
        thread_name: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Search within a specific thread

        Useful for finding relevant context within isolated workstreams
        """
        if thread_name not in self.threads:
            return []

        collection = self.get_thread_collection(thread_name)
        query_embedding = self.embedder.encode(query).tolist()

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

        return self._format_results(results)

    def _format_results(self, chroma_results: Dict) -> List[Dict]:
        """Format ChromaDB results into clean list"""
        if not chroma_results["ids"]:
            return []

        formatted = []
        for i in range(len(chroma_results["ids"][0])):
            formatted.append({
                "id": chroma_results["ids"][0][i],
                "content": chroma_results["documents"][0][i],
                "metadata": chroma_results["metadatas"][0][i],
                "distance": chroma_results["distances"][0][i] if "distances" in chroma_results else None
            })

        return formatted

    def get_recent_context(
        self,
        limit: int = 10,
        thread: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent conversation context

        Args:
            limit: Number of recent entries
            thread: Optional thread filter

        Returns:
            Recent conversation entries
        """
        collection = self.get_thread_collection(thread) if thread else self.conversations

        # Fetch all items so we can sort by timestamp and return the truly most-recent ones.
        # ChromaDB's get() has no ordering guarantee, so fetching only `limit` items can
        # silently omit newer entries.
        all_results = collection.get(
            include=["documents", "metadatas"]
        )

        if not all_results["ids"]:
            return []

        # Convert to list of dicts
        entries = [
            {
                "id": all_results["ids"][i],
                "content": all_results["documents"][i],
                "metadata": all_results["metadatas"][i]
            }
            for i in range(len(all_results["ids"]))
        ]

        # Sort by timestamp (most recent first) then return top `limit`
        entries.sort(
            key=lambda x: x["metadata"].get("timestamp", ""),
            reverse=True
        )

        return entries[:limit]

    def clear_thread(self, thread_name: str):
        """Clear all memories from a specific thread"""
        if thread_name in self.threads:
            collection = self.get_thread_collection(thread_name)
            self.client.delete_collection(f"thread_{thread_name}")
            del self.threads[thread_name]
            logger.info(f"Cleared thread: {thread_name}")

    def get_stats(self) -> Dict:
        """Get memory statistics"""
        return {
            "conversations": self.conversations.count(),
            "skills": self.skills.count(),
            "knowledge": self.knowledge.count(),
            "threads": {
                name: collection.count()
                for name, collection in self.threads.items()
            },
            "total_entries": (
                self.conversations.count() +
                self.skills.count() +
                self.knowledge.count() +
                sum(c.count() for c in self.threads.values())
            )
        }

# Global vector memory instance (lazily initialized to avoid heavy import-time work)
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
