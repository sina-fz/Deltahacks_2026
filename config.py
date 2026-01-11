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
MAX_STROKES_PER_STEP = 20  # Increased to allow more complex drawings
MAX_POINTS_PER_STROKE = 50
MAX_TOTAL_POINTS_PER_STEP = 200

# Coordinate System
# Internal: normalized [0.0, 1.0]
# Physical: mapped to DRAWING_BOX

# Grid System
GRID_SIZE = 10  # 10x10 grid (100 cells total)
# Each grid cell = 0.1 in normalized coordinates
# Grid coordinates: (0,0) to (9,9)
# Conversion: grid(x, y) → normalized(x/10, y/10)

# Execution Settings
CHUNK_SIZE = 2  # Execute N strokes per chunk before checking stop flag
SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
PREVIEW_MODE = os.getenv("PREVIEW_MODE", "true").lower() == "true"  # Show preview before sending to hardware

# Agent Settings
USE_LANGCHAIN_AGENT = os.getenv("USE_LANGCHAIN_AGENT", "true").lower() == "true"  # Use LangChain agent or legacy system

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "drawing_system.log"

# Raspberry Pi Configuration
RASPBERRY_PI_HOST = os.getenv("RASPBERRY_PI_HOST", "raspberrypi.local")  # Or use IP like "192.168.1.100"
RASPBERRY_PI_USER = os.getenv("RASPBERRY_PI_USER", "pi")
RASPBERRY_PI_RUNJOB_PATH = "/home/pi/runjob.py"
RASPBERRY_PI_JOB_PATH = "/tmp/job.json"
USE_RASPBERRY_PI = os.getenv("USE_RASPBERRY_PI", "false").lower() == "true"

def get_drawing_bounds() -> Tuple[float, float, float, float]:
    """Returns (min_x, max_x, min_y, max_y)"""
    box = DRAWING_BOX
    return (box["min_x"], box["max_x"], box["min_y"], box["max_y"])
