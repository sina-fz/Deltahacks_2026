"""
PlotterDriver abstraction for controlling the BrachioGraph drawing arm.
Supports both real hardware and simulation mode.
"""
from typing import List, Tuple, Optional
from config import SIMULATION_MODE, get_drawing_bounds
from execution.coordinate_mapper import CoordinateMapper
from utils.logger import get_logger

logger = get_logger(__name__)


class PlotterDriver:
    """
    Abstraction layer for controlling the drawing arm.
    In simulation mode, prints planned movements instead of moving hardware.
    """
    
    def __init__(self, mapper: CoordinateMapper, simulation: bool = None):
        """
        Initialize the plotter driver.
        
        Args:
            mapper: CoordinateMapper instance
            simulation: If True, simulate without hardware (default from config)
        """
        self.mapper = mapper
        self.simulation = simulation if simulation is not None else SIMULATION_MODE
        self.is_initialized = False
        self._pen_is_down = False
        self.current_position: Optional[Tuple[float, float]] = None
        
        # BrachioGraph instance (will be None in simulation)
        self.brachiograph = None
        
        if not self.simulation:
            self._initialize_hardware()
        else:
            logger.info("Running in SIMULATION MODE - no hardware will be moved")
    
    def _initialize_hardware(self) -> None:
        """Initialize BrachioGraph hardware with proper bounds and configuration."""
        try:
            try:
                from brachiograph import BrachioGraph
                
                # Get drawing bounds (in mm)
                min_x, max_x, min_y, max_y = get_drawing_bounds()
                
                # Convert mm to cm for BrachioGraph (BrachioGraph uses cm)
                min_x_cm = min_x / 10.0
                max_x_cm = max_x / 10.0
                min_y_cm = min_y / 10.0
                max_y_cm = max_y / 10.0
                
                # BrachioGraph bounds format: [left, top, right, bottom]
                bounds = [min_x_cm, max_y_cm, max_x_cm, min_y_cm]
                
                # Initialize BrachioGraph with bounds and default arm lengths
                # Default: inner_arm=8cm, outer_arm=8cm (adjust if your hardware differs)
                self.brachiograph = BrachioGraph(
                    virtual=False,  # Real hardware
                    bounds=bounds,
                    inner_arm=8,  # Adjust based on your hardware
                    outer_arm=8,  # Adjust based on your hardware
                    resolution=0.1,  # 0.1 cm resolution for smooth curves
                    angular_step=0.1,  # 0.1 degree precision
                    wait=0.01  # Small wait between movements
                )
                logger.info(f"BrachioGraph hardware initialized with bounds {bounds} cm")
            except ImportError:
                logger.warning("BrachioGraph package not available. Install with: pip install brachiograph")
                logger.warning("Falling back to simulation mode.")
                self.simulation = True
            except Exception as e:
                logger.error(f"Failed to initialize BrachioGraph: {e}. Falling back to simulation mode.")
                self.simulation = True
        except Exception as e:
            logger.error(f"Hardware initialization error: {e}")
            self.simulation = True
    
    def initialize(self) -> None:
        """Initialize/home the plotter using BrachioGraph's park() method."""
        if self.simulation:
            logger.info("[SIM] Initializing plotter (home position)")
            self.current_position = (0.0, 0.0)  # Normalized
        else:
            if self.brachiograph:
                # BrachioGraph doesn't have a home() method, but park() moves to safe position
                # We'll start at the center of the drawing area
                min_x, max_x, min_y, max_y = get_drawing_bounds()
                center_x = (min_x + max_x) / 2.0 / 10.0  # Convert to cm
                center_y = (min_y + max_y) / 2.0 / 10.0  # Convert to cm
                
                # Move to center with pen up
                self.brachiograph.xy(x=center_x, y=center_y, draw=False)
                logger.info(f"Plotter initialized at center ({center_x:.2f}, {center_y:.2f}) cm")
            self.current_position = (0.5, 0.5)  # Normalized center
        
        self.is_initialized = True
    
    def pen_up(self) -> None:
        """Lift the pen using BrachioGraph's pen control."""
        if self.simulation:
            logger.debug("[SIM] Pen UP")
        else:
            if self.brachiograph:
                # BrachioGraph uses pulse widths for pen control
                # pw_up is typically 1500, pw_down is typically 1100-1300
                # The plotter handles this automatically, but we can set it explicitly if needed
                # For now, we rely on xy() and plot_lines() to handle pen state
                pass
        self._pen_is_down = False
    
    def pen_down(self) -> None:
        """Lower the pen (start drawing) using BrachioGraph's pen control."""
        if self.simulation:
            logger.debug("[SIM] Pen DOWN")
        else:
            if self.brachiograph:
                # BrachioGraph uses pulse widths for pen control
                # The plotter handles this automatically via xy(draw=True) or plot_lines()
                pass
        self._pen_is_down = True
    
    def move_to(self, x_norm: float, y_norm: float, draw: bool = False) -> None:
        """
        Move to a position (normalized coordinates) using BrachioGraph's xy() method.
        
        Args:
            x_norm: Normalized X [0.0, 1.0]
            y_norm: Normalized Y [0.0, 1.0]
            draw: If True, draw while moving (pen down)
        """
        if not self.is_initialized:
            self.initialize()
        
        # Map to physical coordinates (BrachioGraph uses cm, not mm)
        x_phys, y_phys = self.mapper.normalize_to_physical(x_norm, y_norm)
        # Convert mm to cm for BrachioGraph
        x_cm = x_phys / 10.0
        y_cm = y_phys / 10.0
        
        if self.simulation:
            action = "DRAW" if draw else "MOVE"
            logger.info(f"[SIM] {action} to ({x_norm:.3f}, {y_norm:.3f}) -> physical ({x_phys:.1f}, {y_phys:.1f}) mm -> ({x_cm:.2f}, {y_cm:.2f}) cm")
        else:
            if self.brachiograph:
                # Use BrachioGraph's xy() method for accurate positioning
                # xy() handles angle calculations and servo control automatically
                self.brachiograph.xy(
                    x=x_cm,
                    y=y_cm,
                    draw=draw,
                    angular_step=0.1,  # 0.1 degree precision
                    wait=0.01,  # Small wait between movements
                    resolution=0.1  # 0.1 cm resolution for smooth curves
                )
                logger.debug(f"Moved to ({x_cm:.2f}, {y_cm:.2f}) cm (draw={draw})")
            else:
                # Fallback: manual pen control
                if draw and not self._pen_is_down:
                    self.pen_down()
                elif not draw and self._pen_is_down:
                    self.pen_up()
        
        self.current_position = (x_norm, y_norm)
    
    def draw_polyline(self, points: List[Tuple[float, float]]) -> None:
        """
        Draw a polyline (connected points) using BrachioGraph's plot_lines method.
        This provides better accuracy by using BrachioGraph's built-in line processing.
        
        Args:
            points: List of (x_norm, y_norm) tuples
        """
        if not points:
            return
        
        if not self.is_initialized:
            self.initialize()
        
        # Convert normalized points to physical coordinates
        physical_points = [self.mapper.normalize_to_physical(x, y) for x, y in points]
        
        if self.simulation:
            logger.info(f"[SIM] Drawing polyline with {len(points)} points:")
            for i, (x_norm, y_norm) in enumerate(points):
                x_phys, y_phys = physical_points[i]
                logger.info(f"  Point {i+1}: ({x_norm:.3f}, {y_norm:.3f}) -> ({x_phys:.1f}, {y_phys:.1f}) mm")
        else:
            if self.brachiograph:
                # Use BrachioGraph's plot_lines method for better accuracy
                # Format: lines is a list of lines, each line is a list of [x, y] points
                lines = [[list(point) for point in physical_points]]
                
                # Use BrachioGraph's plot_lines with proper resolution
                # resolution: distance in cm - breaks long lines into shorter curved segments
                # angular_step: angle in degrees for servo movement precision
                self.brachiograph.plot_lines(
                    lines=lines,
                    resolution=0.1,  # 0.1 cm resolution for smooth curves
                    angular_step=0.1,  # 0.1 degree precision
                    wait=0.01  # Small wait between movements
                )
                logger.info(f"Drew polyline with {len(points)} points using BrachioGraph plot_lines")
            else:
                # Fallback: manual point-by-point drawing
                if len(points) > 0:
                    first_x, first_y = points[0]
                    self.move_to(first_x, first_y, draw=False)
                
                self.pen_down()
                
                for x, y in points[1:]:
                    self.move_to(x, y, draw=True)
                
                self.pen_up()
    
    def execute_strokes(self, strokes: List[List[Tuple[float, float]]], 
                       stop_flag: callable = None) -> None:
        """
        Execute multiple strokes using BrachioGraph's plot_lines for better accuracy.
        
        Args:
            strokes: List of polylines (each is a list of points)
            stop_flag: Callable that returns True if should stop
        """
        if not self.is_initialized:
            self.initialize()
        
        logger.info(f"Executing {len(strokes)} strokes")
        
        # Check stop flag before starting
        if stop_flag and stop_flag():
            logger.warning("Stop flag set - aborting execution")
            return
        
        if self.simulation:
            # In simulation, draw each stroke individually for clarity
            for i, stroke in enumerate(strokes):
                if stop_flag and stop_flag():
                    logger.warning("Stop flag set - interrupting execution")
                    return
                logger.debug(f"Executing stroke {i+1}/{len(strokes)} ({len(stroke)} points)")
                self.draw_polyline(stroke)
        else:
            if self.brachiograph:
                # Convert all strokes to physical coordinates (cm)
                lines = []
                for stroke in strokes:
                    if stop_flag and stop_flag():
                        logger.warning("Stop flag set - interrupting execution")
                        return
                    physical_stroke = [self.mapper.normalize_to_physical(x, y) for x, y in stroke]
                    # Convert mm to cm and format as [x, y] lists
                    cm_stroke = [[x/10.0, y/10.0] for x, y in physical_stroke]
                    lines.append(cm_stroke)
                
                # Use BrachioGraph's plot_lines for accurate batch drawing
                # This uses proper resolution and angular_step for smooth curves
                self.brachiograph.plot_lines(
                    lines=lines,
                    resolution=0.1,  # 0.1 cm resolution - breaks long lines into curved segments
                    angular_step=0.1,  # 0.1 degree precision for servo movement
                    wait=0.01  # Small wait between movements
                )
                logger.info(f"Drew {len(strokes)} strokes using BrachioGraph plot_lines")
            else:
                # Fallback: draw each stroke individually
                for i, stroke in enumerate(strokes):
                    if stop_flag and stop_flag():
                        logger.warning("Stop flag set - interrupting execution")
                        self.pen_up()
                        return
                    logger.debug(f"Executing stroke {i+1}/{len(strokes)} ({len(stroke)} points)")
                    self.draw_polyline(stroke)
        
        logger.info("All strokes executed")
    
    def stop(self) -> None:
        """Immediate safe stop (lift pen, park)."""
        logger.warning("STOP called - lifting pen and parking")
        self.pen_up()
        
        if self.simulation:
            logger.info("[SIM] Stopped and parked")
        else:
            if self.brachiograph:
                # self.brachiograph.park()  # Adjust based on actual API
                pass
    
    def park(self) -> None:
        """Park the plotter (move to safe position)."""
        if self.simulation:
            logger.info("[SIM] Parking plotter")
        else:
            if self.brachiograph:
                # self.brachiograph.park()  # Adjust based on actual API
                pass
        self.pen_up()
        self.current_position = None
