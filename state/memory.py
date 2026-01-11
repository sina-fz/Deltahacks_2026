"""
State and memory management for the drawing system.
Maintains history of strokes, anchors, and labels.
"""
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import json


@dataclass
class Stroke:
    """Represents a single stroke (polyline)."""
    id: int
    points: List[Tuple[float, float]]  # Normalized coordinates [0.0, 1.0]
    label: Optional[str] = None
    state: str = "confirmed"  # "preview" or "confirmed"


@dataclass
class DrawingMemory:
    """Maintains the state of what has been drawn."""
    strokes_history: List[Stroke] = field(default_factory=list)
    features: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # label -> {stroke_ids, anchors}
    anchors: Dict[str, Any] = field(default_factory=dict)  # anchor_name -> value (point or scalar)
    last_position: Tuple[float, float] = (0.5, 0.5)  # Normalized [0.0, 1.0]
    stop_flag: bool = False
    _next_stroke_id: int = 0
    last_question: Optional[str] = None  # Store the last question asked by LLM

    def add_strokes(self, strokes: List[List[Tuple[float, float]]], 
                   labels: Optional[Dict[str, str]] = None,
                   state: str = "confirmed") -> List[int]:
        """
        Add new strokes to history.
        Automatically numbers shapes (square_1, square_2, etc.) and generates side anchors.
        Returns list of stroke IDs.
        """
        stroke_ids = []
        labels = labels or {}
        
        # Count existing shapes by type for naming
        shape_counts = {}
        for stroke in self.strokes_history:
            if stroke.label:
                # Extract base type (e.g., "square" from "square_1" or "square")
                base_label = stroke.label.split('_')[0]
                shape_counts[base_label] = shape_counts.get(base_label, 0) + 1
        
        for i, points in enumerate(strokes):
            stroke_id = self._next_stroke_id
            label_key = f"stroke_{i}"
            label = labels.get(label_key) or labels.get(str(i)) or None
            
            # If label exists, number it if needed
            if label:
                base_label = label.split('_')[0] if '_' in label else label
                count = shape_counts.get(base_label, 0)
                if count > 0:
                    # This is not the first of this type
                    numbered_label = f"{base_label}_{count + 1}"
                else:
                    numbered_label = f"{base_label}_1"
                shape_counts[base_label] = shape_counts.get(base_label, 0) + 1
                label = numbered_label
            
            stroke = Stroke(id=stroke_id, points=points, label=label, state=state)
            self.strokes_history.append(stroke)
            stroke_ids.append(stroke_id)
            self._next_stroke_id += 1
            
            # Auto-generate side anchors if stroke has points
            if points and label:
                self._auto_generate_side_anchors(stroke, label)
            
            # Update last position to end of stroke
            if points:
                self.last_position = points[-1]
        
        return stroke_ids
    
    def _auto_generate_side_anchors(self, stroke: Stroke, label: str) -> None:
        """
        Auto-generate side anchors for a stroke if LLM didn't provide them.
        Ensures all sides (top, bottom, left, right, corners) are tracked.
        """
        if not stroke.points:
            return
        
        xs = [p[0] for p in stroke.points]
        ys = [p[1] for p in stroke.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # Extract base name and shape number
        if '_' in label and label.split('_')[-1].isdigit():
            parts = label.split('_')
            base_name = '_'.join(parts[:-1])
            shape_num = parts[-1]
        else:
            base_name = label
            shape_num = "1"
        
        # Generate comprehensive side anchors
        side_anchors = {
            f"{base_name}_{shape_num}_center": [center_x, center_y],
            f"{base_name}_{shape_num}_top": [center_x, max_y],
            f"{base_name}_{shape_num}_bottom": [center_x, min_y],
            f"{base_name}_{shape_num}_left": [min_x, center_y],
            f"{base_name}_{shape_num}_right": [max_x, center_y],
            f"{base_name}_{shape_num}_top_left": [min_x, max_y],
            f"{base_name}_{shape_num}_top_right": [max_x, max_y],
            f"{base_name}_{shape_num}_bottom_left": [min_x, min_y],
            f"{base_name}_{shape_num}_bottom_right": [max_x, min_y],
        }
        
        # Only add if not already present (don't override LLM's anchors)
        for key, value in side_anchors.items():
            if key not in self.anchors:
                self.anchors[key] = value

    def update_anchors(self, anchors: Dict[str, Any]) -> None:
        """Update anchor points/values."""
        self.anchors.update(anchors)

    def update_features(self, labels: Dict[str, str], stroke_ids: List[int]) -> None:
        """
        Update feature mapping: label -> stroke_ids.
        """
        for label_key, label_name in labels.items():
            if label_name:
                if label_name not in self.features:
                    self.features[label_name] = {"stroke_ids": [], "anchors": {}}
                # Find corresponding stroke ID
                try:
                    idx = int(label_key.split("_")[-1]) if "_" in label_key else int(label_key)
                    if idx < len(stroke_ids):
                        stroke_id = stroke_ids[idx]
                        if stroke_id not in self.features[label_name]["stroke_ids"]:
                            self.features[label_name]["stroke_ids"].append(stroke_id)
                except (ValueError, IndexError):
                    pass

    def get_state_summary(self) -> str:
        """
        Generate a comprehensive string summary of current state for LLM prompts.
        Includes ALL strokes with their actual point coordinates and ALL anchors.
        """
        parts = []
        
        if self.strokes_history:
            parts.append(f"PREVIOUSLY DRAWN STROKES ({len(self.strokes_history)} total):")
            
            # Group by shape label for clarity
            shape_groups = {}
            for i, stroke in enumerate(self.strokes_history):
                if not stroke.points:
                    continue
                
                label = stroke.label or f"unlabeled_{i}"
                if label not in shape_groups:
                    shape_groups[label] = []
                shape_groups[label].append((i, stroke))
            
            # Display ALL strokes with their actual coordinates
            for label, strokes_list in sorted(shape_groups.items()):
                for i, stroke in strokes_list:
                    # Calculate bounding box
                    xs = [p[0] for p in stroke.points]
                    ys = [p[1] for p in stroke.points]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    center_x = (min_x + max_x) / 2
                    center_y = (min_y + max_y) / 2
                    
                    # Include actual point coordinates with grid coordinates
                    # For strokes with <= 10 points, show all points
                    # For larger strokes, show first 3, ..., last 3
                    from config import GRID_SIZE
                    
                    if len(stroke.points) <= 10:
                        points_with_grid = []
                        for p in stroke.points:
                            grid_x = int(p[0] * GRID_SIZE)
                            grid_y = int(p[1] * GRID_SIZE)
                            points_with_grid.append(f"({p[0]:.3f}, {p[1]:.3f})=grid({grid_x},{grid_y})")
                        points_str = ", ".join(points_with_grid)
                    else:
                        first_three = []
                        for p in stroke.points[:3]:
                            grid_x = int(p[0] * GRID_SIZE)
                            grid_y = int(p[1] * GRID_SIZE)
                            first_three.append(f"({p[0]:.3f}, {p[1]:.3f})=grid({grid_x},{grid_y})")
                        last_three = []
                        for p in stroke.points[-3:]:
                            grid_x = int(p[0] * GRID_SIZE)
                            grid_y = int(p[1] * GRID_SIZE)
                            last_three.append(f"({p[0]:.3f}, {p[1]:.3f})=grid({grid_x},{grid_y})")
                        points_str = f"{', '.join(first_three)}, ..., {', '.join(last_three)} ({len(stroke.points)} total points)"
                    
                    # Calculate grid coordinates for bounding box
                    grid_min_x = int(min_x * GRID_SIZE)
                    grid_max_x = int(max_x * GRID_SIZE)
                    grid_min_y = int(min_y * GRID_SIZE)
                    grid_max_y = int(max_y * GRID_SIZE)
                    grid_center_x = int(center_x * GRID_SIZE)
                    grid_center_y = int(center_y * GRID_SIZE)
                    
                    # Build stroke info line
                    if len(strokes_list) == 1:
                        parts.append(f"  {label.upper()} (stroke {i}, ID: {stroke.id}):")
                    else:
                        parts.append(f"  {label.upper()}_{i} (stroke {i}, ID: {stroke.id}):")
                    
                    parts.append(f"    Bounding box: center=({center_x:.3f}, {center_y:.3f})=grid({grid_center_x},{grid_center_y}), top={max_y:.3f}=grid({grid_max_y}), bottom={min_y:.3f}=grid({grid_min_y}), left={min_x:.3f}=grid({grid_min_x}), right={max_x:.3f}=grid({grid_max_x})")
                    parts.append(f"    Points: [{points_str}]")
        else:
            parts.append("No strokes drawn yet.")
        
        # Include ALL anchors (no limit)
        if self.anchors:
            parts.append("\nANCHORS (all reference points for spatial relationships):")
            # Group by shape for clarity
            shape_anchors = {}
            for name, value in self.anchors.items():
                parts_list = name.split('_')
                if len(parts_list) >= 2:
                    shape_key = '_'.join(parts_list[:-1]) if parts_list[-1] in ['center', 'top', 'bottom', 'left', 'right', 'top_left', 'top_right', 'bottom_left', 'bottom_right'] else '_'.join(parts_list[:2])
                else:
                    shape_key = "other"
                
                if shape_key not in shape_anchors:
                    shape_anchors[shape_key] = []
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    from config import GRID_SIZE
                    # Handle nested lists (e.g., [[x, y]] instead of [x, y])
                    if isinstance(value[0], (list, tuple)):
                        # Value is nested: [[x, y]]
                        coord_x = value[0][0] if len(value[0]) > 0 else 0.0
                        coord_y = value[0][1] if len(value[0]) > 1 else 0.0
                    else:
                        # Value is flat: [x, y]
                        coord_x = value[0]
                        coord_y = value[1]
                    
                    # Ensure coordinates are numbers
                    if isinstance(coord_x, (int, float)) and isinstance(coord_y, (int, float)):
                        grid_x = int(coord_x * GRID_SIZE)
                        grid_y = int(coord_y * GRID_SIZE)
                        shape_anchors[shape_key].append((name, f"({coord_x:.3f}, {coord_y:.3f})=grid({grid_x},{grid_y})"))
                    else:
                        shape_anchors[shape_key].append((name, str(value)))
                else:
                    shape_anchors[shape_key].append((name, str(value)))
            
            # Display ALL anchors (no limit)
            for shape_key in sorted(shape_anchors.keys()):
                parts.append(f"  {shape_key.upper()}:")
                for name, value in sorted(shape_anchors[shape_key]):
                    parts.append(f"    {name}: {value}")
        
        return "\n".join(parts)

    def set_stop_flag(self, value: bool = True) -> None:
        """Set the stop flag."""
        self.stop_flag = value

    def reset_stop_flag(self) -> None:
        """Reset the stop flag."""
        self.stop_flag = False
    
    def get_preview_strokes(self) -> List[Stroke]:
        """Get all strokes in preview state."""
        return [s for s in self.strokes_history if s.state == "preview"]
    
    def confirm_preview_strokes(self) -> int:
        """
        Confirm all preview strokes (change state to 'confirmed').
        Returns number of strokes confirmed.
        """
        count = 0
        for stroke in self.strokes_history:
            if stroke.state == "preview":
                stroke.state = "confirmed"
                count += 1
        return count
    
    def reject_preview_strokes(self) -> int:
        """
        Reject and remove all preview strokes.
        Returns number of strokes removed.
        """
        preview_strokes = [s for s in self.strokes_history if s.state == "preview"]
        count = len(preview_strokes)
        
        # Remove preview strokes
        self.strokes_history = [s for s in self.strokes_history if s.state != "preview"]
        
        # Remove from features
        for stroke in preview_strokes:
            for feature_data in self.features.values():
                if stroke.id in feature_data.get("stroke_ids", []):
                    feature_data["stroke_ids"].remove(stroke.id)
        
        return count

    def undo_last_strokes(self, count: int = 1) -> None:
        """
        Remove last N strokes from memory (logical undo).
        Note: Physical ink remains on paper.
        """
        if count <= 0:
            return
        
        removed = min(count, len(self.strokes_history))
        for _ in range(removed):
            if self.strokes_history:
                stroke = self.strokes_history.pop()
                # Remove from features
                for feature_data in self.features.values():
                    if stroke.id in feature_data.get("stroke_ids", []):
                        feature_data["stroke_ids"].remove(stroke.id)
        
        # Update last position
        if self.strokes_history:
            last_stroke = self.strokes_history[-1]
            if last_stroke.points:
                self.last_position = last_stroke.points[-1]
        else:
            self.last_position = (0.5, 0.5)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "strokes_history": [
                {
                    "id": s.id,
                    "points": s.points,
                    "label": s.label
                }
                for s in self.strokes_history
            ],
            "features": self.features,
            "anchors": self.anchors,
            "last_position": self.last_position,
            "stop_flag": self.stop_flag
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrawingMemory":
        """Deserialize from dictionary."""
        memory = cls()
        memory.strokes_history = [
            Stroke(id=s["id"], points=s["points"], label=s.get("label"))
            for s in data.get("strokes_history", [])
        ]
        memory.features = data.get("features", {})
        memory.anchors = data.get("anchors", {})
        memory.last_position = tuple(data.get("last_position", (0.5, 0.5)))
        memory.stop_flag = data.get("stop_flag", False)
        if memory.strokes_history:
            memory._next_stroke_id = max(s.id for s in memory.strokes_history) + 1
        return memory


def create_state_summary(memory: DrawingMemory) -> str:
    """Convenience function to get state summary."""
    return memory.get_state_summary()
