"""
Groq LLM Client.

Handles communication with the Groq API for lightning-fast architectural reasoning.
Requires GROQ_API_KEY to be set in the environment.
"""

import json
from typing import Any

from groq import AsyncGroq

from backend.core.config import Settings
from backend.core.logger import get_logger

logger = get_logger(__name__)
settings = Settings()

# Singleton client instance
_client: AsyncGroq | None = None


def get_groq_client() -> AsyncGroq:
    """Get or initialize the Groq client."""
    global _client
    if _client is None:
        api_key = settings.groq_api_key
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set. LLM reasoning disabled.")
        _client = AsyncGroq(api_key=api_key)
    return _client


async def generate_json_response(
    system_prompt: str,
    user_prompt: str,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.2,
) -> dict[str, Any]:
    """
    Generate a JSON response from the Groq LLM.
    
    Args:
        system_prompt: The system context/instructions.
        user_prompt: The specific request/data.
        model: The Groq model to use.
        temperature: Sampling temperature.
        
    Returns:
        Parsed JSON dictionary from the model.
    """
    client = get_groq_client()
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=4000,
        )
        
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from Groq")
            
        return json.loads(content)  # type: ignore[no-any-return]
        
    except Exception as e:
        logger.error("groq_generation_failed", error=str(e))
        raise
