import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import faiss
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

class CodeChunk(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    symbol: str
    text: str
    formatted: str

class EmbeddingAgent:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        # Lazy load model to avoid importing on startup delays
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _chunk_file(self, file_path: Path, rel_path: str, symbols: List[Dict[str, Any]]) -> List[CodeChunk]:
        """
        Syntactically chunks a Python file. Extracts function and class definitions
        as distinct chunks, and falls back to text blocks for other lines.
        """
        chunks = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return []

        # Find line intervals already covered by functions/methods/classes
        covered_intervals = []
        file_symbols = [s for s in symbols if s["file_path"] == rel_path]

        # Extract chunks for functions, methods, and classes
        # Sort symbols so we chunk methods, then classes (avoid duplication if possible, or include parent class context)
        for sym in sorted(file_symbols, key=lambda x: x["start_line"]):
            start = max(1, sym["start_line"])
            end = min(len(lines), sym["end_line"])
            
            # Extract actual lines
            chunk_lines = lines[start - 1 : end]
            chunk_text = "".join(chunk_lines)
            
            if not chunk_text.strip():
                continue
                
            formatted = f"# File: {rel_path}\n# Lines: {start}-{end}\n# Symbol: {sym['qualified_name']}\n{chunk_text}"
            
            chunks.append(CodeChunk(
                file_path=rel_path,
                start_line=start,
                end_line=end,
                symbol=sym["qualified_name"],
                text=chunk_text,
                formatted=formatted
            ))
            covered_intervals.append((start, end))

        # Capture remaining code blocks that are not inside functions or classes (e.g. module level variables, imports)
        covered_intervals.sort()
        current_line = 1
        for start, end in covered_intervals:
            if start > current_line:
                # Capture the gap
                gap_lines = lines[current_line - 1 : start - 1]
                gap_text = "".join(gap_lines)
                if gap_text.strip():
                    formatted = f"# File: {rel_path}\n# Lines: {current_line}-{start - 1}\n# Symbol: ModuleLevel\n{gap_text}"
                    chunks.append(CodeChunk(
                        file_path=rel_path,
                        start_line=current_line,
                        end_line=start - 1,
                        symbol="ModuleLevel",
                        text=gap_text,
                        formatted=formatted
                    ))
            current_line = max(current_line, end + 1)

        # Catch tail of the file
        if current_line <= len(lines):
            tail_lines = lines[current_line - 1 :]
            tail_text = "".join(tail_lines)
            if tail_text.strip():
                formatted = f"# File: {rel_path}\n# Lines: {current_line}-{len(lines)}\n# Symbol: ModuleLevel\n{tail_text}"
                chunks.append(CodeChunk(
                    file_path=rel_path,
                    start_line=current_line,
                    end_line=len(lines),
                    symbol="ModuleLevel",
                    text=tail_text,
                    formatted=formatted
                ))

        return chunks

    def run(self, checkout_path: Path, python_files: List[str], symbols: List[Dict[str, Any]], output_dir: Path) -> int:
        """
        Performs syntax-aware chunking, generates embeddings, builds a FAISS index,
        and saves it to the designated folder. Returns the total count of embedded chunks.
        """
        all_chunks: List[CodeChunk] = []

        # 1. Generate Chunks
        for rel_path in python_files:
            file_path = checkout_path / rel_path
            if file_path.exists():
                file_chunks = self._chunk_file(file_path, rel_path, symbols)
                all_chunks.extend(file_chunks)

        if not all_chunks:
            return 0

        # 2. Embed Chunks
        texts = [chunk.formatted for chunk in all_chunks]
        embeddings = self.model.encode(texts, show_progress_bar=False)

        # 3. Create and Write FAISS Index
        embeddings_np = np.array(embeddings).astype("float32")
        dimension = embeddings_np.shape[1]
        
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_np)

        # Ensure directory exists
        faiss_dir = output_dir / "faiss"
        faiss_dir.mkdir(parents=True, exist_ok=True)

        faiss.write_index(index, str(faiss_dir / "index.faiss"))

        # Save metadata matching indexes
        metadata_list = [c.model_dump() for c in all_chunks]
        with open(faiss_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(metadata_list, f, indent=2)

        return len(all_chunks)
