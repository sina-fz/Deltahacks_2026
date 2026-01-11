"""
Main loop for the drawing system.
Coordinates UI, LLM, and execution layers.
"""
from typing import Optional, List, Tuple
from state.memory import DrawingMemory
from agent.llm_wrapper import LLMWrapper, LLMResponse
from agent.prompt_builder import build_prompt, build_repair_prompt
from agent.semantic_validator import SemanticValidator
from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import CoordinateMapper, validate_and_clamp_coordinates
from config import MAX_STROKES_PER_STEP, MAX_POINTS_PER_STROKE, CHUNK_SIZE, USE_LANGCHAIN_AGENT, PREVIEW_MODE
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
        self.validator = SemanticValidator()
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
            logger.info(f"Checking for plan in memory. Anchors: {list(self.memory.anchors.keys())}")
            if "plan" in self.memory.anchors:
                logger.info("User confirmed plan - executing drawing")
                # Modify instruction to tell LLM to execute the plan
                instruction = "execute the plan and draw all components"
            elif self.memory.anchors.get("_auto_continue"):
                # Model indicated it needs to continue - automatically continue
                logger.info("Auto-continuing multi-step drawing...")
                # Clear the auto-continue flag
                del self.memory.anchors["_auto_continue"]
                # Use a continuation instruction
                instruction = "continue drawing the remaining components"
            else:
                logger.warning(f"No plan found in anchors when user confirmed. Available anchors: {list(self.memory.anchors.keys())}")
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
                logger.error("[MEMORY VERIFICATION] [FAIL] CRITICAL: 'CURRENT DRAWING STATE:' section missing from prompt!")
            
            # Call LLM
            response = self.llm.call_llm(prompt)
            logger.info(f"LLM returned {len(response.strokes)} strokes, {len(response.anchors)} anchors")
            logger.debug(f"LLM assistant_message: {response.assistant_message[:200] if response.assistant_message else 'EMPTY'}...")
            
            # SELF-ITERATION: Validate and repair if needed (only if strokes were generated)
            if response.strokes:
                response = self._validate_and_repair(instruction, response, max_iterations=1)
            
            # Check if we're executing a plan (skip plan detection in this case)
            is_executing_plan = instruction.lower().strip() in ["execute the plan", "execute the plan and draw all components"]
            
            # Check if LLM is showing a plan (planning phase) - but NOT if we're executing
            # Plan detection: has plan in anchors, no strokes, and either current_stage==0 or current_stage is missing (defaults to planning)
            has_plan = "plan" in response.anchors
            is_planning_stage = response.anchors.get("current_stage") == 0 or (has_plan and "current_stage" not in response.anchors)
            if not is_executing_plan and not response.strokes and has_plan and is_planning_stage:
                # LLM is showing a plan, waiting for approval
                plan_text = response.assistant_message or "Here is my plan. Should I proceed?"
                logger.info(f"LLM showing plan, waiting for user approval: {plan_text[:100]}...")
                # Store the plan in memory BEFORE returning
                logger.info(f"Storing plan in memory. Response anchors keys: {list(response.anchors.keys())}")
                self.memory.update_anchors(response.anchors)
                logger.info(f"Plan stored. Memory anchors now: {list(self.memory.anchors.keys())}")
                # Verify plan is stored
                if "plan" not in self.memory.anchors:
                    logger.error("CRITICAL: Plan was NOT stored in memory after update_anchors!")
                else:
                    logger.info(f"Plan successfully stored: {self.memory.anchors.get('plan', '')[:100]}...")
                # Store the question so we can recognize approval
                self.memory.last_question = plan_text
                return plan_text
            
            # Check if LLM is asking a follow-up question (no strokes, not done, no plan)
            if not response.strokes and not response.done:
                # LLM is asking a clarifying question
                question_text = response.assistant_message
                
                # Check if the message is generic or empty
                generic_patterns = [
                    "ready for next instruction",
                    "i need more information",
                    "could you clarify",
                    "can you clarify",
                    "please clarify"
                ]
                
                is_generic = False
                if not question_text or question_text.strip() == "Ready for next instruction.":
                    is_generic = True
                else:
                    msg_lower = question_text.lower()
                    # Check if it's generic AND doesn't have a specific question (no ? or no options)
                    if any(pattern in msg_lower for pattern in generic_patterns):
                        if "?" not in question_text or len(question_text) < 50:
                            is_generic = True
                
                if is_generic:
                    # Instead of asking, just draw with defaults!
                    logger.warning("LLM returned generic message - forcing draw with defaults instead of asking")
                    # Return a message that we'll draw with defaults
                    return "I'll draw with reasonable defaults based on your request. If you'd like something specific, please let me know."
                else:
                    logger.info(f"LLM asking clarifying question: {question_text[:100]}...")
                
                # Store the question so we can recognize answers to it
                self.memory.last_question = question_text
                return question_text
            
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
                
                # Determine stroke state based on preview mode
                stroke_state = "preview" if PREVIEW_MODE else "confirmed"
                
                # Execute strokes on hardware only if not in preview mode OR if confirming
                if not PREVIEW_MODE or stroke_state == "confirmed":
                    self._execute_strokes_chunked(validated_strokes)
                else:
                    logger.info(f"Preview mode: skipping hardware execution for {len(validated_strokes)} strokes")
                
                # Update memory
                stroke_ids = self.memory.add_strokes(validated_strokes, response.labels, state=stroke_state)
                self.memory.update_anchors(response.anchors)
                self.memory.update_features(response.labels, stroke_ids)
                
                # Check if there are more components to draw (incremental drawing)
                components_remaining = response.anchors.get("components_remaining", [])
                component_drawn = response.anchors.get("component_drawn")
                
                if components_remaining and len(components_remaining) > 0:
                    # More components to draw - automatically continue
                    logger.info(f"Incremental drawing: drew {component_drawn}, {len(components_remaining)} components remaining")
                    logger.info(f"Automatically continuing to draw next component: {components_remaining[0]}")
                    
                    # Recursively call process_instruction to draw next component
                    next_message = self.process_instruction("yes")
                    
                    # Return combined message
                    return f"{response.assistant_message}\n{next_message}"
                elif component_drawn and (not components_remaining or len(components_remaining) == 0):
                    # All components drawn - clear plan
                    logger.info(f"Incremental drawing complete: all components drawn")
                    if "plan" in self.memory.anchors:
                        del self.memory.anchors["plan"]
                    if "components" in self.memory.anchors:
                        del self.memory.anchors["components"]
                    if "component_drawn" in self.memory.anchors:
                        del self.memory.anchors["component_drawn"]
                    if "components_remaining" in self.memory.anchors:
                        del self.memory.anchors["components_remaining"]
                    self.memory.last_question = None
                
                # Check if this is part of a multi-stage drawing (legacy support)
                elif "current_stage" in response.anchors and "total_stages" in response.anchors:
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
                        if "component_drawn" in self.memory.anchors:
                            del self.memory.anchors["component_drawn"]
                        if "components_remaining" in self.memory.anchors:
                            del self.memory.anchors["components_remaining"]
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
    
    def _validate_and_repair(
        self,
        instruction: str,
        response: LLMResponse,
        max_iterations: int = 2
    ) -> LLMResponse:
        """
        Validate LLM response and repair if needed (self-iteration loop).
        
        Args:
            instruction: User instruction
            response: Initial LLM response
            max_iterations: Maximum repair iterations
        
        Returns:
            Best response (original or repaired)
        """
        best_response = response
        best_score = 0.0
        
        for iteration in range(max_iterations + 1):
            # Validate current response
            existing_strokes = [stroke.points for stroke in self.memory.strokes_history]
            validation = self.validator.validate(
                strokes=response.strokes,
                labels=response.labels,
                anchors=response.anchors,
                existing_strokes=existing_strokes,
                instruction=instruction
            )
            
            logger.info(f"[ITERATION {iteration}] Validation score: {validation.score:.2f}, valid: {validation.valid}")
            
            # Track best response
            if validation.score > best_score:
                best_score = validation.score
                best_response = response
            
            # If valid, we're done
            if validation.valid:
                logger.info(f"[ITERATION {iteration}] Validation PASSED - using this response")
                return response
            
            # If not valid and we have iterations left, try to repair
            if iteration < max_iterations:
                logger.info(f"[ITERATION {iteration}] Validation FAILED - attempting repair (iteration {iteration + 1}/{max_iterations})")
                
                # Build repair prompt
                issues_text = validation.get_repair_hints()
                repair_prompt = build_repair_prompt(
                    instruction=instruction,
                    memory=self.memory,
                    failed_strokes=response.strokes,
                    failed_labels=response.labels,
                    failed_anchors=response.anchors,
                    issues=issues_text
                )
                
                # Call LLM for repair
                try:
                    response = self.llm.call_llm(repair_prompt)
                    logger.info(f"[ITERATION {iteration + 1}] Repair generated {len(response.strokes)} strokes")
                except Exception as e:
                    logger.error(f"[ITERATION {iteration + 1}] Repair failed: {e}")
                    break
            else:
                logger.warning(f"[ITERATION {iteration}] Max iterations reached - using best response (score={best_score:.2f})")
        
        return best_response
    
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
