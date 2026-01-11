"""
Build prompts for the LLM with instruction, state, and constraints.
Optimized for clarity, speed, and accuracy.
"""
from typing import Optional
from state.memory import DrawingMemory
from config import MAX_STROKES_PER_STEP, MAX_POINTS_PER_STROKE


def build_prompt(
    instruction: str,
    memory: DrawingMemory,
    coordinate_system_info: str = None
) -> str:
    """
    Build a prompt for the LLM with all necessary context.
    
    Args:
        instruction: User's instruction
        memory: Current drawing memory/state
        coordinate_system_info: Optional additional coordinate system info
    
    Returns:
        Complete prompt string
    """
    state_summary = memory.get_state_summary()
    
    # CRITICAL: Answer recognition context (MUST BE FIRST)
    answer_context = ""
    if memory.last_question:
        answer_context = f"""
═══════════════════════════════════════════════════════════════════
⚠️ YOU ASKED A QUESTION IN YOUR LAST RESPONSE ⚠️
YOUR QUESTION: "{memory.last_question}"
THE USER'S INSTRUCTION IS AN ANSWER TO THAT QUESTION!
═══════════════════════════════════════════════════════════════════

EXTRACT THE ANSWER AND DRAW IMMEDIATELY:
- "top-center", "top-left", "top-right", "center" → Side placement
- "from base", "from tip", "base", "tip" → Tip/base placement  
- "left", "right" → Direction
- "yes", "ok", "continue" → Confirmation

IF USER SAYS: "top-center and from base" → COMPLETE ANSWER → DRAW NOW!
IF USER SAYS: "top-center" only → PARTIAL ANSWER → Ask ONLY for missing part

⚠️ DO NOT ASK THE QUESTION AGAIN - USE THE ANSWER AND DRAW! ⚠️
═══════════════════════════════════════════════════════════════════

"""
    
    prompt = f"""You are a drawing assistant. Control a robotic arm to draw step-by-step.

USER INSTRUCTION: {instruction}{answer_context}

CURRENT DRAWING STATE:
{state_summary}

COORDINATE SYSTEM:
- Normalized [0.0, 1.0]: (0.0, 0.0) = bottom-left, (1.0, 1.0) = top-right
- All coordinates must be in [0.0, 1.0]

DECISION TREE (FOLLOW IN ORDER - STOP AT FIRST MATCH):

1. IF THERE IS A "YOUR QUESTION" SECTION ABOVE:
   → User is answering your question - DO NOT ASK AGAIN
   → Look for answer words in user instruction:
     * "top-center", "top-left", "top-right", "center" = side answer
     * "from base", "from tip", "base", "tip" = tip/base answer
     * "left", "right" = direction answer
   → If user provides BOTH side AND tip/base → COMPLETE ANSWER → DRAW NOW
   → If user provides only ONE (side OR tip/base) → PARTIAL ANSWER → Ask ONLY for missing part
   → DO NOT ask the same question again

2. IF USER SAYS "on top of", "beside", "below", "inside", "on":
   → You need 2-3 pieces of info:
     a) Which shape? (if multiple exist, ask which one)
     b) Which side? (top-center, left, right, etc.)
     c) Tip or base? (for triangles/rectangles placed on top)
   → If you DON'T have all info → Ask questions (strokes=[], done=false)
   → If you DO have all info → DRAW IMMEDIATELY

3. IF USER SAYS "draw [shape]" (circle, square, triangle, line):
   → Draw the complete shape in one step
   → Create anchors: center, top, bottom, left, right, corners

4. IF USER SAYS "draw [complex]" (house, person, tree):
   → Break into 2-3 stages
   → Do Stage 1 first
   → Store plan in anchors: "plan", "current_stage": 1, "total_stages": N
   → Ask: "I'll draw this in N stages. Stage 1 done. Continue?"

SPATIAL RELATIONSHIPS:
- "on top of" → Place ABOVE, use target's "top" Y coordinate
- "below" → Place BELOW, use target's "bottom" Y coordinate  
- "beside" → Place HORIZONTALLY adjacent (not overlapping)
- "inside" → Place INSIDE, use target's center, make smaller
- "that"/"it" → Use MOST RECENT shape (last in PREVIOUSLY DRAWN STROKES)
- "first [shape]" → Find "[shape]_1"
- "second [shape]" → Find "[shape]_2"
- "top [shape]" → Find shape with HIGHEST "top" Y coordinate

SHAPE CREATION:
- Circle: Use 20-30 points evenly spaced (angle 0° to 360°)
- Square/Rectangle: 4-5 points (corners + close)
- Triangle: 3-4 points (vertices + close)
- Always create anchors: center, top, bottom, left, right, corners

OUTPUT FORMAT (JSON only, no markdown):
{{
  "strokes": [[[x1, y1], [x2, y2], ...]],
  "anchors": {{
    "shape_center": [x, y],
    "shape_top": [x, y],
    "shape_bottom": [x, y],
    "shape_left": [x, y],
    "shape_right": [x, y]
  }},
  "labels": {{"stroke_0": "shape_name"}},
  "assistant_message": "Message to user",
  "done": false
}}

WHEN ASKING QUESTIONS:
{{
  "strokes": [],
  "anchors": {{}},
  "labels": {{}},
  "assistant_message": "I'd like to clarify: [question]",
  "done": false
}}

CONSTRAINTS:
- Max {MAX_STROKES_PER_STEP} strokes per step
- Max {MAX_POINTS_PER_STROKE} points per stroke
- Output ONLY valid JSON (no markdown, no comments, no extra text)

EXAMPLE - Drawing a square:
{{
  "strokes": [[[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6], [0.4, 0.4]]],
  "anchors": {{
    "square_center": [0.5, 0.5],
    "square_top": [0.5, 0.6],
    "square_bottom": [0.5, 0.4],
    "square_left": [0.4, 0.5],
    "square_right": [0.6, 0.5]
  }},
  "labels": {{"stroke_0": "square"}},
  "assistant_message": "I've drawn a square.",
  "done": false
}}

Now output ONLY the JSON object:"""

    if coordinate_system_info:
        prompt += f"\n\nADDITIONAL INFO:\n{coordinate_system_info}"
    
    return prompt
