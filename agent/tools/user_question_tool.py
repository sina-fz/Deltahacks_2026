"""
User question tool for LangChain agent.
Asks clarifying questions to the user.
"""
from langchain.tools import BaseTool
from typing import Optional, Type
from pydantic import BaseModel, Field

from state.memory import DrawingMemory
from utils.logger import get_logger

logger = get_logger(__name__)


class UserQuestionToolInput(BaseModel):
    """Input schema for user question tool."""
    question: str = Field(description="Question to ask the user")


class AskUserQuestionTool(BaseTool):
    """Tool for asking user questions."""
    
    name = "ask_user_question"
    description = """Use this tool when you need to ask the user a clarifying question.
    Examples: 'Which side of the square?', 'What type of roof?', 'Proceed with the plan?'
    Input: The question text.
    Output: The question (user will answer in next turn)."""
    
    args_schema: Type[BaseModel] = UserQuestionToolInput
    
    def __init__(self, memory: DrawingMemory):
        super().__init__()
        self.memory = memory
    
    def _run(self, question: str) -> str:
        """Execute the user question tool."""
        try:
            logger.info(f"[User Question Tool] Asking: {question}")
            
            # Store question in memory
            self.memory.last_question = question
            
            # Return question (agent will return this to user)
            return f"QUESTION: {question}"
            
        except Exception as e:
            logger.error(f"[User Question Tool] Error: {e}", exc_info=True)
            return f"QUESTION: {question}"
