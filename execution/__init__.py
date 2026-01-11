"""Execution layer for controlling the drawing arm."""

from .plotter_driver import PlotterDriver
from .coordinate_mapper import CoordinateMapper, validate_and_clamp_coordinates

__all__ = ["PlotterDriver", "CoordinateMapper", "validate_and_clamp_coordinates"]
