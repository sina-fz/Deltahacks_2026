"""
Coordinate generation tool for LangChain agent.
Generates precise coordinates for drawing components.
"""
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import json

from agent.langchain_wrapper import get_coordinate_llm
from agent.prompts.coordinate_prompt import get_coordinate_prompt
from agent.langchain_memory import memory_to_context
from state.memory import DrawingMemory
from utils.logger import get_logger
from langchain.chains import LLMChain

logger = get_logger(__name__)


class CoordinateToolInput(BaseModel):
    """Input schema for coordinate tool."""
    component_name: str = Field(description="Name of the component (e.g., 'house_base')")
    component_type: str = Field(description="Type of component (e.g., 'rectangle', 'triangle', 'circle')")
    grid_position: str = Field(description="Grid position (e.g., 'grid(3,3) to (7,6)')")
    size: str = Field(description="Size in grid cells (e.g., '4x3 cells')")
    description: str = Field(description="Component description")
    memory_context: str = Field(description="Current drawing state/memory context")


class GenerateCoordinatesTool(BaseTool):
    """Tool for generating coordinates."""
    
    name = "generate_coordinates"
    description = """Use this tool to generate precise normalized coordinates for drawing a component.
    Input: Component name, type, grid position, size, description, and current drawing state.
    Output: JSON with strokes (coordinate points), anchors, and labels."""
    
    args_schema: Type[BaseModel] = CoordinateToolInput
    
    def __init__(self, memory: DrawingMemory):
        super().__init__()
        self.memory = memory
        self.llm = get_coordinate_llm()
        self.prompt = get_coordinate_prompt()
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def _run(self, component_name: str, component_type: str, grid_position: str,
             size: str, description: str, memory_context: str) -> str:
        """Execute the coordinate generation tool."""
        try:
            logger.info(f"[Coordinate Tool] Generating coordinates for: {component_name}")
            
            # Invoke chain
            response = self.chain.run(
                component_name=component_name,
                component_type=component_type,
                grid_position=grid_position,
                size=size,
                description=description,
                memory_context=memory_context
            )
            
            # Extract content
            content = response if isinstance(response, str) else str(response)
            
            # Try to extract JSON
            json_str = self._extract_json(content)
            
            logger.info(f"[Coordinate Tool] Coordinates generated: {json_str[:200]}...")
            return json_str
            
        except Exception as e:
            logger.error(f"[Coordinate Tool] Error: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "strokes": [],
                "anchors": {},
                "labels": {}
            })
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response."""
        # Remove markdown code blocks
        text = text.replace("```json", "").replace("```", "").strip()
        
        # Try to find JSON object
        start_idx = text.find('{')
        if start_idx != -1:
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start_idx:i+1]
        
        return text
