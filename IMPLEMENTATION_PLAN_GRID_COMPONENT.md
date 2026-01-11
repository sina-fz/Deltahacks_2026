# Implementation Plan: Grid + Component-Based System with Planning

## Requirements Summary
1. ✅ Grid-based coordinate system (10x10 grid)
2. ✅ Component-based decomposition with ratios
3. ✅ Planning phase with user approval
4. ✅ Memory includes both normalized AND grid coordinates
5. ✅ Flexible (no hardcoded object specs)
6. ✅ LLM can ask questions for clarity

## Implementation Steps

### Step 1: Add Grid Configuration
- Add `GRID_SIZE = 10` to `config.py`
- Add grid conversion helper functions

### Step 2: Enhance Memory State Summary
- Update `state/memory.py` `get_state_summary()` to include grid coordinates
- Show both normalized AND grid coordinates for all points
- Format: "Points: [(0.4, 0.4) = grid(4, 4), ...]"

### Step 3: Update Prompt Builder
- Add comprehensive grid system explanation
- Add component-based decomposition workflow
- Add planning phase instructions
- Add grid conversion formulas
- Add memory lookup with grid coordinates
- Keep flexible (no hardcoded specs)

### Step 4: Update Main Loop
- Enhance planning phase detection
- Better handling of plan approval
- Store plan in memory properly

## Files to Modify
1. `config.py` - Add grid configuration
2. `state/memory.py` - Add grid coordinates to state summary
3. `agent/prompt_builder.py` - Major update with grid + component system
4. `main_loop.py` - Enhance planning phase handling

## Expected Flow

```
User: "draw a house"
    ↓
LLM Planning Phase:
  - Decomposes: base, roof, door
  - Defines ratios: base 4x3 cells, roof triangle, door 1x2 cells
  - Calculates grid positions
  - Shows plan to user
    ↓
User: "yes" or "make it bigger"
    ↓
LLM Execution Phase:
  - Converts grid → normalized
  - Draws components step by step
  - Uses memory grid coordinates for relative placement
    ↓
Memory Update:
  - Stores both normalized AND grid coordinates
  - Next query sees: "base at grid(3,3) to (7,6) = normalized(0.3,0.3) to (0.7,0.6)"
```
