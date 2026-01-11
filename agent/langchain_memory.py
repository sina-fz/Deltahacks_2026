"""
Bridge between DrawingMemory and LangChain memory.
"""
from typing import Dict, Any
from state.memory import DrawingMemory
from utils.logger import get_logger

logger = get_logger(__name__)


def memory_to_context(memory: DrawingMemory) -> str:
    """
    Convert DrawingMemory to a string context for LLM prompts.
    
    Args:
        memory: DrawingMemory instance
    
    Returns:
        String representation of memory state
    """
    return memory.get_state_summary()


def update_memory_from_agent(agent_output: Dict[str, Any], memory: DrawingMemory) -> None:
    """
    Update DrawingMemory from agent output.
    
    Args:
        agent_output: Dictionary with strokes, anchors, labels
        memory: DrawingMemory instance to update
    """
    if "strokes" in agent_output and agent_output["strokes"]:
        stroke_ids = memory.add_strokes(
            agent_output["strokes"],
            agent_output.get("labels", {})
        )
        memory.update_features(agent_output.get("labels", {}), stroke_ids)
    
    if "anchors" in agent_output:
        memory.update_anchors(agent_output["anchors"])
    
    if "assistant_message" in agent_output:
        # Store question if it's a question
        msg = agent_output["assistant_message"]
        if "?" in msg or "clarify" in msg.lower() or "proceed" in msg.lower():
            memory.last_question = msg
        else:
            memory.last_question = None
