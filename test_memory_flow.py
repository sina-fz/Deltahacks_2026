#!/usr/bin/env python3
"""Test script to verify memory is being sent to LLM correctly."""

from state.memory import DrawingMemory
from agent.prompt_builder import build_prompt

def test_memory_flow():
    """Test that memory is properly included in prompts."""
    print("=== MEMORY FLOW VERIFICATION TEST ===\n")
    
    # Create memory and add shapes
    m = DrawingMemory()
    
    print("Step 1: Adding square...")
    m.add_strokes([[(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6), (0.4, 0.4)]], {'stroke_0': 'square'})
    print(f"  Strokes: {len(m.strokes_history)}, Anchors: {len(m.anchors)}")
    
    print("\nStep 2: Building prompt for 'add triangle on top'...")
    prompt1 = build_prompt('add triangle on top', m)
    has_state1 = 'CURRENT DRAWING STATE:' in prompt1
    has_square1 = 'SQUARE' in prompt1
    print(f"  Has state section: {has_state1}")
    print(f"  Has square: {has_square1}")
    
    print("\nStep 3: Adding triangle...")
    m.add_strokes([[(0.5, 0.6), (0.45, 0.75), (0.55, 0.75), (0.5, 0.6)]], {'stroke_0': 'triangle'})
    print(f"  Strokes: {len(m.strokes_history)}, Anchors: {len(m.anchors)}")
    
    print("\nStep 4: Building prompt for 'add circle beside square'...")
    prompt2 = build_prompt('add circle beside square', m)
    has_state2 = 'CURRENT DRAWING STATE:' in prompt2
    has_square2 = 'SQUARE' in prompt2
    has_triangle2 = 'TRIANGLE' in prompt2
    print(f"  Has state section: {has_state2}")
    print(f"  Has square: {has_square2}")
    print(f"  Has triangle: {has_triangle2}")
    
    # Extract state sections
    if has_state2:
        state_section = prompt2.split('CURRENT DRAWING STATE:')[1].split('COORDINATE SYSTEM:')[0]
        print(f"\n  State section length: {len(state_section)} chars")
        print(f"  Has point coordinates: {'Points:' in state_section}")
        print(f"  Has anchors: {'ANCHORS' in state_section}")
    
    print("\n=== VERIFICATION SUMMARY ===")
    all_checks = [
        has_state1, has_square1,
        has_state2, has_square2, has_triangle2
    ]
    
    if all(all_checks):
        print("[PASS] ALL CHECKS PASSED - Memory is being sent correctly!")
        return True
    else:
        print("[FAIL] SOME CHECKS FAILED - Memory may not be sent correctly!")
        print(f"   Failed checks: {[i for i, check in enumerate(all_checks) if not check]}")
        return False

if __name__ == '__main__':
    test_memory_flow()
