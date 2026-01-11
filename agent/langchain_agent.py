"""
Main LangChain agent for the drawing system.
Uses ReAct pattern with custom tools.
"""
import json
from typing import Optional, Dict, Any, List, Tuple

try:
    # Try new LangChain API (0.1.0+)
    from langchain.agents import create_react_agent, AgentExecutor
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.memory import ConversationBufferMemory
    LANGCHAIN_NEW_API = True
except ImportError:
    # Fallback to old API
    try:
        from langchain.agents import initialize_agent, AgentType
        from langchain.memory import ConversationBufferMemory
        from langchain.schema import BaseMessage
        LANGCHAIN_NEW_API = False
    except ImportError:
        LANGCHAIN_NEW_API = None

from agent.langchain_wrapper import get_agent_llm
from agent.prompts.agent_system_prompt import get_agent_system_prompt
from agent.tools.planning_tool import CreatePlanTool
from agent.tools.coordinate_tool import GenerateCoordinatesTool
from agent.tools.verification_tool import VerifyCoordinatesTool
from agent.tools.user_question_tool import AskUserQuestionTool
from agent.tools.execution_tool import ExecuteDrawingTool
from agent.langchain_memory import memory_to_context, update_memory_from_agent
from state.memory import DrawingMemory
from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import CoordinateMapper
from utils.logger import get_logger

logger = get_logger(__name__)


class DrawingAgent:
    """LangChain-based agent for drawing system."""
    
    def __init__(self, plotter: PlotterDriver, memory: Optional[DrawingMemory] = None):
        """
        Initialize the drawing agent.
        
        Args:
            plotter: PlotterDriver instance
            memory: Optional existing memory (creates new if None)
        """
        self.plotter = plotter
        self.memory = memory or DrawingMemory()
        self.mapper = CoordinateMapper()
        
        # Initialize tools
        self.tools = [
            CreatePlanTool(self.memory),
            GenerateCoordinatesTool(self.memory),
            VerifyCoordinatesTool(self.memory),
            AskUserQuestionTool(self.memory),
            ExecuteDrawingTool(self.plotter, self.mapper)
        ]
        
        # Initialize LLM
        self.llm = get_agent_llm()
        
        # Initialize memory
        self.langchain_memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Initialize agent based on API version
        if LANGCHAIN_NEW_API:
            # New API (0.1.0+)
            prompt = ChatPromptTemplate.from_messages([
                ("system", get_agent_system_prompt()),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            agent = create_react_agent(self.llm, self.tools, prompt)
            self.agent = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                memory=self.langchain_memory,
                max_iterations=15,
                handle_parsing_errors=True
            )
        else:
            # Old API (fallback)
            self.agent = initialize_agent(
                tools=self.tools,
                llm=self.llm,
                agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
                verbose=True,
                memory=self.langchain_memory,
                max_iterations=15,
                agent_kwargs={
                    "system_message": get_agent_system_prompt()
                }
            )
        
        logger.info("LangChain agent initialized")
    
    def process_instruction(self, instruction: str) -> str:
        """
        Process a user instruction using the LangChain agent.
        
        Args:
            instruction: User's text instruction
        
        Returns:
            Assistant message to display
        """
        try:
            logger.info(f"[LangChain Agent] Processing instruction: {instruction}")
            
            # Check for stop command
            if instruction.lower().strip() in ["stop", "quit", "exit", "done"]:
                self.memory.set_stop_flag(True)
                self.plotter.stop()
                return "Stopped. Thank you!"
            
            # Check stop flag
            if self.memory.stop_flag:
                return "System is stopped. Type 'continue' to resume or 'quit' to exit."
            
            if instruction.lower().strip() == "continue":
                self.memory.reset_stop_flag()
                return "Resumed. What would you like to draw?"
            
            # Handle confirmation for multi-stage drawings
            confirmation_words = ["yes", "ok", "okay", "continue", "proceed", "go ahead"]
            if instruction.lower().strip() in confirmation_words:
                # Check if there's a plan in anchors
                if "plan" in self.memory.anchors:
                    logger.info("User confirmed, continuing multi-stage drawing")
                    # Agent will handle continuation
                else:
                    return "I'm ready. What would you like to draw?"
            
            # Get memory context
            memory_context = memory_to_context(self.memory)
            
            # Add memory context to instruction
            full_instruction = f"""Current drawing state:
{memory_context}

User instruction: {instruction}"""
            
            # If there's a pending question, add context
            if self.memory.last_question:
                full_instruction = f"""Previous question: {self.memory.last_question}

{full_instruction}

Note: The user's instruction may be an answer to the previous question."""
            
            # Run agent
            if LANGCHAIN_NEW_API:
                # New API uses invoke
                response = self.agent.invoke({"input": full_instruction})
                # Extract response text
                if isinstance(response, dict):
                    response = response.get("output", str(response))
            else:
                # Old API uses run
                response = self.agent.run(full_instruction)
            
            # Parse agent response
            result = self._parse_agent_response(response)
            
            # Update memory if needed
            if "strokes" in result or "anchors" in result:
                update_memory_from_agent(result, self.memory)
            
            # Extract message to return to user
            if "assistant_message" in result:
                return result["assistant_message"]
            elif isinstance(response, str):
                # Clean up response
                if response.startswith("QUESTION:"):
                    return response.replace("QUESTION:", "").strip()
                return response
            else:
                return str(response)
            
        except Exception as e:
            logger.error(f"[LangChain Agent] Error: {e}", exc_info=True)
            return f"An error occurred: {e}. Please try again."
    
    def _parse_agent_response(self, response: str) -> Dict[str, Any]:
        """
        Parse agent response to extract structured data.
        
        Args:
            response: Raw agent response
        
        Returns:
            Dictionary with strokes, anchors, labels, assistant_message
        """
        result = {
            "strokes": [],
            "anchors": {},
            "labels": {},
            "assistant_message": response
        }
        
        # Try to extract JSON from response
        try:
            # Look for JSON in response
            start_idx = response.find('{')
            if start_idx != -1:
                brace_count = 0
                for i in range(start_idx, len(response)):
                    if response[i] == '{':
                        brace_count += 1
                    elif response[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = response[start_idx:i+1]
                            data = json.loads(json_str)
                            if "strokes" in data:
                                result["strokes"] = data["strokes"]
                            if "anchors" in data:
                                result["anchors"] = data["anchors"]
                            if "labels" in data:
                                result["labels"] = data["labels"]
                            if "assistant_message" in data:
                                result["assistant_message"] = data["assistant_message"]
                            break
        except Exception as e:
            logger.debug(f"Could not parse JSON from response: {e}")
        
        return result
