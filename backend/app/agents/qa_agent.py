import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import faiss
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from groq import Groq
from backend.app.config import settings

logger = logging.getLogger(__name__)

class SourceCitation(BaseModel):
    file_path: str
    line_interval: List[int] # [start_line, end_line]
    symbol: str
    relevance_score: float

class QaResponse(BaseModel):
    answer: str
    confidence: str # High, Medium, Low
    sources: List[SourceCitation]

class QaAgent:
    def __init__(self, api_key: str = "", model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = Groq(api_key=api_key) if api_key else None
        self._model = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    def _get_fallback_qa(self, question: str, retrieved_chunks: List[Tuple[Dict[str, Any], float]]) -> QaResponse:
        """Retrieval-only fallback when Groq LLM is not configured."""
        answer = "### Semantic Retrieval Results\n\nGroq API is not configured. Here are the top matching source code blocks found for your question:\n\n"
        citations = []
        
        for idx, (chunk, score) in enumerate(retrieved_chunks):
            file_path = chunk["file_path"]
            start = chunk["start_line"]
            end = chunk["end_line"]
            symbol = chunk["symbol"]
            text = chunk["text"]
            
            # Map score: FlatL2 distance. Closer to 0 is better. Let's make relevance score
            relevance = float(max(0.0, min(1.0, 1.0 - (score / 2.0))))

            answer += f"#### [{file_path} (Lines {start}-{end})](file:///{file_path})\n"
            answer += f"**Symbol:** `{symbol}`\n"
            answer += f"```python\n{text}\n```\n\n"
            
            citations.append(SourceCitation(
                file_path=file_path,
                line_interval=[start, end],
                symbol=symbol,
                relevance_score=round(relevance, 2)
            ))
            
        return QaResponse(
            answer=answer,
            confidence="Medium (Retrieved Snips Only)",
            sources=citations
        )

    def run(self, repository_id: str, question: str) -> QaResponse:
        """
        Runs RAG:
        1. Embeds question.
        2. Queries FAISS index.
        3. Prompts Groq with context chunks.
        4. Returns structured answer and citations.
        """
        faiss_dir = settings.ANALYSIS_DIR / repository_id / "faiss"
        index_path = faiss_dir / "index.faiss"
        chunks_path = faiss_dir / "chunks.json"

        if not index_path.exists() or not chunks_path.exists():
            return QaResponse(
                answer="No analysis case or index was found for this repository. Please run an examination first.",
                confidence="Low",
                sources=[]
            )

        # 1. Load FAISS flat index and chunks metadata
        index = faiss.read_index(str(index_path))
        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        # 2. Embed Query
        query_vector = self.model.encode([question]).astype("float32")
        
        # 3. Retrieve Top-K Chunks
        k = 4
        distances, indices = index.search(query_vector, k)
        
        retrieved: List[Tuple[Dict[str, Any], float]] = []
        for idx_in_search, idx_in_meta in enumerate(indices[0]):
            if idx_in_meta != -1 and idx_in_meta < len(chunks):
                retrieved.append((chunks[idx_in_meta], float(distances[0][idx_in_search])))

        if not retrieved:
            return QaResponse(
                answer="I searched the vector database but couldn't find any relevant code snippets in the repository.",
                confidence="Low",
                sources=[]
            )

        # If LLM is not configured, return semantic retrieval result
        if not self.client:
            return self._get_fallback_qa(question, retrieved)

        # 4. Formulate LLM Prompt
        context_str = ""
        citations = []
        for i, (chunk, score) in enumerate(retrieved):
            file_path = chunk["file_path"]
            start = chunk["start_line"]
            end = chunk["end_line"]
            symbol = chunk["symbol"]
            text = chunk["text"]
            
            context_str += f"--- Source {i+1} ---\n"
            context_str += f"File: {file_path}\n"
            context_str += f"Lines: {start}-{end}\n"
            context_str += f"Symbol: {symbol}\n"
            context_str += f"{text}\n\n"
            
            relevance = float(max(0.0, min(1.0, 1.0 - (score / 2.0))))
            citations.append(SourceCitation(
                file_path=file_path,
                line_interval=[start, end],
                symbol=symbol,
                relevance_score=round(relevance, 2)
            ))

        prompt = f"""You are an advanced software QA chatbot. Answer the user's question about the repository based ONLY on the provided code snippet context.
If the snippets do not contain enough information to answer the question, do your best but state that the context was limited and point out what is missing.

User Question: {question}

Context Snippets:
{context_str}

Respond ONLY as a valid JSON object matching this schema:
{{
  "answer": "Compelling answer in Markdown formatting. Include code examples from the context where appropriate. Quote file paths.",
  "confidence": "High", // High, Medium, or Low
  "cited_sources": [
     // Index numbers (1-based) of the sources you actually used to answer the question (e.g. [1, 3])
     1, 3
  ]
}}
"""
        try:
            chat_completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a repository assistant. Return ONLY a valid JSON object."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result_data = json.loads(chat_completion.choices[0].message.content)
            
            # Map LLM-cited sources back to the actual citation list
            used_citations = []
            cited_indices = result_data.get("cited_sources", [])
            for idx in cited_indices:
                # idx is 1-based
                if 1 <= idx <= len(citations):
                    used_citations.append(citations[idx - 1])
                    
            if not used_citations:
                # If LLM didn't cite properly, default to all retrieved citations
                used_citations = citations

            return QaResponse(
                answer=result_data.get("answer", "No answer compiled."),
                confidence=result_data.get("confidence", "Medium"),
                sources=used_citations
            )
        except Exception as e:
            logger.error(f"Error calling Groq API for QA: {e}. Falling back.")
            return self._get_fallback_qa(question, retrieved)
