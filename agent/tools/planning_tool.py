"""
Planning tool for LangChain agent.
Decomposes objects into components and creates step-by-step plans.
"""
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import json

from agent.langchain_wrapper import get_planning_llm
from agent.prompts.planning_prompt import get_planning_prompt
from agent.langchain_memory import memory_to_context
from state.memory import DrawingMemory
from utils.logger import get_logger
from langchain.chains import LLMChain

logger = get_logger(__name__)


class PlanningToolInput(BaseModel):
    """Input schema for planning tool."""
    instruction: str = Field(description="User's instruction (e.g., 'draw a house')")
    memory_context: str = Field(description="Current drawing state/memory context")


class CreatePlanTool(BaseTool):
    """Tool for creating drawing plans."""
    
    name = "create_plan"
    description = """Use this tool when the user wants to draw a complex object (house, person, tree, car, etc.).
    This tool decomposes the object into components and creates a step-by-step plan.
    Input: User's instruction and current drawing state.
    Output: JSON plan with components, grid positions, and sizes."""
    
    args_schema: Type[BaseModel] = PlanningToolInput
    
    def __init__(self, memory: DrawingMemory):
        super().__init__()
        self.memory = memory
        self.llm = get_planning_llm()
        self.prompt = get_planning_prompt()
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def _run(self, instruction: str, memory_context: str) -> str:
        """Execute the planning tool."""
        try:
            logger.info(f"[Planning Tool] Creating plan for: {instruction}")
            
            # Invoke chain
            response = self.chain.run(
                instruction=instruction,
                memory_context=memory_context
            )
            
            # Extract content
            content = response if isinstance(response, str) else str(response)
            
            # Try to extract JSON
            json_str = self._extract_json(content)
            
            logger.info(f"[Planning Tool] Plan created: {json_str[:200]}...")
            return json_str
            
        except Exception as e:
            logger.error(f"[Planning Tool] Error: {e}", exc_info=True)
            return json.dumps({
                "error": str(e),
                "components": {},
                "plan_summary": "Failed to create plan",
                "total_stages": 0
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
