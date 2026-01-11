"""
Prompt template for coordinate generation chain.
"""
from langchain.prompts import ChatPromptTemplate
from config import GRID_SIZE, MAX_POINTS_PER_STROKE


def get_coordinate_prompt() -> ChatPromptTemplate:
    """Get prompt template for coordinate generation chain."""
    return ChatPromptTemplate.from_messages([
        ("system", """You are a coordinate generation assistant. Your job is to generate precise normalized coordinates for drawing components.

You work with a {grid_size}x{grid_size} grid system:
- Grid coordinates: (0,0) to ({grid_max},{grid_max})
- Normalized coordinates: [0.0, 1.0]
- Conversion: grid(x, y) → normalized(x/{grid_size}, y/{grid_size})

Given a component description and grid position, generate the exact coordinate points for drawing it.

Rules:
- All coordinates must be in normalized range [0.0, 1.0]
- For circles: Use 20-30 points evenly spaced (angle 0° to 360°)
- For rectangles: Use 4-5 points (corners + close)
- For triangles: Use 3-4 points (vertices + close)
- For polylines: Use appropriate number of points for smooth curves
- Maximum {max_points} points per stroke

Output a JSON object with this structure:
{{
  "strokes": [[[x1, y1], [x2, y2], ...]],
  "anchors": {{
    "component_center": [x, y],
    "component_top": [x, y],
    "component_bottom": [x, y],
    "component_left": [x, y],
    "component_right": [x, y]
  }},
  "labels": {{"stroke_0": "component_name"}}
}}

Be precise with coordinates. Use the grid position to calculate exact normalized values."""),
        ("human", """Generate coordinates for this component:

Component: {component_name}
Type: {component_type}
Grid Position: {grid_position}
Size: {size}
Description: {description}

Current drawing state:
{memory_context}

Generate the exact coordinate points for drawing this component."""),
    ]).partial(
        grid_size=GRID_SIZE,
        grid_max=GRID_SIZE - 1,
        max_points=MAX_POINTS_PER_STROKE
    )
