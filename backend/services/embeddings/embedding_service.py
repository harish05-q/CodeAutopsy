"""
Embedding service — generates semantic embeddings for code elements.

Uses sentence-transformers to encode functions, classes, and modules
into dense vectors. These are stored in FAISS for semantic search.

Design decisions:
- Model is loaded once and cached (lazy initialization).
- Builds text representations from code structure, not raw source.
  This produces better semantic embeddings for code search.
- Processes in batches for efficiency.
- Pure service: takes parsed data → returns embeddings. No side effects.
- Model selection: all-MiniLM-L6-v2 (fast, 384-dim, good quality).
"""

import time

import numpy as np

from backend.core.logger import get_logger
from backend.models.schemas import FunctionInfo, ClassInfo, ModuleInfo
from backend.services.embeddings.faiss_store import FaissStore

logger = get_logger(__name__)

# Module-level model cache (loaded once on first use)
_model = None


def _get_model():  # type: ignore[no-untyped-def]
    """
    Lazy-load the sentence-transformer model.

    Cached at module level so it's only loaded once per process.
    """
    global _model
    if _model is None:
        logger.info("loading_embedding_model", model="all-MiniLM-L6-v2")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("embedding_model_loaded")
    return _model


def _function_to_text(func: FunctionInfo) -> str:
    """
    Convert a FunctionInfo into a text representation for embedding.

    Combines name, parameters, docstring, and metadata into a
    searchable text representation.
    """
    parts = [f"Function: {func.name}"]
    if func.parameters:
        params = [p for p in func.parameters if p not in ("self", "cls")]
        if params:
            parts.append(f"Parameters: {', '.join(params)}")
    if func.return_type:
        parts.append(f"Returns: {func.return_type}")
    if func.docstring:
        parts.append(f"Description: {func.docstring[:300]}")
    if func.decorators:
        parts.append(f"Decorators: {', '.join(func.decorators)}")
    if func.is_async:
        parts.append("Async function")
    parts.append(f"Complexity: {func.complexity}")
    return ". ".join(parts)


def _class_to_text(cls: ClassInfo) -> str:
    """Convert a ClassInfo into a text representation for embedding."""
    parts = [f"Class: {cls.name}"]
    if cls.bases:
        parts.append(f"Inherits from: {', '.join(cls.bases)}")
    if cls.docstring:
        parts.append(f"Description: {cls.docstring[:300]}")
    if cls.methods:
        parts.append(f"Methods: {', '.join(cls.methods[:15])}")
    if cls.attributes:
        parts.append(f"Attributes: {', '.join(cls.attributes[:15])}")
    parts.append(f"Method count: {cls.method_count}")
    return ". ".join(parts)


def _module_to_text(module: ModuleInfo) -> str:
    """Convert a ModuleInfo into a text representation for embedding."""
    parts = [f"Module: {module.module_name}"]
    if module.docstring:
        parts.append(f"Description: {module.docstring[:300]}")
    if module.functions:
        func_names = [f.name for f in module.functions[:10]]
        parts.append(f"Functions: {', '.join(func_names)}")
    if module.classes:
        cls_names = [c.name for c in module.classes[:10]]
        parts.append(f"Classes: {', '.join(cls_names)}")
    parts.append(f"Lines: {module.line_count}")
    return ". ".join(parts)


def generate_embeddings(
    modules: list[ModuleInfo],
    embedding_dim: int = 384,
) -> tuple[FaissStore, dict[str, int]]:
    """
    Generate embeddings for all code elements and store them in FAISS.

    Embeds three types of code elements:
    1. Functions (including methods)
    2. Classes
    3. Modules (files)

    Args:
        modules: Parsed module data.
        embedding_dim: Dimension of the embedding model output.

    Returns:
        Tuple of (FaissStore with all embeddings, stats dict).
    """
    start = time.monotonic()
    model = _get_model()
    store = FaissStore(dimension=embedding_dim)

    texts: list[str] = []
    metadata_list: list[dict[str, str]] = []

    # Collect texts and metadata for all code elements
    for module in modules:
        # Module-level embedding
        module_text = _module_to_text(module)
        texts.append(module_text)
        metadata_list.append({
            "id": f"module::{module.module_name}",
            "type": "module",
            "name": module.module_name,
            "file_path": module.file_path,
            "text_preview": module_text[:200],
        })

        # Function embeddings
        for func in module.functions:
            func_text = _function_to_text(func)
            texts.append(func_text)
            metadata_list.append({
                "id": f"function::{func.qualified_name}",
                "type": "method" if func.is_method else "function",
                "name": func.name,
                "file_path": func.file_path,
                "text_preview": func_text[:200],
            })

        # Class embeddings
        for cls in module.classes:
            cls_text = _class_to_text(cls)
            texts.append(cls_text)
            metadata_list.append({
                "id": f"class::{cls.qualified_name}",
                "type": "class",
                "name": cls.name,
                "file_path": cls.file_path,
                "text_preview": cls_text[:200],
            })

    if not texts:
        logger.warning("no_texts_to_embed")
        return store, {"functions": 0, "classes": 0, "modules": 0, "total": 0}

    # Generate embeddings in batch
    logger.info("generating_embeddings", count=len(texts))
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=64)
    embeddings_np = np.array(embeddings, dtype=np.float32)

    # Add to FAISS store
    store.add(embeddings_np, metadata_list)

    duration = time.monotonic() - start

    stats = {
        "functions": sum(1 for m in metadata_list if m["type"] in ("function", "method")),
        "classes": sum(1 for m in metadata_list if m["type"] == "class"),
        "modules": sum(1 for m in metadata_list if m["type"] == "module"),
        "total": len(texts),
        "duration_seconds": round(duration, 3),
    }

    logger.info("embeddings_generated", **stats)

    return store, stats


def semantic_search(
    query: str,
    store: FaissStore,
    k: int = 10,
    min_score: float = 0.2,
    type_filter: str | None = None,
) -> list[dict[str, str | float]]:
    """
    Perform semantic search over the code embedding index.

    Args:
        query: Natural language search query.
        store: FAISS store with code embeddings.
        k: Number of results to return.
        min_score: Minimum cosine similarity threshold.
        type_filter: Optional filter by element type ("function", "class", "module").

    Returns:
        List of search results with metadata and similarity scores.
    """
    if store.size == 0:
        return []

    model = _get_model()

    # Encode the query
    query_embedding = model.encode([query], show_progress_bar=False)
    query_np = np.array(query_embedding, dtype=np.float32)

    # Search with extra results if filtering
    search_k = k * 3 if type_filter else k
    results = store.search(query_np, k=search_k, min_score=min_score)

    # Apply type filter if specified
    if type_filter:
        results = [r for r in results if r.get("type") == type_filter]

    return results[:k]
