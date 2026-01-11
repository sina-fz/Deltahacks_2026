"""
Semantic validator for generated strokes.
Checks spatial relationships, overlaps, spacing, ratios, and symmetry.
Pure logic - no LLM calls.
"""
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from config import GRID_SIZE
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BoundingBox:
    """Bounding box for a stroke."""
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    center_x: float
    center_y: float
    width: float
    height: float
    
    @classmethod
    def from_points(cls, points: List[Tuple[float, float]]) -> "BoundingBox":
        """Create bounding box from points."""
        if not points:
            return cls(0, 0, 0, 0, 0, 0, 0, 0)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width = max_x - min_x
        height = max_y - min_y
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        return cls(min_x, max_x, min_y, max_y, center_x, center_y, width, height)


@dataclass
class ValidationIssue:
    """Represents a validation issue."""
    severity: str  # "error" or "warning"
    category: str  # "overlap", "spacing", "ratio", "symmetry", "size"
    description: str
    affected_strokes: List[int]  # indices of affected strokes


@dataclass
class ValidationResult:
    """Result of semantic validation."""
    valid: bool
    score: float  # 0.0 to 1.0, higher is better
    issues: List[ValidationIssue]
    
    def get_repair_hints(self) -> str:
        """Generate repair hints for LLM."""
        if self.valid or not self.issues:
            return ""
        
        hints = ["ISSUES DETECTED (fix these):"]
        for i, issue in enumerate(self.issues, 1):
            hints.append(f"{i}. {issue.category.upper()}: {issue.description}")
        
        return "\n".join(hints)


