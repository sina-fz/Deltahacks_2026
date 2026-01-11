"""
Minimal CLI interface for the drawing system.
"""
from typing import Callable
from utils.logger import get_logger

logger = get_logger(__name__)


class CLIInterface:
    """Simple CLI interface."""
    
    def __init__(self):
        self.prompt = "> "
    
    def get_input(self) -> str:
        """Get user input from command line."""
        try:
            return input(self.prompt).strip()
        except (EOFError, KeyboardInterrupt):
            raise
    
    def display(self, message: str) -> None:
        """Display a message to the user."""
        print(message)
        logger.info(f"UI: {message}")
    
    def display_error(self, message: str) -> None:
        """Display an error message."""
        print(f"ERROR: {message}")
        logger.error(f"UI Error: {message}")
    
    def display_success(self, message: str) -> None:
        """Display a success message."""
        print(f"✓ {message}")
        logger.info(f"UI Success: {message}")
    
    def show_help(self) -> None:
        """Show help message."""
        help_text = """
Drawing System Commands:
  - Type any drawing instruction (e.g., "draw a circle", "add a hat")
  - 'stop' or 'quit' - Stop the system
  - 'continue' - Resume after stop
  - 'undo' - Undo last strokes (logical only - ink remains)
  - 'help' - Show this help
  - 'status' - Show current drawing state
        """
        self.display(help_text)
    
    def handle_special_command(self, command: str, system) -> bool:
        """
        Handle special CLI commands.
        
        Returns:
            True if command was handled, False otherwise
        """
        cmd = command.lower().strip()
        
        if cmd == "help":
            self.show_help()
            return True
        elif cmd == "status":
            summary = system.memory.get_state_summary()
            self.display(f"\nCurrent Drawing State:\n{summary}\n")
            return True
        elif cmd.startswith("undo"):
            # Parse undo count
            parts = cmd.split()
            count = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            system.memory.undo_last_strokes(count)
            self.display_success(f"Undid last {count} stroke(s) (logical only - physical ink remains)")
            return True
        
        return False
