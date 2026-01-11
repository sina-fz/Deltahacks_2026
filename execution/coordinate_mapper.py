"""
Coordinate mapping and validation.
Maps normalized [0.0, 1.0] coordinates to physical arm coordinates.
"""
from typing import Tuple, List
from config import get_drawing_bounds, DRAWING_BOX


class CoordinateMapper:
    """Maps normalized coordinates to physical coordinates."""
    
    def __init__(self, drawing_box: dict = None):
        """
        Initialize with drawing box bounds.
        
        Args:
            drawing_box: Dict with min_x, max_x, min_y, max_y (in mm)
        """
        self.drawing_box = drawing_box or DRAWING_BOX
        self.min_x = self.drawing_box["min_x"]
        self.max_x = self.drawing_box["max_x"]
        self.min_y = self.drawing_box["min_y"]
        self.max_y = self.drawing_box["max_y"]
        
        self.width = self.max_x - self.min_x
        self.height = self.max_y - self.min_y
    
    def normalize_to_physical(self, x_norm: float, y_norm: float) -> Tuple[float, float]:
        """
        Convert normalized [0.0, 1.0] coordinates to physical coordinates.
        
        Args:
            x_norm: Normalized X [0.0, 1.0]
            y_norm: Normalized Y [0.0, 1.0]
        
        Returns:
            (x_physical, y_physical) in mm
        """
        x_phys = self.min_x + (x_norm * self.width)
        y_phys = self.min_y + (y_norm * self.height)
        return (x_phys, y_phys)
    
    def physical_to_normalize(self, x_phys: float, y_phys: float) -> Tuple[float, float]:
        """
        Convert physical coordinates to normalized [0.0, 1.0].
        
        Args:
            x_phys: Physical X in mm
            y_phys: Physical Y in mm
        
        Returns:
            (x_norm, y_norm) in [0.0, 1.0]
        """
        x_norm = (x_phys - self.min_x) / self.width if self.width > 0 else 0.5
        y_norm = (y_phys - self.min_y) / self.height if self.height > 0 else 0.5
        return (x_norm, y_norm)
    
    def clamp_normalized(self, x: float, y: float) -> Tuple[float, float]:
        """Clamp normalized coordinates to [0.0, 1.0]."""
        x_clamped = max(0.0, min(1.0, x))
        y_clamped = max(0.0, min(1.0, y))
        return (x_clamped, y_clamped)
    
    def clamp_physical(self, x: float, y: float) -> Tuple[float, float]:
        """Clamp physical coordinates to drawing box."""
        x_clamped = max(self.min_x, min(self.max_x, x))
        y_clamped = max(self.min_y, min(self.max_y, y))
        return (x_clamped, y_clamped)
    
    def verify_normalization(self) -> bool:
        """
        Verify that normalization is working correctly.
        Returns True if all tests pass, raises AssertionError if any test fails.
        """
        # Test 1: (0.0, 0.0) should map to (min_x, min_y)
        x_phys, y_phys = self.normalize_to_physical(0.0, 0.0)
        assert abs(x_phys - self.min_x) < 0.001, f"Test 1 failed: Expected {self.min_x}, got {x_phys}"
        assert abs(y_phys - self.min_y) < 0.001, f"Test 1 failed: Expected {self.min_y}, got {y_phys}"
        
        # Test 2: (1.0, 1.0) should map to (max_x, max_y)
        x_phys, y_phys = self.normalize_to_physical(1.0, 1.0)
        assert abs(x_phys - self.max_x) < 0.001, f"Test 2 failed: Expected {self.max_x}, got {x_phys}"
        assert abs(y_phys - self.max_y) < 0.001, f"Test 2 failed: Expected {self.max_y}, got {y_phys}"
        
        # Test 3: (0.5, 0.5) should map to center
        x_phys, y_phys = self.normalize_to_physical(0.5, 0.5)
        expected_x = self.min_x + (self.width / 2)
        expected_y = self.min_y + (self.height / 2)
        assert abs(x_phys - expected_x) < 0.001, f"Test 3 failed: Expected {expected_x}, got {x_phys}"
        assert abs(y_phys - expected_y) < 0.001, f"Test 3 failed: Expected {expected_y}, got {y_phys}"
        
        # Test 4: Round trip (normalize -> physical -> normalize)
        x_norm, y_norm = 0.3, 0.7
        x_phys, y_phys = self.normalize_to_physical(x_norm, y_norm)
        x_norm2, y_norm2 = self.physical_to_normalize(x_phys, y_phys)
        assert abs(x_norm - x_norm2) < 0.001, f"Test 4 failed: Round trip failed for X: {x_norm} -> {x_norm2}"
        assert abs(y_norm - y_norm2) < 0.001, f"Test 4 failed: Round trip failed for Y: {y_norm} -> {y_norm2}"
        
        # Test 5: Edge cases
        # Test 5a: Very small normalized value
        x_phys, y_phys = self.normalize_to_physical(0.001, 0.001)
        assert x_phys >= self.min_x and x_phys <= self.max_x, f"Test 5a failed: X out of bounds: {x_phys}"
        assert y_phys >= self.min_y and y_phys <= self.max_y, f"Test 5a failed: Y out of bounds: {y_phys}"
        
        # Test 5b: Very large normalized value (should be clamped)
        x_phys, y_phys = self.normalize_to_physical(0.999, 0.999)
        assert x_phys >= self.min_x and x_phys <= self.max_x, f"Test 5b failed: X out of bounds: {x_phys}"
        assert y_phys >= self.min_y and y_phys <= self.max_y, f"Test 5b failed: Y out of bounds: {y_phys}"
        
        return True


def validate_and_clamp_coordinates(
    strokes: List[List[Tuple[float, float]]],
    mapper: CoordinateMapper
) -> List[List[Tuple[float, float]]]:
    """
    Validate and clamp all coordinates in strokes to valid ranges.
    
    Args:
        strokes: List of polylines with normalized coordinates
        mapper: CoordinateMapper instance
    
    Returns:
        Validated and clamped strokes
    """
    validated = []
    for stroke in strokes:
        validated_stroke = []
        for x, y in stroke:
            # Validate types
            if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                raise ValueError(f"Invalid coordinate type: ({x}, {y})")
            
            # Clamp to [0.0, 1.0]
            x_clamped, y_clamped = mapper.clamp_normalized(float(x), float(y))
            validated_stroke.append((x_clamped, y_clamped))
        validated.append(validated_stroke)
    return validated
