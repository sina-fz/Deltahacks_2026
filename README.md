# Voice/Text-Driven Drawing System

A hackathon MVP for a voice/text-driven "draw-with-me" system that controls a physical BrachioGraph-style servo drawing arm. The system uses an LLM to translate user instructions into incremental drawing actions, executed step-by-step with memory of what has been drawn.

## Features

- **Iterative Drawing**: Build drawings step-by-step through natural language instructions
- **Memory System**: Remembers what's been drawn with semantic anchors and labels
- **Safety First**: Bounds checking, stop flags, and validation at every step
- **Simulation Mode**: Test the system without hardware
- **Modular Architecture**: Clean separation between UI, Agent, and Execution layers

## System Architecture

### Three-Layer Design

1. **UI Layer** (`ui/`): User interaction (CLI interface)
2. **Agent/Planner Layer** (`agent/`): LLM integration with strict JSON output
3. **Execution Layer** (`execution/`): BrachioGraph control with coordinate mapping

### Key Components

- **State/Memory** (`state/`): Maintains drawing history, anchors, and features
- **Coordinate System**: Normalized [0.0, 1.0] coordinates mapped to physical bounds
- **Main Loop** (`main_loop.py`): Coordinates all components with chunked execution

## Installation

1. **Clone the repository**:
   ```bash
   cd Deltahacks_2026
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key
   ```

4. **Configure your API key**:
   - For OpenAI: Set `OPENAI_API_KEY` in `.env` and `LLM_PROVIDER=openai`
   - For Anthropic: Set `ANTHROPIC_API_KEY` in `.env` and `LLM_PROVIDER=anthropic`
   - For OpenRouter: Set `OPENROUTER_API_KEY` in `.env` and `LLM_PROVIDER=openrouter`
     - Model format: `LLM_MODEL=openai/gpt-4o-mini` (prefix with provider name)

## Configuration

Edit `config.py` or set environment variables:

- **Drawing Bounds**: Adjust `DRAWING_BOX` to match your BrachioGraph's physical limits
- **Safety Constraints**: `MAX_STROKES_PER_STEP`, `MAX_POINTS_PER_STROKE`
- **Simulation Mode**: Set `SIMULATION_MODE=true` to test without hardware

## Usage

### Running the System

**Standard mode** (clean output):
```bash
python main.py
```

**Interactive demo mode** (verbose output - shows LLM prompts, responses, coordinates):
```bash
python demo_interactive.py
```

The demo mode is perfect for testing before hardware integration - it shows:
- Current drawing state
- LLM prompts and raw JSON responses
- Parsed coordinates (normalized and physical)
- Execution plans
- Memory updates

See `DEMO_INSTRUCTIONS.md` for detailed demo instructions.

### Example Session

```
Drawing system ready! Type your instructions (or 'stop' to quit).
Example: 'draw a circle', 'add a hat', 'make it bigger'
Type 'help' for commands.

> draw a circle
[SIM] Drawing polyline with 20 points...
I've drawn a circle. What would you like to add next?

> add a hat on top
[SIM] Drawing polyline with 10 points...
I've added a hat on top of the circle. What would you like to add next?

> stop
Stopped. Thank you!
```

### Commands

- **Drawing Instructions**: Natural language (e.g., "draw a circle", "add ears")
- **`stop`** or **`quit`**: Stop the system
- **`continue`**: Resume after stop
- **`undo [N]`**: Undo last N strokes (logical only - physical ink remains)
- **`status`**: Show current drawing state
- **`help`**: Show help message

## How It Works

1. **User Input**: User provides a text instruction
2. **LLM Processing**: System builds a prompt with:
   - User instruction
   - Current drawing state (anchors, features, strokes)
   - Coordinate system and constraints
3. **JSON Response**: LLM returns structured JSON with:
   - Strokes (polylines to draw)
   - Anchors (semantic points for future reference)
   - Labels (feature names)
   - Assistant message
4. **Validation**: Coordinates validated and clamped to bounds
5. **Execution**: Strokes executed in chunks with stop flag checks
6. **Memory Update**: New strokes, anchors, and labels added to memory
7. **Feedback**: Assistant message displayed, loop continues

## Coordinate System

- **Internal**: Normalized [0.0, 1.0] for both X and Y
- **Physical**: Mapped to drawing box (default: 200mm x 200mm)
- **Safety**: All coordinates automatically clamped to valid ranges

## Simulation Mode

By default, the system runs in simulation mode (no hardware required). In simulation mode:
- All movements are logged but not executed
- Perfect for testing LLM logic and system flow
- Set `SIMULATION_MODE=false` in `.env` when ready for hardware

## BrachioGraph Integration

The `PlotterDriver` class provides an abstraction layer. To integrate with actual BrachioGraph hardware:

1. Install BrachioGraph: `pip install brachiograph` (if available)
2. Update `execution/plotter_driver.py` with actual BrachioGraph API calls
3. Set `SIMULATION_MODE=false`

The driver supports:
- `initialize()`: Home the plotter
- `pen_up()` / `pen_down()`: Control pen state
- `move_to(x, y, draw)`: Move to position
- `draw_polyline(points)`: Draw a connected line
- `stop()`: Immediate safe stop

## Testing

The system includes comprehensive logging. Check `drawing_system.log` for:
- User inputs
- LLM prompts and responses
- Parsed strokes
- Execution chunks
- State updates

## Project Structure

```
Deltahacks_2026/
├── main.py                 # Main entrypoint
├── main_loop.py            # Main system loop
├── config.py               # Configuration
├── requirements.txt        # Dependencies
├── ui/
│   └── cli.py             # CLI interface
├── agent/
│   ├── llm_wrapper.py    # LLM integration
│   └── prompt_builder.py # Prompt construction
├── execution/
│   ├── plotter_driver.py  # BrachioGraph abstraction
│   └── coordinate_mapper.py # Coordinate mapping
├── state/
│   └── memory.py         # State management
└── utils/
    └── logger.py         # Logging utilities
```

## Safety Features

- **Bounds Validation**: All coordinates clamped to drawing box
- **Stop Flag**: Can interrupt execution at any time
- **Chunked Execution**: Small batches with stop checks between
- **Input Validation**: Max strokes/points per step enforced
- **Error Handling**: Graceful degradation on errors

## Future Enhancements

- Voice input integration
- Webcam visual feedback (optional)
- Web UI (Flask/FastAPI)
- True physical undo (requires pen control)
- Multi-step planning mode

## Troubleshooting

**LLM API Errors**:
- Check API key in `.env`
- Verify `LLM_PROVIDER` matches your API key
- Check internet connection

**Coordinate Errors**:
- Verify `DRAWING_BOX` matches your hardware
- Check that coordinates are in [0.0, 1.0] range

**Import Errors**:
- Run `pip install -r requirements.txt`
- Check Python version (3.8+)

## License

Hackathon project for DeltaHacks 2026.

## Contributors

Built for DeltaHacks 2026 hackathon.
