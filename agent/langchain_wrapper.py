"""
LangChain wrapper for LLM initialization.
Supports OpenAI, Anthropic, and OpenRouter.
"""
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOpenAI as CommunityChatOpenAI

from config import LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, LLM_MODEL
from utils.logger import get_logger

logger = get_logger(__name__)


def get_langchain_llm(provider: Optional[str] = None, model: Optional[str] = None, temperature: float = 0.3) -> any:
    """
    Get a LangChain ChatLLM instance.
    
    Args:
        provider: "openai", "anthropic", or "openrouter"
        model: Model name
        temperature: Temperature for generation
    
    Returns:
        LangChain ChatLLM instance
    
    Raises:
        ImportError: If LangChain packages are not installed
    """
    if not LANGCHAIN_AVAILABLE:
        raise ImportError(
            "LangChain packages not installed. Please run: "
            "pip install langchain langchain-openai langchain-anthropic langchain-community"
        )
    
    provider = provider or LLM_PROVIDER
    model = model or LLM_MODEL
    
    if provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set in environment")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=OPENAI_API_KEY
        )
    elif provider == "anthropic":
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            api_key=ANTHROPIC_API_KEY
        )
    elif provider == "openrouter":
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not set in environment")
        # OpenRouter uses OpenAI-compatible API
        return CommunityChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/deltahacks/drawing-system",
                "X-Title": "Drawing System"
            }
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


def get_planning_llm() -> any:
    """Get LLM for planning tasks."""
    return get_langchain_llm(temperature=0.5)  # Slightly higher for creative planning


def get_coordinate_llm() -> any:
    """Get LLM for coordinate generation (needs precision)."""
    return get_langchain_llm(temperature=0.2)  # Lower for precise coordinates


def get_verification_llm() -> any:
    """Get LLM for verification (needs accuracy)."""
    return get_langchain_llm(temperature=0.1)  # Very low for strict verification


def get_agent_llm() -> any:
    """Get LLM for main agent reasoning."""
    return get_langchain_llm(temperature=0.3)  # Balanced for reasoning
