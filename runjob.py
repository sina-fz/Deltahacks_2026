#!/usr/bin/env python3
"""
BrachioGraph Drawing Job Executor for Raspberry Pi

USAGE:
  Copy this file to your Raspberry Pi at: /home/pi/runjob.py
  
  From laptop, send and execute jobs:
    scp job.json pi@raspberrypi.local:/tmp/job.json
    ssh pi@raspberrypi.local "python3 /home/pi/runjob.py /tmp/job.json"
  
  Or use --dry-run to test without moving hardware:
    python3 runjob.py job.json --dry-run

REQUIREMENTS ON PI:
  pip3 install brachiograph

JOB FILE FORMATS SUPPORTED:
  
  Format A (simple array of polylines):
    [
      [[1.0, 1.0], [8.0, 1.0], [8.0, 6.0]],
      [[2.5, 2.0], [3.5, 2.0]]
    ]
  
  Format B (structured with metadata):
    {
      "format": "plot_job_v1",
      "coords": "normalized",
      "bounds_cm": {"min_x":0, "max_x":10, "min_y":0, "max_y":10},
      "lines": [[[0.1,0.1],[0.9,0.1],[0.9,0.9]]],
      "metadata": {"prompt": "draw a square"}
    }

COORDINATE SYSTEMS:
  - "cm": Coordinates are in centimeters (BrachioGraph native)
  - "normalized": Coordinates are [0.0, 1.0], mapped using bounds_cm
  - "auto": Auto-detect (if all points in [0,1] → normalized, else cm)
"""

import json
import sys
import argparse
from typing import List, Tuple, Dict, Any


def load_job(filepath: str) -> Dict[str, Any]:
    """Load and parse job JSON file."""
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"ERROR: Job file not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)


def parse_job(data: Any, coord_mode: str = 'auto') -> Tuple[List[List[Tuple[float, float]]], Dict[str, float]]:
    """
    Parse job data into polylines (in cm) and bounds.
    
    Returns:
        (lines, bounds_dict)
        lines: List of polylines, each polyline is list of (x_cm, y_cm)
        bounds_dict: {"min_x", "max_x", "min_y", "max_y"} in cm
    """
    # Default bounds (10cm x 10cm)
    default_bounds = {"min_x": 0.0, "max_x": 10.0, "min_y": 0.0, "max_y": 10.0}
    
    # Format A: Simple array of polylines
    if isinstance(data, list):
        lines = data
        coords = coord_mode
        bounds = default_bounds
    # Format B: Structured object
    elif isinstance(data, dict):
        lines = data.get("lines", [])
        coords = data.get("coords", coord_mode)
        bounds = data.get("bounds_cm", default_bounds)
    else:
        print(f"ERROR: Invalid job format. Expected list or dict, got {type(data)}", file=sys.stderr)
        sys.exit(1)
    
    # Auto-detect coordinate system if needed
    if coords == 'auto':
        # Check if all points are in [0, 1] range
        all_normalized = True
        for line in lines:
            for point in line:
                if len(point) != 2:
                    continue
                x, y = point[0], point[1]
                if x < 0 or x > 1 or y < 0 or y > 1:
                    all_normalized = False
                    break
            if not all_normalized:
                break
        coords = 'normalized' if all_normalized else 'cm'
        print(f"Auto-detected coordinate mode: {coords}")
    
    # Convert normalized coordinates to cm if needed
    if coords == 'normalized':
        if not bounds:
            print("ERROR: Normalized coordinates require bounds_cm", file=sys.stderr)
            sys.exit(1)
        
        min_x = bounds["min_x"]
        max_x = bounds["max_x"]
        min_y = bounds["min_y"]
        max_y = bounds["max_y"]
        
        # Map normalized [0,1] to bounds
        converted_lines = []
        for line in lines:
            converted_line = []
            for point in line:
                x_norm, y_norm = point[0], point[1]
                x_cm = min_x + x_norm * (max_x - min_x)
                y_cm = min_y + y_norm * (max_y - min_y)
                converted_line.append((x_cm, y_cm))
            converted_lines.append(converted_line)
        lines = converted_lines
    else:
        # Already in cm, just convert to tuples
        lines = [[(point[0], point[1]) for point in line] for line in lines]
    
    # Clamp all points to bounds if bounds exist
    if bounds:
        min_x = bounds["min_x"]
        max_x = bounds["max_x"]
        min_y = bounds["min_y"]
        max_y = bounds["max_y"]
        
        clamped_lines = []
        for line in lines:
            clamped_line = []
            for x, y in line:
                x_clamped = max(min_x, min(max_x, x))
                y_clamped = max(min_y, min(max_y, y))
                clamped_line.append((x_clamped, y_clamped))
            clamped_lines.append(clamped_line)
        lines = clamped_lines
    
    # Filter out invalid polylines (< 2 points)
    valid_lines = [line for line in lines if len(line) >= 2]
    
    if len(valid_lines) < len(lines):
        print(f"WARNING: Filtered out {len(lines) - len(valid_lines)} invalid polylines (< 2 points)")
    
    return valid_lines, bounds