class SemanticValidator:
    """Validates generated strokes for semantic correctness."""
    
    def __init__(self, min_spacing: float = 0.05, max_overlap_ratio: float = 0.1):
        """
        Initialize validator.
        
        Args:
            min_spacing: Minimum spacing between objects (normalized)
            max_overlap_ratio: Maximum allowed overlap ratio (0.0 to 1.0)
        """
        self.min_spacing = min_spacing
        self.max_overlap_ratio = max_overlap_ratio
    
    def validate(
        self,
        strokes: List[List[Tuple[float, float]]],
        labels: Dict[str, str],
        anchors: Dict[str, Any],
        existing_strokes: List[List[Tuple[float, float]]] = None,
        instruction: str = ""
    ) -> ValidationResult:
        """
        Validate strokes for semantic correctness.
        
        Args:
            strokes: New strokes to validate
            labels: Labels for the strokes
            anchors: Anchors (may include plan/components)
            existing_strokes: Previously drawn strokes
            instruction: User instruction (for context)
        
        Returns:
            ValidationResult with score and issues
        """
        issues = []
        
        if not strokes:
            return ValidationResult(valid=True, score=1.0, issues=[])
        
        # Compute bounding boxes for all strokes
        new_boxes = [BoundingBox.from_points(s) for s in strokes]
        existing_boxes = [BoundingBox.from_points(s) for s in existing_strokes] if existing_strokes else []
        
        # Check 1: Overlap between new strokes
        overlap_issues = self._check_overlaps(new_boxes, labels)
        issues.extend(overlap_issues)
        
        # Check 2: Spacing relative to existing strokes
        if existing_strokes and instruction:
            spacing_issues = self._check_spacing(new_boxes, existing_boxes, labels, instruction)
            issues.extend(spacing_issues)
        
        # Check 3: Size ratios (if multiple components)
        if len(strokes) > 1:
            ratio_issues = self._check_ratios(new_boxes, labels)
            issues.extend(ratio_issues)
        
        # Check 4: Pair symmetry (if labels indicate pairs)
        pair_issues = self._check_pair_symmetry(new_boxes, labels, anchors)
        issues.extend(pair_issues)
        
        # Check 5: Size sanity (not too small, not too large)
        size_issues = self._check_sizes(new_boxes, labels)
        issues.extend(size_issues)
        
        # Calculate score
        score = self._calculate_score(issues)
        valid = score >= 0.7 and not any(issue.severity == "error" for issue in issues)
        
        logger.info(f"Validation: {'PASS' if valid else 'FAIL'} (score={score:.2f}, issues={len(issues)})")
        for issue in issues:
            logger.info(f"  [{issue.severity.upper()}] {issue.category}: {issue.description}")
        
        return ValidationResult(valid=valid, score=score, issues=issues)
    
    def _check_overlaps(
        self,
        boxes: List[BoundingBox],
        labels: Dict[str, str]
    ) -> List[ValidationIssue]:
        """Check for overlaps between strokes."""
        issues = []
        
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                box1, box2 = boxes[i], boxes[j]
                overlap_ratio = self._compute_overlap_ratio(box1, box2)
                
                if overlap_ratio > self.max_overlap_ratio:
                    label1 = labels.get(f"stroke_{i}", f"stroke {i}")
                    label2 = labels.get(f"stroke_{j}", f"stroke {j}")
                    issues.append(ValidationIssue(
                        severity="error",
                        category="overlap",
                        description=f"{label1} and {label2} overlap by {overlap_ratio*100:.1f}%",
                        affected_strokes=[i, j]
                    ))
        
        return issues
    
    def _check_spacing(
        self,
        new_boxes: List[BoundingBox],
        existing_boxes: List[BoundingBox],
        labels: Dict[str, str],
        instruction: str
    ) -> List[ValidationIssue]:
        """Check spacing relative to existing strokes based on instruction."""
        issues = []
        instruction_lower = instruction.lower()
        
        # Determine expected spacing from instruction
        if "much further" in instruction_lower or "far" in instruction_lower:
            expected_spacing = 0.3  # 3 grid cells
        elif "beside" in instruction_lower or "next to" in instruction_lower:
            expected_spacing = 0.1  # 1 grid cell
        elif "to the left" in instruction_lower or "to the right" in instruction_lower:
            expected_spacing = 0.15  # 1.5 grid cells
        else:
            return []  # No spacing constraint
        
        # Check spacing to nearest existing stroke
        for i, new_box in enumerate(new_boxes):
            min_distance = float('inf')
            for existing_box in existing_boxes:
                distance = self._compute_distance(new_box, existing_box)
                min_distance = min(min_distance, distance)
            
            if min_distance < self.min_spacing:
                label = labels.get(f"stroke_{i}", f"stroke {i}")
                issues.append(ValidationIssue(
                    severity="error",
                    category="spacing",
                    description=f"{label} too close to existing object (distance={min_distance:.3f}, min={self.min_spacing:.3f})",
                    affected_strokes=[i]
                ))
            elif abs(min_distance - expected_spacing) > expected_spacing * 0.5:
                # Warning if spacing is off by more than 50%
                label = labels.get(f"stroke_{i}", f"stroke {i}")
                issues.append(ValidationIssue(
                    severity="warning",
                    category="spacing",
                    description=f"{label} spacing may not match instruction '{instruction}' (actual={min_distance:.3f}, expected≈{expected_spacing:.3f})",
                    affected_strokes=[i]
                ))
        
        return issues
    
    def _check_ratios(
        self,
        boxes: List[BoundingBox],
        labels: Dict[str, str]
    ) -> List[ValidationIssue]:
        """Check size ratios between components."""
        issues = []
        
        if len(boxes) < 2:
            return []
        
        # Get all sizes
        sizes = [(box.width * box.height, i) for i, box in enumerate(boxes)]
        sizes.sort(reverse=True)
        
        largest_size, largest_idx = sizes[0]
        smallest_size, smallest_idx = sizes[-1]
        
        # Check if ratio is too extreme
        if largest_size > 0 and smallest_size > 0:
            ratio = largest_size / smallest_size
            if ratio > 100:  # One component is 100x larger than another
                label1 = labels.get(f"stroke_{largest_idx}", f"stroke {largest_idx}")
                label2 = labels.get(f"stroke_{smallest_idx}", f"stroke {smallest_idx}")
                issues.append(ValidationIssue(
                    severity="error",
                    category="ratio",
                    description=f"{label1} is {ratio:.1f}x larger than {label2} - extreme size difference",
                    affected_strokes=[largest_idx, smallest_idx]
                ))
        
        return issues
    
    def _check_pair_symmetry(
        self,
        boxes: List[BoundingBox],
        labels: Dict[str, str],
        anchors: Dict[str, Any]
    ) -> List[ValidationIssue]:
        """Check symmetry for paired components (e.g., two ears, two eyes)."""
        issues = []
        
        # Detect pairs by looking for similar labels or plan mentioning "two X"
        plan = anchors.get("plan", "")
        components = anchors.get("components", {})
        
        # Look for pairs in labels (e.g., "ear_left", "ear_right" or "ear_1", "ear_2")
        label_groups = {}
        for key, label in labels.items():
            if not label:
                continue
            # Extract base name (remove _left, _right, _1, _2, etc.)
            base_name = label.split('_')[0]
            if base_name not in label_groups:
                label_groups[base_name] = []
            stroke_idx = int(key.split('_')[-1]) if '_' in key else int(key)
            label_groups[base_name].append((stroke_idx, label, boxes[stroke_idx] if stroke_idx < len(boxes) else None))
        
        # Check each group with 2+ items
        for base_name, group in label_groups.items():
            if len(group) != 2:
                continue  # Only check pairs
            
            idx1, label1, box1 = group[0]
            idx2, label2, box2 = group[1]
            
            if box1 is None or box2 is None:
                continue
            
            # Check if they have similar sizes (should be within 50% of each other)
            size1 = box1.width * box1.height
            size2 = box2.width * box2.height
            if size1 > 0 and size2 > 0:
                ratio = max(size1, size2) / min(size1, size2)
                if ratio > 2.0:
                    issues.append(ValidationIssue(
                        severity="warning",
                        category="symmetry",
                        description=f"{label1} and {label2} have very different sizes (ratio={ratio:.1f})",
                        affected_strokes=[idx1, idx2]
                    ))
            
            # Check if they have different X positions (not overlapping horizontally)
            x_overlap = min(box1.max_x, box2.max_x) - max(box1.min_x, box2.min_x)
            if x_overlap > 0.01:  # Overlapping in X
                issues.append(ValidationIssue(
                    severity="error",
                    category="symmetry",
                    description=f"{label1} and {label2} overlap horizontally - should be on different sides",
                    affected_strokes=[idx1, idx2]
                ))
            
            # Check if they're at similar Y positions (should be aligned)
            y_diff = abs(box1.center_y - box2.center_y)
            max_height = max(box1.height, box2.height)
            if y_diff > max_height * 0.5:  # Y difference is more than half the height
                issues.append(ValidationIssue(
                    severity="warning",
                    category="symmetry",
                    description=f"{label1} and {label2} not aligned vertically (Y diff={y_diff:.3f})",
                    affected_strokes=[idx1, idx2]
                ))
        
        return issues
    
    def _check_sizes(
        self,
        boxes: List[BoundingBox],
        labels: Dict[str, str]
    ) -> List[ValidationIssue]:
        """Check if sizes are reasonable."""
        issues = []
        
        for i, box in enumerate(boxes):
            size = box.width * box.height
            
            # Too small (less than 0.5% of canvas)
            if size < 0.005:
                label = labels.get(f"stroke_{i}", f"stroke {i}")
                issues.append(ValidationIssue(
                    severity="warning",
                    category="size",
                    description=f"{label} very small (size={size:.4f})",
                    affected_strokes=[i]
                ))
            
            # Too large (more than 80% of canvas)
            if size > 0.8:
                label = labels.get(f"stroke_{i}", f"stroke {i}")
                issues.append(ValidationIssue(
                    severity="warning",
                    category="size",
                    description=f"{label} very large (size={size:.4f})",
                    affected_strokes=[i]
                ))
        
        return issues
    
    def _compute_overlap_ratio(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """Compute overlap ratio between two bounding boxes."""
        # Compute intersection
        x_overlap = max(0, min(box1.max_x, box2.max_x) - max(box1.min_x, box2.min_x))
        y_overlap = max(0, min(box1.max_y, box2.max_y) - max(box1.min_y, box2.min_y))
        intersection = x_overlap * y_overlap
        
        # Compute union
        area1 = box1.width * box1.height
        area2 = box2.width * box2.height
        union = area1 + area2 - intersection
        
        if union <= 0:
            return 0.0
        
        return intersection / union
    
    def _compute_distance(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """Compute minimum distance between two bounding boxes."""
        # Check if boxes overlap
        x_overlap = min(box1.max_x, box2.max_x) - max(box1.min_x, box2.min_x)
        y_overlap = min(box1.max_y, box2.max_y) - max(box1.min_y, box2.min_y)
        
        if x_overlap > 0 and y_overlap > 0:
            return 0.0  # Overlapping
        
        # Compute distances in each dimension
        if x_overlap > 0:
            # Horizontally aligned
            x_dist = 0
            y_dist = max(0, max(box1.min_y, box2.min_y) - min(box1.max_y, box2.max_y))
        elif y_overlap > 0:
            # Vertically aligned
            x_dist = max(0, max(box1.min_x, box2.min_x) - min(box1.max_x, box2.max_x))
            y_dist = 0
        else:
            # Diagonal
            x_dist = max(0, max(box1.min_x, box2.min_x) - min(box1.max_x, box2.max_x))
            y_dist = max(0, max(box1.min_y, box2.min_y) - min(box1.max_y, box2.max_y))
        
        return (x_dist**2 + y_dist**2)**0.5
    
    def _calculate_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate overall score from issues."""
        if not issues:
            return 1.0
        
        # Deduct points for each issue
        score = 1.0
        for issue in issues:
            if issue.severity == "error":
                score -= 0.3
            elif issue.severity == "warning":
                score -= 0.1
        
        return max(0.0, score)
