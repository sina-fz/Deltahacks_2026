"""
Verification tool for LangChain agent.
Verifies that generated coordinates make semantic sense.
"""
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field
import json

from agent.langchain_wrapper import get_verification_llm
from agent.prompts.verification_prompt import get_verification_prompt
from agent.verification_rules import get_verification_rules
from state.memory import DrawingMemory
from utils.logger import get_logger
from langchain.chains import LLMChain

logger = get_logger(__name__)


class VerificationToolInput(BaseModel):
    """Input schema for verification tool."""
    component_name: str = Field(description="Name of the component")
    component_type: str = Field(description="Type of component")
    coordinates: str = Field(description="Generated coordinates (JSON string)")
    memory_context: str = Field(description="Current drawing state/memory context")


class VerifyCoordinatesTool(BaseTool):
    """Tool for verifying coordinates."""
    
    name = "verify_coordinates"
    description = """Use this tool to verify that generated coordinates make semantic and spatial sense.
    Checks if coordinates follow rules (e.g., roof above base, door inside base).
    Input: Component name, type, coordinates, and current drawing state.
    Output: JSON with validation result (valid/invalid) and reason."""
    
    args_schema: Type[BaseModel] = VerificationToolInput
    
    def __init__(self, memory: DrawingMemory):
        super().__init__()
        self.memory = memory
        self.llm = get_verification_llm()
        self.prompt = get_verification_prompt()
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt)
    
    def _run(self, component_name: str, component_type: str, coordinates: str,
             memory_context: str) -> str:
        """Execute the verification tool."""
        try:
            logger.info(f"[Verification Tool] Verifying coordinates for: {component_name}")
            
            # Get verification rules
            rules = get_verification_rules(component_type, component_name, self.memory)
            
            # Invoke chain
            response = self.chain.run(
                component_name=component_name,
                component_type=component_type,
                coordinates=coordinates,
                rules=rules,
                memory_context=memory_context
            )
            
            # Extract content
            content = response if isinstance(response, str) else str(response)
            
            # Try to extract JSON
            json_str = self._extract_json(content)
            
            logger.info(f"[Verification Tool] Verification result: {json_str[:200]}...")
            return json_str
            
        except Exception as e:
            logger.error(f"[Verification Tool] Error: {e}", exc_info=True)
            return json.dumps({
                "valid": False,
                "reason": f"Verification error: {str(e)}",
                "issues": [str(e)],
                "suggestions": []
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
