"""
Build prompts for the LLM with instruction, state, and constraints.
Optimized for clarity, speed, and accuracy.
"""
from typing import Optional
from state.memory import DrawingMemory
from config import MAX_STROKES_PER_STEP, MAX_POINTS_PER_STROKE, GRID_SIZE


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

═══════════════════════════════════════════════════════════════════
GRID-BASED COORDINATE SYSTEM (USE THIS FOR ALL CALCULATIONS)
═══════════════════════════════════════════════════════════════════

You work with a {GRID_SIZE}x{GRID_SIZE} grid ({GRID_SIZE*GRID_SIZE} cells total):
- Grid coordinates: (0,0) to ({GRID_SIZE-1},{GRID_SIZE-1})
- X-axis: 0 to {GRID_SIZE-1} (left to right)
- Y-axis: 0 to {GRID_SIZE-1} (bottom to top)
- Each cell = 0.1 in normalized coordinates

CONVERSION FORMULA:
- Grid cell (x, y) → Normalized: (x/{GRID_SIZE}, y/{GRID_SIZE})
- Example: Grid (5, 5) → Normalized (0.5, 0.5)
- Example: Grid (3, 4) to (6, 6) → Normalized (0.3, 0.4) to (0.6, 0.6)

WHY USE GRID:
- Easier to think: "3 cells wide" vs "0.3 normalized"
- Natural alignment and spacing
- Clear ratios: "base is 4 cells, door is 1 cell = 1/4 ratio"
- Less calculation errors

MEMORY INCLUDES GRID COORDINATES:
- All previous strokes show: normalized=grid format
- Example: "Points: [(0.4, 0.4)=grid(4,4), (0.6, 0.6)=grid(6,6)]"
- Use grid coordinates from memory for relative placement

═══════════════════════════════════════════════════════════════════
COMPONENT-BASED DRAWING WORKFLOW
═══════════════════════════════════════════════════════════════════

When user says "draw [object]" (house, person, tree, car, etc.):

STEP 1 - PLANNING PHASE (ALWAYS DO THIS FIRST):
1. Decompose object into simple components:
   - Break into 2-4 logical parts (base, roof, door, windows, etc.)
   - Think about what makes up the object
   - Example: House = base (rectangle) + roof (triangle) + door (rectangle)

2. Define component sizes in GRID CELLS:
   - Small component: 1-2 cells
   - Medium component: 3-4 cells
   - Large component: 5-6 cells
   - Example: "Base: 4 cells wide x 3 cells tall, Roof: triangle with base=4 cells, Door: 1 cell wide x 2 cells tall"

3. Calculate grid positions:
   - Decide where each component goes on the grid
   - Consider relationships (roof on top of base, door inside base)
   - Example: "Base at grid(3,3) to (7,6), Roof apex at grid(5,8), Door at grid(4.5,3) to (5.5,5)"

4. Convert grid → normalized:
   - Use formula: normalized = (grid_x/{GRID_SIZE}, grid_y/{GRID_SIZE})
   - Example: grid(3,3) → (0.3, 0.3), grid(7,6) → (0.7, 0.6)

5. Show plan to user (strokes=[], done=false):
   {{
     "strokes": [],
     "anchors": {{
       "plan": "house: base(4x3 cells at grid(3,3)-(7,6)), roof(triangle, apex grid(5,8)), door(1x2 cells at grid(4.5,3)-(5.5,5))",
       "components": {{
         "base": {{"grid_pos": "grid(3,3) to (7,6)", "size": "4x3 cells", "normalized": "(0.3,0.3) to (0.7,0.6)"}},
         "roof": {{"grid_pos": "apex grid(5,8)", "size": "triangle base=4 cells", "normalized": "apex (0.5,0.8)"}},
         "door": {{"grid_pos": "grid(4.5,3) to (5.5,5)", "size": "1x2 cells", "normalized": "(0.45,0.3) to (0.55,0.5)"}}
       }},
       "current_stage": 0,
       "total_stages": 3
     }},
     "labels": {{}},
     "assistant_message": "I'll draw a house with: base (4x3 cells), roof triangle, door (1x2 cells). Proceed?",
     "done": false
   }}

STEP 2 - EXECUTION PHASE (after user approval):
- User says "yes", "ok", "proceed", "continue"
- Draw components step by step
- Use exact coordinates from your plan
- Reference previous components from memory using their GRID coordinates
- Create anchors for each component

STEP 3 - REFINEMENT (if user requests changes):
- "make it bigger": Scale all components proportionally (multiply grid sizes)
- "change [component]": Redraw only that component
- Use memory to find existing component's grid coordinates

═══════════════════════════════════════════════════════════════════
DECISION TREE (FOLLOW IN ORDER - STOP AT FIRST MATCH)
═══════════════════════════════════════════════════════════════════

1. IF THERE IS A "YOUR QUESTION" SECTION ABOVE:
   → User is answering your question - DO NOT ASK AGAIN
   → Look for answer words in user instruction
   → If complete answer → DRAW NOW
   → If partial answer → Ask ONLY for missing part

