"""
Verification rules generator for coordinate validation.
"""
from typing import Dict, Any
from state.memory import DrawingMemory
from config import GRID_SIZE


def get_verification_rules(component_type: str, component_name: str, 
                          memory: DrawingMemory) -> str:
    """
    Generate verification rules for a component based on its type and memory.
    
    Args:
        component_type: Type of component (e.g., "roof", "door", "window")
        component_name: Name of component (e.g., "house_roof", "house_door")
        memory: Current drawing memory
    
    Returns:
        String of verification rules
    """
    rules = []
    
    # Base rules for all components
    rules.append("1. All coordinates must be in normalized range [0.0, 1.0]")
    rules.append("2. Component must fit within drawing bounds")
    
    # Component-specific rules
    if component_type.lower() in ["roof", "rooftop", "top"]:
        # Roof should be above base
        if memory.strokes_history:
            # Find base/house base in memory
            for stroke in memory.strokes_history:
                label = stroke.label or ""
                if "base" in label.lower() or "house" in label.lower():
                    if stroke.points:
                        ys = [p[1] for p in stroke.points]
                        base_top = max(ys)
                        rules.append(f"3. Roof bottom Y coordinate must be >= {base_top:.3f} (base top)")
                        rules.append("4. Roof should be positioned above the base")
                    break
    
    elif component_type.lower() in ["door", "entrance"]:
        # Door should be inside base
        if memory.strokes_history:
            for stroke in memory.strokes_history:
                label = stroke.label or ""
                if "base" in label.lower() or "house" in label.lower():
                    if stroke.points:
                        xs = [p[0] for p in stroke.points]
                        ys = [p[1] for p in stroke.points]
                        base_left = min(xs)
                        base_right = max(xs)
                        base_bottom = min(ys)
                        base_top = max(ys)
                        rules.append(f"3. Door center X must be between {base_left:.3f} and {base_right:.3f} (base left/right)")
                        rules.append(f"4. Door bottom Y must be >= {base_bottom:.3f} (base bottom)")
                        rules.append(f"5. Door top Y must be <= {base_top:.3f} (base top)")
                        rules.append("6. Door must be completely inside the base")
                    break
    
    elif component_type.lower() in ["window", "windows"]:
        # Windows should be on base walls (not on roof)
        if memory.strokes_history:
            for stroke in memory.strokes_history:
                label = stroke.label or ""
                if "base" in label.lower() or "house" in label.lower():
                    if stroke.points:
                        xs = [p[0] for p in stroke.points]
                        ys = [p[1] for p in stroke.points]
                        base_left = min(xs)
                        base_right = max(xs)
                        base_bottom = min(ys)
                        base_top = max(ys)
                        rules.append(f"3. Window must be on base walls (X between {base_left:.3f} and {base_right:.3f})")
                        rules.append(f"4. Window Y must be between {base_bottom:.3f} and {base_top:.3f} (base bottom/top)")
                        rules.append("5. Window should not overlap with door")
                    break
    
    elif component_type.lower() in ["base", "foundation", "body"]:
        # Base should be at bottom or center
        rules.append("3. Base should be positioned in lower or center area of canvas")
        rules.append("4. Base should have reasonable size (not too small or too large)")
    
    # General spatial relationship rules
    if memory.strokes_history:
        rules.append("5. Component should not overlap with existing components (unless specified)")
        rules.append("6. Component should maintain proper proportions relative to existing components")
    
    return "\n".join(rules)
