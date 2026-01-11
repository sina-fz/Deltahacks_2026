"""
Build prompts for the LLM with instruction, state, and constraints.
Simple, logical prompt that gives exact coordinate calculation rules.
"""
from typing import Optional, List, Tuple, Dict, Any
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
    
    # If there's a previous question, add context for answer recognition
    answer_context = ""
    if memory.last_question:
        answer_context = f"\n\nPREVIOUS QUESTION: \"{memory.last_question}\"\nThe user's instruction is likely an answer. Extract and use it."
    
    # Check if we're executing a plan
    continuation_context = ""
    if instruction.lower().strip() in ["execute the plan", "execute the plan and draw all components", "yes", "ok", "proceed"]:
        plan = memory.anchors.get("plan", "")
        components = memory.anchors.get("components", {})
        component_drawn = memory.anchors.get("component_drawn")
        components_remaining = memory.anchors.get("components_remaining", [])
        
        if plan:
            if component_drawn and components_remaining:
                # Continuing multi-component drawing
                next_component = components_remaining[0] if components_remaining else None
                if next_component:
                    continuation_context = f"\n\nCONTINUE DRAWING:\nPlan: {plan}\nAlready drawn: {component_drawn}\nNext component to draw: {next_component}\nRemaining after this: {components_remaining[1:]}\n\n⚠️ Draw ONLY {next_component} in this response. The system will call you again for the next component."
                else:
                    # All components drawn
                    continuation_context = f"\n\nPlan complete! All components have been drawn."
            else:
                # First component
                all_components = list(components.keys()) if isinstance(components, dict) else components
                first_component = all_components[0] if all_components else "first component"
                continuation_context = f"\n\nEXECUTE PLAN NOW:\nPlan: {plan}\nComponents: {components}\n\n⚠️ Draw ONLY the FIRST component ({first_component}) in this response. The system will call you again for the next component."
    
    prompt = f"""You are a drawing assistant. Draw on a {GRID_SIZE}x{GRID_SIZE} grid.

USER INSTRUCTION: {instruction}{answer_context}{continuation_context}

CURRENT DRAWING STATE:
{state_summary}

COORDINATE SYSTEM:
- Grid: {GRID_SIZE}x{GRID_SIZE} cells (0 to {GRID_SIZE-1} in each dimension)
- Origin: (0,0) = bottom-left, ({GRID_SIZE-1},{GRID_SIZE-1}) = top-right
- ⚠️ CRITICAL: ALL coordinates in JSON output MUST be NORMALIZED [0.0, 1.0] ⚠️
- Conversion formula: normalized = grid_coordinate / {GRID_SIZE}
- Examples:
  * grid(0, 0) → normalized(0.0, 0.0)
  * grid(5, 5) → normalized(0.5, 0.5)
  * grid(9, 9) → normalized(0.9, 0.9)
- ❌ WRONG: [5, 5] (grid coordinates)
- ✅ CORRECT: [0.5, 0.5] (normalized coordinates)

COORDINATE CALCULATION LOGIC:

1. NEW OBJECT (no reference):
   - Think in grid coordinates first (for planning)
   - Center around grid({GRID_SIZE//2}, {GRID_SIZE//2}) = normalized(0.5, 0.5) if first object
   - Size: small=1-2 cells, medium=3-4 cells, large=5-6 cells
   - ⚠️ MUST CONVERT to normalized before output:
     * Example: grid(4, 6) → normalized(0.4, 0.6)
     * Example: grid(5, 5) → normalized(0.5, 0.5)
     * Formula: x_norm = grid_x / {GRID_SIZE}, y_norm = grid_y / {GRID_SIZE}

2. RELATIVE POSITIONING (using existing objects):
   STEP 1 - SPATIAL REASONING (visualize first):
   - Before calculating, visualize: "Where would this component naturally attach/connect to the base object?"
   - Think spatially: "How do these parts connect in reality?" (not just mathematically)
   - Example: "Ears attach to the SIDES of a head, not on top" → visualize left ear on left side, right ear on right side
   
   STEP 2 - EXTRACT TARGET'S BOUNDING BOX:
   - Find target object in CURRENT DRAWING STATE (look for labels like "head_1", "body_1", etc.)
   - Extract anchors: target_left, target_right, target_top, target_bottom (these are in normalized [0.0, 1.0])
   - Convert to grid for calculation: grid_x = normalized_x * {GRID_SIZE}
   - Example: If head_1_left = 0.4 (normalized), then grid_left = 0.4 * 10 = 4
   
   STEP 3 - CALCULATE NEW POSITION (edge-based math):
   - Use edge-based positioning (components connect at edges, not centers):
     * "to the left of": new_right_edge = target_left_edge - spacing
       spacing = 1-2 cells (normalized: 0.1-0.2)
     * "to the right of": new_left_edge = target_right_edge + spacing
     * "on top of": new_bottom_edge = target_top_edge + spacing
       spacing = 0.5-1 cell (normalized: 0.05-0.1)
     * "below": new_top_edge = target_bottom_edge - spacing
   - Calculate in grid, then convert to normalized
   
   STEP 4 - VALIDATION CHECK:
   - Before outputting: "Does this placement make spatial sense?"
   - "Would these components connect naturally in reality?"
   - "Are they positioned relative to each other, not floating independently?"
   
   STEP 5 - CONVERT TO NORMALIZED:
   - ⚠️ MUST CONVERT all coordinates to normalized [0.0, 1.0] before output
   - Formula: normalized = grid_coordinate / {GRID_SIZE}

3. MULTIPLE SIMILAR COMPONENTS (two ears, two eyes, etc.):
   STEP 1 - SPATIAL REASONING:
   - Visualize: "How are these arranged in reality?" 
   - Think: "Two ears on a head - where would they naturally be?" (left and right SIDES, not on top)
   - Think: "Two eyes on a face - where would they naturally be?" (left and right SIDES, not stacked)
   
   STEP 2 - EXTRACT BASE OBJECT'S EDGES:
   - Find base object (e.g., "head_1") in CURRENT DRAWING STATE
   - Extract: head_left, head_right, head_top, head_bottom (normalized coordinates)
   - Convert to grid: head_left_grid = head_left * {GRID_SIZE}
   
   STEP 3 - CALCULATE POSITIONS AT DIFFERENT LOCATIONS:
   - Left component: position at base's LEFT side
     * left_component_right_edge = base_left_edge - 0.5 cell (in grid)
     * Calculate left_component's full position from this edge
   - Right component: position at base's RIGHT side
     * right_component_left_edge = base_right_edge + 0.5 cell (in grid)
     * Calculate right_component's full position from this edge
   - Both at similar Y level (aligned horizontally, not vertically stacked)
   
   STEP 4 - VALIDATION:
   - "Are they at DIFFERENT X positions?" (left vs right, not same X)
   - "Are they at similar Y positions?" (same level, not stacked)
   - "Would this look natural?" (ears on sides of head, not on top)
   
   STEP 5 - CONVERT TO NORMALIZED:
   - Convert all grid coordinates to normalized [0.0, 1.0]

4. COMPLEX OBJECTS (house, cat, person, etc.):
   STEP 1 - DECOMPOSE:
   - Decompose into shapes using your knowledge
   - Think: "What shapes make this up? How do they connect?"
   
   STEP 2 - PLAN:
   - Create plan with components and sizes
   - Think about relative positioning: "Head sits ON body, ears on SIDES of head"
   
   STEP 3 - DRAW (after approval):
   ⚠️ CRITICAL: DRAW ONE COMPONENT PER RESPONSE ⚠️
   
   When executing a plan, you draw components INCREMENTALLY:
   - First response: Draw ONLY the first component (e.g., body)
   - System will call you again with updated memory (body now exists)
   - Second response: Draw ONLY the next component (e.g., head) relative to body
   - System will call you again with updated memory (body + head now exist)
   - Continue until all components drawn
   
   For EACH component you draw, you MUST:
   
   a) STATE WHAT YOU'RE DRAWING:
      - "Drawing [component] (e.g., 'body', 'head', 'left ear')"
   
   b) IDENTIFY THE BASE/REFERENCE:
      - "Positioning it relative to [base component]" (e.g., "head relative to body", "left ear relative to head")
      - If it's the first component, state: "This is the base component, centered at grid(5,5)"
   
   c) EXTRACT BASE'S COORDINATES FROM MEMORY:
      - Look in CURRENT DRAWING STATE for the base component's anchors
      - Extract: base_left, base_right, base_top, base_bottom (normalized coordinates)
      - Convert to grid: base_left_grid = base_left * {GRID_SIZE}
      - Example: "Found body_1_left = 0.4 (normalized) = grid 4"
   
   d) CALCULATE NEW POSITION:
      - Use edge-based math based on how components connect
      - Example: "Head sits ON body → head_bottom = body_top"
      - Example: "Left ear on LEFT SIDE of head → left_ear_right_edge = head_left_edge - 0.5 cell"
      - Calculate in grid coordinates first
   
   e) DETERMINE SIZE:
      - Use consistent sizing: small=1-2 cells, medium=3-4 cells, large=5-6 cells
      - Check ratio: "Head should be smaller than body" (e.g., body=4 cells, head=2 cells)
   
   f) VALIDATE:
      - "Does this placement make spatial sense?"
      - "Is the size proportional to the base?"
      - "Are they properly connected (touching or with small gap)?"
   
   g) CONVERT TO NORMALIZED:
      - Convert all grid coordinates to normalized [0.0, 1.0]
      - Formula: normalized = grid_coordinate / {GRID_SIZE}
   
   h) OUTPUT THE STROKE:
      - Add the stroke to your output
      - Create anchors for this component (center, top, bottom, left, right)
      - Set "component_drawn": "[component name]" in anchors
      - Set "components_remaining": ["list", "of", "remaining", "components"]
      - If more components remain, set "assistant_message": "Drew [component]. Continuing with next component..."
   
   After drawing one component, STOP. The system will call you again to draw the next one.
   
   Components don't exist in isolation - they CONNECT. Each component builds on the previous ones.

RATIO AND CONSISTENCY CHECKS:
- Keep object proportions consistent: if head is 2 cells wide, body should be 2-3 cells wide
- Same object type should have similar sizes: all eyes same size, all ears same size
- Components of same object should maintain relative sizes: head < body, arms < body
- Check: before drawing, verify sizes make sense relative to existing objects

MEMORY (COMMUTATIVE - everything stored exactly):
- All strokes stored with exact coordinates
- All anchors stored: center, top, bottom, left, right for each shape
- Labels identify each stroke
- Use anchors to find existing objects and calculate relative positions
- Memory is cumulative - everything drawn remains available

OUTPUT FORMAT (JSON only, no comments):
⚠️ ALL COORDINATES MUST BE NORMALIZED [0.0, 1.0] - NOT grid coordinates! ⚠️

When drawing multiple components, think through each one step-by-step:

Example - Drawing a cat incrementally:

FIRST RESPONSE (draw body only):
{{
  "strokes": [
    [[0.3, 0.4], [0.7, 0.4], [0.7, 0.6], [0.3, 0.6], [0.3, 0.4]]
  ],
  "anchors": {{
    "body_1_center": [0.5, 0.5],
    "body_1_top": [0.5, 0.6],
    "body_1_bottom": [0.5, 0.4],
    "body_1_left": [0.3, 0.5],
    "body_1_right": [0.7, 0.5],
    "component_drawn": "body",
    "components_remaining": ["head", "ear_left", "ear_right", "eye_left", "eye_right"]
  }},
  "labels": {{
    "stroke_0": "body"
  }},
  "assistant_message": "Drew body. Continuing with next component...",
  "done": false
}}

SECOND RESPONSE (draw head on top of body):
{{
  "strokes": [
    [[0.4, 0.6], [0.6, 0.6], [0.6, 0.8], [0.4, 0.8], [0.4, 0.6]]
  ],
  "anchors": {{
    "head_1_center": [0.5, 0.7],
    "head_1_top": [0.5, 0.8],
    "head_1_bottom": [0.5, 0.6],
    "head_1_left": [0.4, 0.7],
    "head_1_right": [0.6, 0.7],
    "component_drawn": "head",
    "components_remaining": ["ear_left", "ear_right", "eye_left", "eye_right"]
  }},
  "labels": {{
    "stroke_0": "head"
  }},
  "assistant_message": "Drew head on top of body. Continuing with next component...",
  "done": false
}}

... and so on for remaining components.

❌ WRONG: "strokes": [[[5, 5], [7, 5], ...]]  (grid coordinates)
✅ CORRECT: "strokes": [[[0.5, 0.5], [0.7, 0.5], ...]]  (normalized)

For complex objects, output plan first:
{{
  "strokes": [],
  "anchors": {{
    "plan": "Description of components",
    "components": {{"component1": "description", "component2": "description"}},
    "current_stage": 0,
    "total_stages": 1
  }},
  "labels": {{}},
  "assistant_message": "I'll draw [object] with: [components]. Should I proceed?",
  "done": false
}}

CONSTRAINTS:
- Max {MAX_STROKES_PER_STEP} strokes per step
- Max {MAX_POINTS_PER_STROKE} points per stroke
- Output ONLY valid JSON (no comments, no markdown)

Now output ONLY the JSON object:"""

    if coordinate_system_info:
        prompt += f"\n\nADDITIONAL INFO:\n{coordinate_system_info}"
    
    return prompt