def execute_drawing(lines: List[List[Tuple[float, float]]], bounds: Dict[str, float], dry_run: bool = False):
    """
    Execute the drawing on BrachioGraph hardware.
    
    Args:
        lines: List of polylines in cm
        bounds: Drawing bounds in cm
        dry_run: If True, print stats without moving hardware
    """
    if dry_run:
        print(f"\n{'='*50}")
        print("DRY RUN MODE - No hardware will move")
        print(f"{'='*50}")
        print(f"Polylines: {len(lines)}")
        total_points = sum(len(line) for line in lines)
        print(f"Total points: {total_points}")
        print(f"Bounds (cm): x=[{bounds['min_x']}, {bounds['max_x']}], y=[{bounds['min_y']}, {bounds['max_y']}]")
        print(f"\nPolylines:")
        for i, line in enumerate(lines, 1):
            print(f"  {i}. {len(line)} points: {line[0]} -> {line[-1]}")
        print(f"{'='*50}\n")
        return
    
    # Initialize BrachioGraph
    try:
        from brachiograph import BrachioGraph
    except ImportError:
        print("ERROR: brachiograph package not installed", file=sys.stderr)
        print("Install with: pip3 install brachiograph", file=sys.stderr)
        sys.exit(1)
    
    print("Initializing BrachioGraph...")
    
    # Create BrachioGraph instance with bounds
    # Format: [left, top, right, bottom]
    bg_bounds = [
        bounds["min_x"],
        bounds["max_y"],
        bounds["max_x"],
        bounds["min_y"]
    ]
    
    try:
        # Initialize with your specific hardware config
        # Adjust inner_arm and outer_arm lengths to match your hardware
        bg = BrachioGraph(
            virtual=False,
            bounds=bg_bounds,
            inner_arm=8,      # Adjust to your arm length (cm)
            outer_arm=8,      # Adjust to your arm length (cm)
            resolution=0.1,   # 0.1 cm resolution for smooth curves
            angular_step=0.1, # 0.1 degree precision
            wait=0.01         # Small wait between movements
        )
        print(f"BrachioGraph initialized with bounds: {bg_bounds} cm")
    except Exception as e:
        print(f"ERROR: Failed to initialize BrachioGraph: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Convert lines to format BrachioGraph expects: list of lists of [x, y]
    bg_lines = [[[x, y] for x, y in line] for line in lines]
    
    # Execute drawing
    print(f"Drawing {len(bg_lines)} polylines ({sum(len(line) for line in bg_lines)} total points)...")
    
    try:
        # Use plot_lines for accurate batch drawing
        bg.plot_lines(
            lines=bg_lines,
            resolution=0.1,   # Break long lines into 0.1cm segments
            angular_step=0.1, # 0.1 degree servo precision
            wait=0.01         # Delay between movements
        )
        print("✓ Drawing complete!")
        
        # Park the arm in a safe position
        try:
            bg.park()
            print("✓ Arm parked")
        except AttributeError:
            # park() might not exist in all versions
            pass
            
    except Exception as e:
        print(f"ERROR during drawing: {e}", file=sys.stderr)
        # Try to lift pen on error
        try:
            bg.pen_up()
        except:
            pass
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Execute BrachioGraph drawing jobs from JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('jobfile', help='Path to job.json file')
    parser.add_argument('--coords', choices=['auto', 'cm', 'normalized'], default='auto',
                       help='Coordinate system (default: auto-detect)')
    parser.add_argument('--bounds-cm', type=str,
                       help='Override bounds as "min_x,max_x,min_y,max_y" (e.g., "0,10,0,10")')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print job details without moving hardware')
    
    args = parser.parse_args()
    
    # Load job
    print(f"Loading job from: {args.jobfile}")
    data = load_job(args.jobfile)
    
    # Parse job
    lines, bounds = parse_job(data, coord_mode=args.coords)
    
    # Override bounds if specified
    if args.bounds_cm:
        try:
            parts = args.bounds_cm.split(',')
            bounds = {
                "min_x": float(parts[0]),
                "max_x": float(parts[1]),
                "min_y": float(parts[2]),
                "max_y": float(parts[3])
            }
            print(f"Using override bounds: {bounds}")
        except (ValueError, IndexError):
            print("ERROR: Invalid bounds format. Use: min_x,max_x,min_y,max_y", file=sys.stderr)
            sys.exit(1)
    
    if not lines:
        print("ERROR: No valid polylines in job file", file=sys.stderr)
        sys.exit(1)
    
    # Execute
    execute_drawing(lines, bounds, dry_run=args.dry_run)
    
    print("\n✓ Job complete!")
    sys.exit(0)


if __name__ == '__main__':
    main()
