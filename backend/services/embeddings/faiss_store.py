"""
FAISS vector store — manages embedding indexes for semantic search.

Stores embeddings in a FAISS index with a parallel metadata list.
Supports: add, search, save/load, and clear operations.

Design decisions:
- Uses IndexFlatIP (inner product) with normalized vectors for cosine similarity.
- Metadata (file path, function name, type) stored in a parallel list — not in FAISS.
- Index is saved/loaded from disk alongside a JSON metadata file.
- Thread-safe for reads; writes should be single-threaded.
- Pure data store — no embedding generation logic here.
"""

import json
from pathlib import Path

import faiss
import numpy as np

from backend.core.logger import get_logger

logger = get_logger(__name__)


class FaissStore:
    """
    FAISS-backed vector store with metadata.

    Each vector has an associated metadata dict that stores:
    - id: unique identifier
    - type: "function", "class", "module"
    - name: human-readable name
    - file_path: source file
    - text_preview: first 200 chars of the embedded text
    """

    def __init__(self, dimension: int = 384) -> None:
        """
        Initialize the FAISS store.

        Args:
            dimension: Vector dimension (must match embedding model output).
                       384 for all-MiniLM-L6-v2.
        """
        self.dimension = dimension
        # IndexFlatIP = exact inner product search.
        # With normalized vectors, IP == cosine similarity.
        self.index = faiss.IndexFlatIP(dimension)
        self.metadata: list[dict[str, str]] = []

    @property
    def size(self) -> int:
        """Number of vectors in the index."""
        return self.index.ntotal

    def add(
        self,
        embeddings: np.ndarray,
        metadata_list: list[dict[str, str]],
    ) -> None:
        """
        Add vectors and their metadata to the index.

        Vectors are L2-normalized before adding so that inner product == cosine similarity.

        Args:
            embeddings: Array of shape (N, dimension), dtype float32.
            metadata_list: List of N metadata dicts, one per vector.

        Raises:
            ValueError: If embeddings shape doesn't match or metadata count differs.
        """
        if len(embeddings) == 0:
            return

        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension {embeddings.shape[1]} != expected {self.dimension}"
            )

        if len(embeddings) != len(metadata_list):
            raise ValueError(
                f"Got {len(embeddings)} embeddings but {len(metadata_list)} metadata entries"
            )

        # Normalize for cosine similarity via inner product
        vectors = embeddings.astype(np.float32)
        faiss.normalize_L2(vectors)

        self.index.add(vectors)
        self.metadata.extend(metadata_list)

        logger.info("faiss_vectors_added", count=len(embeddings), total=self.size)

    def search(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        min_score: float = 0.0,
    ) -> list[dict[str, str | float]]:
        """
        Search for the k nearest neighbors of the query vector.

        Args:
            query_embedding: Query vector of shape (1, dimension) or (dimension,).
            k: Number of results to return.
            min_score: Minimum cosine similarity score to include.

        Returns:
            List of result dicts with metadata + similarity score, sorted by score descending.
        """
        if self.size == 0:
            return []

        # Ensure shape is (1, dimension)
        query = query_embedding.astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(query)

        # Clamp k to index size
        k = min(k, self.size)

        scores, indices = self.index.search(query, k)

        results: list[dict[str, str | float]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            if score < min_score:
                continue

            result = {**self.metadata[idx], "score": round(float(score), 4)}
            results.append(result)

        return results

    def save(self, directory: Path) -> None:
        """
        Save the FAISS index and metadata to disk.

        Creates two files:
        - faiss_index.bin: the FAISS index
        - faiss_metadata.json: the metadata list

        Args:
            directory: Directory to save into (created if needed).
        """
        directory.mkdir(parents=True, exist_ok=True)

        index_path = directory / "faiss_index.bin"
        metadata_path = directory / "faiss_metadata.json"

        faiss.write_index(self.index, str(index_path))
        metadata_path.write_text(
            json.dumps(self.metadata, indent=2),
            encoding="utf-8",
        )

        logger.info(
            "faiss_index_saved",
            path=str(directory),
            vectors=self.size,
        )

    def load(self, directory: Path) -> bool:
        """
        Load a FAISS index and metadata from disk.

        Args:
            directory: Directory containing the saved index files.

        Returns:
            True if loaded successfully, False if files not found.
        """
        index_path = directory / "faiss_index.bin"
        metadata_path = directory / "faiss_metadata.json"

        if not index_path.exists() or not metadata_path.exists():
            logger.warning("faiss_index_not_found", path=str(directory))
            return False

        self.index = faiss.read_index(str(index_path))
        self.metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

        logger.info(
            "faiss_index_loaded",
            path=str(directory),
            vectors=self.size,
        )
        return True

    def clear(self) -> None:
        """Reset the index and metadata."""
        self.index = faiss.IndexFlatIP(self.dimension)
        self.metadata = []
