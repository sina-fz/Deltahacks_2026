"""
Configuration for the drawing system.
"""
import os
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # "openai", "anthropic", or "openrouter"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")  # Use cheaper model for hackathon (or "openai/gpt-4o-mini" for OpenRouter)

# Drawing Bounds (physical coordinates in mm)
# These should match your BrachioGraph's drawing area
DRAWING_BOX = {
    "min_x": 0.0,   # mm
    "max_x": 200.0, # mm
    "min_y": 0.0,   # mm
    "max_y": 200.0  # mm
}

# Safety Constraints
MAX_STROKES_PER_STEP = 5
MAX_POINTS_PER_STROKE = 50
MAX_TOTAL_POINTS_PER_STEP = 200

# Coordinate System
# Internal: normalized [0.0, 1.0]
# Physical: mapped to DRAWING_BOX

# Execution Settings
CHUNK_SIZE = 2  # Execute N strokes per chunk before checking stop flag
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "drawing_system.log"

def get_drawing_bounds() -> Tuple[float, float, float, float]:
    """Returns (min_x, max_x, min_y, max_y)"""
    box = DRAWING_BOX
    return (box["min_x"], box["max_x"], box["min_y"], box["max_y"])
