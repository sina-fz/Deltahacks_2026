"""
Main loop for the drawing system.
Coordinates UI, LLM, and execution layers.
"""
from typing import Optional, List, Tuple
from state.memory import DrawingMemory
from agent.llm_wrapper import LLMWrapper
from agent.prompt_builder import build_prompt
from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import CoordinateMapper, validate_and_clamp_coordinates
from config import MAX_STROKES_PER_STEP, MAX_POINTS_PER_STROKE, CHUNK_SIZE, USE_LANGCHAIN_AGENT
from utils.logger import get_logger

# Conditional import for LangChain agent
try:
    from agent.langchain_agent import DrawingAgent
    LANGCHAIN_AGENT_AVAILABLE = True
except ImportError:
    LANGCHAIN_AGENT_AVAILABLE = False
    DrawingAgent = None

logger = get_logger(__name__)


class DrawingSystem:
    """Main system that coordinates all components."""
    
    def __init__(self, llm_wrapper: LLMWrapper, plotter: PlotterDriver, 
                 memory: Optional[DrawingMemory] = None):
        """
        Initialize the drawing system.
        
        Args:
            llm_wrapper: LLMWrapper instance (used only if not using LangChain agent)
            plotter: PlotterDriver instance
            memory: Optional existing memory (creates new if None)
        """
        self.llm = llm_wrapper
        self.plotter = plotter
        self.memory = memory or DrawingMemory()
        self.mapper = CoordinateMapper()
        self.running = False
        
        # Initialize LangChain agent if enabled
        self.langchain_agent = None
        if USE_LANGCHAIN_AGENT and LANGCHAIN_AGENT_AVAILABLE:
            try:
                # Check if LangChain is available
                from agent.langchain_wrapper import LANGCHAIN_AVAILABLE
                if not LANGCHAIN_AVAILABLE:
                    logger.warning("LangChain packages not installed. Install with: pip install langchain langchain-openai langchain-anthropic langchain-community")
                    logger.info("Falling back to legacy system.")
                else:
                    self.langchain_agent = DrawingAgent(self.plotter, self.memory)
                    logger.info("Using LangChain agent")
            except ImportError as e:
                logger.warning(f"LangChain packages not available: {e}. Falling back to legacy system.")
                self.langchain_agent = None
            except Exception as e:
                logger.warning(f"Failed to initialize LangChain agent: {e}. Falling back to legacy system.")
                self.langchain_agent = None
        elif USE_LANGCHAIN_AGENT and not LANGCHAIN_AGENT_AVAILABLE:
            logger.warning("LangChain agent not available (import failed). Falling back to legacy system.")
    
    def process_instruction(self, instruction: str) -> str:
        """
        Process a single user instruction.
        
        Args:
            instruction: User's text instruction
        
        Returns:
            Assistant message to display
        """
        # Use LangChain agent if enabled
        if self.langchain_agent:
            return self.langchain_agent.process_instruction(instruction)
        
        # Legacy system (original implementation)
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
                # Let LLM handle the continuation based on plan in anchors
            else:
                return "I'm ready. What would you like to draw?"
        
        logger.info(f"Processing instruction: {instruction}")
        
        try:
            # Build prompt
            prompt = build_prompt(instruction, self.memory)
            logger.debug(f"Prompt built ({len(prompt)} chars)")
            
            # VERIFICATION: Log what memory is being sent to LLM
            state_summary = self.memory.get_state_summary()
            logger.info(f"[MEMORY VERIFICATION] State summary length: {len(state_summary)} chars")
            logger.info(f"[MEMORY VERIFICATION] Strokes in memory: {len(self.memory.strokes_history)}")
            logger.info(f"[MEMORY VERIFICATION] Anchors in memory: {len(self.memory.anchors)}")
            if "CURRENT DRAWING STATE:" in prompt:
                state_in_prompt = prompt.split("CURRENT DRAWING STATE:")[1].split("COORDINATE SYSTEM:")[0]
                logger.info(f"[MEMORY VERIFICATION] State section in prompt: {len(state_in_prompt)} chars")
                if len(self.memory.strokes_history) > 0:
                    first_stroke_label = self.memory.strokes_history[0].label or "unlabeled"
                    if first_stroke_label.upper() in state_in_prompt:
                        logger.info(f"[MEMORY VERIFICATION] [OK] First stroke '{first_stroke_label}' found in prompt")
                    else:
                        logger.warning(f"[MEMORY VERIFICATION] [FAIL] First stroke '{first_stroke_label}' NOT found in prompt!")
            else:
                logger.error("[MEMORY VERIFICATION] [CRITICAL] 'CURRENT DRAWING STATE:' section missing from prompt!")
            
            # Call LLM
            response = self.llm.call_llm(prompt)
            logger.info(f"LLM returned {len(response.strokes)} strokes, {len(response.anchors)} anchors")
            
            # Check if LLM is showing a plan (planning phase)
            if not response.strokes and "plan" in response.anchors and response.anchors.get("current_stage") == 0:
                # LLM is showing a plan, waiting for approval
                logger.info("LLM showing plan, waiting for user approval")
                # Store the plan in memory
                self.memory.update_anchors(response.anchors)
                # Store the question so we can recognize approval
                self.memory.last_question = response.assistant_message
                return response.assistant_message
            
            # Check if LLM is asking a follow-up question (no strokes, not done, no plan)
            if not response.strokes and not response.done:
                # LLM is asking a clarifying question
                logger.info("LLM asking clarifying question")
                # Store the question so we can recognize answers to it
                self.memory.last_question = response.assistant_message
                return response.assistant_message
            
            # If no strokes but done=true, task is complete (no drawing needed)
            if not response.strokes and response.done:
                logger.info("Task complete (no strokes needed)")
                return response.assistant_message
            
            # Only execute if there are strokes to draw
            if response.strokes:
                # Validate response
                self.llm.validate_response(response, MAX_STROKES_PER_STEP, MAX_POINTS_PER_STROKE)
                
                # Validate and clamp coordinates
                validated_strokes = validate_and_clamp_coordinates(response.strokes, self.mapper)
                
                # Execute strokes in chunks
                self._execute_strokes_chunked(validated_strokes)
                
                # Update memory
                stroke_ids = self.memory.add_strokes(validated_strokes, response.labels)
                self.memory.update_anchors(response.anchors)
                self.memory.update_features(response.labels, stroke_ids)
                
                # Check if this is part of a multi-stage drawing
                if "current_stage" in response.anchors and "total_stages" in response.anchors:
                    current = response.anchors.get("current_stage", 0)
                    total = response.anchors.get("total_stages", 0)
                    if current < total:
                        # More stages to go - keep the plan, don't clear question
                        logger.info(f"Multi-stage drawing: stage {current}/{total} complete")
                    else:
                        # All stages complete - clear plan and question
                        if "plan" in self.memory.anchors:
                            del self.memory.anchors["plan"]
                        if "components" in self.memory.anchors:
                            del self.memory.anchors["components"]
                        self.memory.last_question = None
                        logger.info("Multi-stage drawing complete")
                else:
                    # Single-stage drawing - clear question
                    self.memory.last_question = None
                
                logger.info(f"Updated memory: {len(self.memory.strokes_history)} total strokes")
            
            return response.assistant_message
            
        except ValueError as e:
            logger.error(f"Validation error: {e}")
            return f"Error: {e}. Please try again with a clearer instruction."
        except Exception as e:
            logger.error(f"Error processing instruction: {e}", exc_info=True)
            return f"An error occurred: {e}. Please try again."
    
    def _execute_strokes_chunked(self, strokes: List[List[Tuple[float, float]]]) -> None:
        """
        Execute strokes in chunks, checking stop flag between chunks.
        
        Args:
            strokes: List of polylines to draw
        """
        if not strokes:
            return
        
        # Split into chunks
        chunks = []
        for i in range(0, len(strokes), CHUNK_SIZE):
            chunk = strokes[i:i + CHUNK_SIZE]
            chunks.append(chunk)
        
        logger.info(f"Executing {len(strokes)} strokes in {len(chunks)} chunks")
        
        for chunk_idx, chunk in enumerate(chunks):
            # Check stop flag before each chunk
            if self.memory.stop_flag:
                logger.warning("Stop flag set - interrupting execution")
                self.plotter.stop()
                return
            
            logger.debug(f"Executing chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} strokes)")
            
            # Execute chunk
            self.plotter.execute_strokes(chunk, stop_flag=lambda: self.memory.stop_flag)
            
            # Small pause between chunks (for interrupt opportunity)
            # In real system, this could be a yield point
    
    def run_interactive_loop(self, input_handler, output_handler, special_command_handler=None):
        """
        Run the main interactive loop.
        
        Args:
            input_handler: Function that returns user input string
            output_handler: Function that displays messages to user
            special_command_handler: Optional function(command, system) -> bool for special commands
        """
        self.running = True
        self.plotter.initialize()
        
        output_handler("Drawing system ready! Type your instructions (or 'stop' to quit).")
        output_handler("Example: 'draw a circle', 'add a hat', 'make it bigger'")
        output_handler("Type 'help' for commands.\n")
        
        while self.running:
            try:
                # Get user input
                instruction = input_handler()
                
                if not instruction:
                    continue
                
                # Check for special commands
                if special_command_handler and special_command_handler(instruction, self):
                    continue
                
                # Process instruction
                response = self.process_instruction(instruction)
                output_handler(f"\n{response}\n")
                
                # Check if done
                if self.memory.stop_flag and "stop" in instruction.lower():
                    self.running = False
                    break
                    
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt - stopping")
                self.memory.set_stop_flag(True)
                self.plotter.stop()
                output_handler("\nStopped by user.")
                self.running = False
                break
            except EOFError:
                logger.info("EOF - stopping")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                output_handler(f"\nError: {e}\n")
        
        # Cleanup
        self.plotter.park()
        output_handler("System shut down. Goodbye!")
