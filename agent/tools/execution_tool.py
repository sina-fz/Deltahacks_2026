"""
Execution tool for LangChain agent.
Executes validated coordinates on the plotter.
"""
from langchain.tools import BaseTool
from typing import Optional, Type, List, Tuple
from pydantic import BaseModel, Field
import json

from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import validate_and_clamp_coordinates, CoordinateMapper
from utils.logger import get_logger

logger = get_logger(__name__)


class ExecutionToolInput(BaseModel):
    """Input schema for execution tool."""
    strokes: str = Field(description="JSON string with strokes (list of coordinate points)")


class ExecuteDrawingTool(BaseTool):
    """Tool for executing drawings."""
    
    name = "execute_drawing"
    description = """Use this tool to execute validated coordinates on the plotter.
    This actually draws the component on the canvas.
    Input: JSON string with strokes (list of coordinate points).
    Output: Success message if drawing executed successfully."""
    
    args_schema: Type[BaseModel] = ExecutionToolInput
    
    def __init__(self, plotter: PlotterDriver, mapper: CoordinateMapper):
        super().__init__()
        self.plotter = plotter
        self.mapper = mapper
    
    def _run(self, strokes: str) -> str:
        """Execute the drawing tool."""
        try:
            logger.info(f"[Execution Tool] Executing drawing: {strokes[:200]}...")
            
            # Parse strokes JSON
            data = json.loads(strokes)
            if isinstance(data, dict) and "strokes" in data:
                strokes_list = data["strokes"]
            elif isinstance(data, list):
                strokes_list = data
            else:
                return json.dumps({"success": False, "error": "Invalid strokes format"})
            
            # Convert to list of tuples
            validated_strokes: List[List[Tuple[float, float]]] = []
            for stroke in strokes_list:
                stroke_tuples = [(float(p[0]), float(p[1])) for p in stroke]
                validated_strokes.append(stroke_tuples)
            
            # Validate and clamp coordinates
            validated_strokes = validate_and_clamp_coordinates(validated_strokes, self.mapper)
            
            # Execute strokes
            self.plotter.execute_strokes(validated_strokes)
            
            logger.info(f"[Execution Tool] Drawing executed successfully: {len(validated_strokes)} strokes")
            return json.dumps({
                "success": True,
                "strokes_executed": len(validated_strokes),
                "message": "Drawing executed successfully"
            })
            
        except Exception as e:
            logger.error(f"[Execution Tool] Error: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e),
                "message": f"Failed to execute drawing: {str(e)}"
            })