def build_repair_prompt(
    instruction: str,
    memory: DrawingMemory,
    failed_strokes: List[List[Tuple[float, float]]],
    failed_labels: Dict[str, str],
    failed_anchors: Dict[str, Any],
    issues: str
) -> str:
    """
    Build a repair prompt for the LLM to fix issues with generated strokes.
    
    Args:
        instruction: Original user instruction
        memory: Current drawing memory/state
        failed_strokes: Strokes that failed validation
        failed_labels: Labels for failed strokes
        failed_anchors: Anchors for failed strokes
        issues: Description of validation issues
    
    Returns:
        Repair prompt string
    """
    state_summary = memory.get_state_summary()
    
    prompt = f"""Your previous drawing had issues. Please fix them.

ORIGINAL INSTRUCTION: {instruction}

CURRENT DRAWING STATE:
{state_summary}

YOUR PREVIOUS ATTEMPT (had issues):
Strokes: {len(failed_strokes)} strokes
Labels: {failed_labels}

{issues}

REPAIR INSTRUCTIONS:
1. Read the issues carefully
2. Fix ONLY the problems listed above
3. Keep the same structure (same components, same plan)
4. Output corrected JSON with ALL coordinates in normalized [0.0, 1.0] format
5. Ensure:
   - Paired components (ears, eyes) are at DIFFERENT X positions
   - Components have proper spacing (not overlapping)
   - Sizes are consistent and reasonable
   - Components are positioned relative to each other, not all centered

OUTPUT:
Return the CORRECTED JSON only (same format as before):
{{
  "strokes": [ ... corrected strokes ... ],
  "anchors": {{ ... same anchors ... }},
  "labels": {{ ... same labels ... }},
  "assistant_message": "Fixed [brief description of what you changed]",
  "done": false
}}

⚠️ CRITICAL: Output ONLY valid JSON. No comments, no markdown."""
    
    return prompt
