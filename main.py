"""
Main entrypoint for the drawing system.
"""
import sys
from config import LLM_PROVIDER, LLM_MODEL, SIMULATION_MODE
from agent.llm_wrapper import LLMWrapper
from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import CoordinateMapper
from state.memory import DrawingMemory
from main_loop import DrawingSystem
from ui.cli import CLIInterface
from utils.logger import setup_logger

# Setup logging
logger = setup_logger()


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("Drawing System Starting")
    logger.info(f"LLM Provider: {LLM_PROVIDER}")
    logger.info(f"LLM Model: {LLM_MODEL}")
    logger.info(f"Simulation Mode: {SIMULATION_MODE}")
    logger.info("=" * 60)
    
    try:
        # Initialize components
        logger.info("Initializing components...")
        
        # LLM Wrapper
        try:
            llm = LLMWrapper(provider=LLM_PROVIDER, model=LLM_MODEL)
            logger.info("LLM wrapper initialized")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            print(f"\nERROR: Failed to initialize LLM: {e}")
            print("Please check your API keys in .env file or environment variables.")
            print("Required: OPENAI_API_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY")
            print(f"Current LLM_PROVIDER setting: {LLM_PROVIDER}")
            sys.exit(1)
        
        # Coordinate Mapper
        mapper = CoordinateMapper()
        logger.info("Coordinate mapper initialized")
        
        # Plotter Driver
        plotter = PlotterDriver(mapper, simulation=SIMULATION_MODE)
        logger.info("Plotter driver initialized")
        
        # Memory
        memory = DrawingMemory()
        logger.info("Memory initialized")
        
        # Drawing System
        system = DrawingSystem(llm, plotter, memory)
        logger.info("Drawing system initialized")
        
        # CLI Interface
        cli = CLIInterface()
        logger.info("CLI interface initialized")
        
        # Run interactive loop
        logger.info("Starting interactive loop...")
        system.run_interactive_loop(
            input_handler=cli.get_input,
            output_handler=cli.display,
            special_command_handler=cli.handle_special_command
        )
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        print("\n\nInterrupted. Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