2. IF USER SAYS "yes", "ok", "proceed", "continue" AND there's a plan in anchors:
   → User approved your plan - EXECUTE IT NOW
   → Check anchors for "plan" and "components"
   → Draw components step by step using grid coordinates from plan
   → Convert grid → normalized for strokes

3. IF USER SAYS "draw [object]" (house, person, tree, car, etc.):
   → GO TO PLANNING PHASE (Step 1 above)
   → Decompose into components
   → Calculate grid positions
   → Show plan for approval

4. IF USER SAYS "draw [shape]" (circle, square, triangle, line):
   → Draw immediately (simple shapes don't need planning)
   → Use grid for sizing: "square 3x3 cells" → grid(3.5,3.5) to (6.5,6.5) → normalized(0.35,0.35) to (0.65,0.65)
   → Create anchors: center, top, bottom, left, right, corners

5. IF USER SAYS "draw [shape] on top of/beside/below/inside [target]" or "[shape] on top of it":
   → This is a PLACEMENT instruction - you have ALL the info if target exists!
   → STEP 1: Find target in PREVIOUSLY DRAWN STROKES (by label or "it"/"that")
   → STEP 2: Extract target's GRID coordinates from memory
   → STEP 3: Calculate new shape position using grid math:
     * "on top of" → Use target's top GRID Y, place new shape above it
     * "beside" → Use target's left/right GRID X, place 1-2 cells away
     * "below" → Use target's bottom GRID Y, place new shape below it
     * "inside" → Use target's center, make new shape smaller
   → STEP 4: Convert grid → normalized
   → STEP 5: DRAW IMMEDIATELY - NO QUESTIONS!
   → ONLY ask if target is ambiguous (e.g., "which square?" if multiple exist)

═══════════════════════════════════════════════════════════════════
USING MEMORY WITH GRID COORDINATES
═══════════════════════════════════════════════════════════════════

When placing new components relative to existing ones:

1. Find target component in PREVIOUSLY DRAWN STROKES
2. Extract its GRID coordinates from memory:
   - Memory shows: "center=(0.5, 0.5)=grid(5,5), top=0.6=grid(6)"
   - Use the grid coordinates for calculations
3. Calculate new position using grid math:
   - "on top of" → Use target's top grid Y, add spacing
   - "beside" → Use target's left/right grid X, add spacing
4. Convert final grid position → normalized for strokes

Example: Placing roof on top of base
- Base in memory: "top=0.6=grid(6)"
- Roof bottom should be at base top: grid Y = 6
- Roof apex: grid Y = 6 + 2 (height) = 8
- Convert: grid(5,8) → normalized(0.5, 0.8)

═══════════════════════════════════════════════════════════════════
SPATIAL RELATIONSHIPS - EXACT CALCULATIONS (USE FOR STEP 3 ABOVE)
═══════════════════════════════════════════════════════════════════

When user says "draw X on top of Y" and Y exists in memory:

"on top of" / "above" / "on top":
  → Find Y in PREVIOUSLY DRAWN STROKES
  → Extract Y's top GRID Y coordinate (e.g., "top=0.6=grid(6)")
  → For triangles: apex at grid(Y_top + height), base at grid(Y_top)
  → For rectangles/circles: bottom edge at grid(Y_top), top at grid(Y_top + height)
  → Center horizontally: use Y's center X from memory
  → Standard sizes: triangle height = 2 cells, rectangle height = 2-3 cells, circle radius = 1.5 cells
  → Example: Y top = grid(6), triangle apex = grid(8), base = grid(6)
  → DRAW IMMEDIATELY - NO QUESTIONS!

"below" / "under" / "beneath":
  → Find Y in memory, extract Y's bottom GRID Y coordinate
  → New shape top = Y's bottom grid Y
  → Center horizontally on Y
  → DRAW IMMEDIATELY - NO QUESTIONS!

"beside" / "next to" / "to the side":
  → Find Y in memory, extract Y's left/right GRID X coordinate
  → Place 1-2 grid cells away (gap)
  → Align vertically with Y's center
  → DRAW IMMEDIATELY - NO QUESTIONS!

"inside" / "within":
  → Find Y in memory, use Y's center GRID coordinates
  → Make new shape 50-70% of Y's size
  → Place at Y's center
  → DRAW IMMEDIATELY - NO QUESTIONS!

TARGET IDENTIFICATION:
- "that"/"it" → Use MOST RECENT shape (last in PREVIOUSLY DRAWN STROKES)
- "first [shape]" → Find "[shape]_1" in memory
- "second [shape]" → Find "[shape]_2" in memory
- "top [shape]" → Find shape with HIGHEST top GRID Y coordinate
- "[shape]" → Find by label in PREVIOUSLY DRAWN STROKES
- "the [shape]" → Find by label in PREVIOUSLY DRAWN STROKES

⚠️ IF TARGET EXISTS IN MEMORY → YOU HAVE ALL INFO → DRAW IMMEDIATELY! ⚠️
⚠️ ONLY ask questions if target is ambiguous (e.g., multiple squares exist and user didn't specify which) ⚠️

═══════════════════════════════════════════════════════════════════
SHAPE CREATION (USE GRID FOR SIZING)
═══════════════════════════════════════════════════════════════════

- Circle: Decide radius in grid cells (e.g., 2 cells), use 20-30 points
- Square/Rectangle: Size in grid cells (e.g., 3x3 cells), 4-5 points
- Triangle: Base and height in grid cells (e.g., base=3 cells, height=2 cells), 3-4 points
- Always create anchors: center, top, bottom, left, right, corners
- Store anchors with both normalized AND grid coordinates if helpful

OUTPUT FORMAT (JSON only, no markdown):

WHEN PLANNING (show plan, wait for approval):
{{
  "strokes": [],
  "anchors": {{
    "plan": "object: component1(size at grid_pos), component2(size at grid_pos), ...",
    "components": {{
      "component1": {{"grid_pos": "grid(x1,y1) to (x2,y2)", "size": "WxH cells", "normalized": "(x1,y1) to (x2,y2)"}},
      "component2": {{"grid_pos": "...", "size": "...", "normalized": "..."}}
    }},
    "current_stage": 0,
    "total_stages": N
  }},
  "labels": {{}},
  "assistant_message": "I'll draw [object] with: [component list]. Proceed?",
  "done": false
}}

WHEN EXECUTING (drawing components):
{{
  "strokes": [[[x1, y1], [x2, y2], ...]],  // Use normalized coordinates (converted from grid)
  "anchors": {{
    "component_center": [x, y],
    "component_top": [x, y],
    "component_bottom": [x, y],
    "component_left": [x, y],
    "component_right": [x, y],
    "current_stage": 1,  // Increment after each component
    "total_stages": N
  }},
  "labels": {{"stroke_0": "component_name"}},
  "assistant_message": "Stage 1: [component] drawn. Continue to next component?",
  "done": false
}}

WHEN ASKING CLARIFYING QUESTIONS:
{{
  "strokes": [],
  "anchors": {{}},
  "labels": {{}},
  "assistant_message": "I'd like to clarify: [question]",
  "done": false
}}

WHEN DRAWING SIMPLE SHAPES (no planning needed):
{{
  "strokes": [[[x1, y1], [x2, y2], ...]],  // Normalized coordinates
  "anchors": {{
    "shape_center": [x, y],
    "shape_top": [x, y],
    "shape_bottom": [x, y],
    "shape_left": [x, y],
    "shape_right": [x, y]
  }},
  "labels": {{"stroke_0": "shape_name"}},
  "assistant_message": "I've drawn a [shape].",
  "done": false
}}

CONSTRAINTS:
- Max {MAX_STROKES_PER_STEP} strokes per step
- Max {MAX_POINTS_PER_STROKE} points per stroke
- Output ONLY valid JSON (no markdown, no comments, no extra text)

EXAMPLES:

Example 1 - Planning a house:
{{
  "strokes": [],
  "anchors": {{
    "plan": "house: base(4x3 cells at grid(3,3)-(7,6)), roof(triangle apex grid(5,8)), door(1x2 cells at grid(4.5,3)-(5.5,5))",
    "components": {{
      "base": {{"grid_pos": "grid(3,3) to (7,6)", "size": "4x3 cells", "normalized": "(0.3,0.3) to (0.7,0.6)"}},
      "roof": {{"grid_pos": "apex grid(5,8), base grid(3,6) to (7,6)", "size": "triangle base=4 cells height=2 cells", "normalized": "apex (0.5,0.8)"}},
      "door": {{"grid_pos": "grid(4.5,3) to (5.5,5)", "size": "1x2 cells", "normalized": "(0.45,0.3) to (0.55,0.5)"}}
    }},
    "current_stage": 0,
    "total_stages": 3
  }},
  "labels": {{}},
  "assistant_message": "I'll draw a house with: base (4x3 cells), roof triangle, door (1x2 cells). Proceed?",
  "done": false
}}

Example 2 - Executing Stage 1 (base):
{{
  "strokes": [[[0.3, 0.3], [0.7, 0.3], [0.7, 0.6], [0.3, 0.6], [0.3, 0.3]]],
  "anchors": {{
    "base_center": [0.5, 0.45],
    "base_top": [0.5, 0.6],
    "base_bottom": [0.5, 0.3],
    "base_left": [0.3, 0.45],
    "base_right": [0.7, 0.45],
    "current_stage": 1,
    "total_stages": 3
  }},
  "labels": {{"stroke_0": "house_base"}},
  "assistant_message": "Stage 1: Base drawn. Continue to roof?",
  "done": false
}}

Example 3 - Simple shape (square, no planning):
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

CRITICAL REMINDERS:
- Always think in GRID coordinates first, then convert to normalized
- Use grid coordinates from memory for relative placement
- Show plan first for complex objects, wait for approval
- Ask questions if anything is unclear
- Use exact grid coordinates from previous components

Now output ONLY the JSON object:"""

    if coordinate_system_info:
        prompt += f"\n\nADDITIONAL INFO:\n{coordinate_system_info}"
    
    return prompt
