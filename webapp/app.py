"""
Flask web application for voice-driven drawing system.
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sys
import os

# Add parent directory to path to import drawing system
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_loop import DrawingSystem
from agent.llm_wrapper import LLMWrapper
from execution.plotter_driver import PlotterDriver
from execution.coordinate_mapper import CoordinateMapper
from state.memory import DrawingMemory
from config import LLM_PROVIDER, LLM_MODEL, SIMULATION_MODE
from utils.logger import setup_logger

logger = setup_logger("webapp")

app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global drawing system instance
drawing_system = None


def initialize_drawing_system():
    """Initialize the drawing system."""
    global drawing_system
    
    try:
        logger.info("Initializing drawing system...")
        
        # Initialize components
        llm = LLMWrapper(provider=LLM_PROVIDER, model=LLM_MODEL)
        mapper = CoordinateMapper()
        plotter = PlotterDriver(mapper, simulation=SIMULATION_MODE)
        memory = DrawingMemory()
        
        drawing_system = DrawingSystem(llm, plotter, memory)
        plotter.initialize()
        
        logger.info("Drawing system initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize drawing system: {e}")
        return False


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current system status and all strokes."""
    if drawing_system is None:
        return jsonify({"status": "not_initialized"}), 503
    
    # Include all strokes in status response
    strokes = [
        {
            "id": s.id,
            "points": s.points,
            "label": s.label
        }
        for s in drawing_system.memory.strokes_history
    ]
    
    return jsonify({
        "status": "ready",
        "strokes_count": len(drawing_system.memory.strokes_history),
        "strokes": strokes,
        "simulation_mode": SIMULATION_MODE
    })


@app.route('/api/process', methods=['POST'])
def process_instruction():
    """Process a drawing instruction."""
    if drawing_system is None:
        return jsonify({"error": "System not initialized"}), 503
    
    data = request.json
    instruction = data.get('instruction', '').strip()
    
    if not instruction:
        return jsonify({"error": "No instruction provided"}), 400
    
    try:
        logger.info(f"Processing instruction: {instruction}")
        
        # Process instruction (this is fast - just LLM call and validation)
        response = drawing_system.process_instruction(instruction)
        
        # Get current state - ALL strokes from memory
        state_summary = drawing_system.memory.get_state_summary()
        strokes = [
            {
                "id": s.id,
                "points": s.points,
                "label": s.label
            }
            for s in drawing_system.memory.strokes_history
        ]
        
        logger.info(f"Returning {len(strokes)} strokes to frontend")
        
        # Emit update via WebSocket immediately (non-blocking)
        socketio.emit('drawing_update', {
            'strokes': strokes,
            'state': state_summary,
            'message': response
        })
        
        # Return response immediately
        return jsonify({
            "success": True,
            "message": response,
            "strokes": strokes,
            "state": state_summary
        })
        
    except Exception as e:
        logger.error(f"Error processing instruction: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset the drawing system."""
    global drawing_system
    
    try:
        if drawing_system:
            drawing_system.memory = DrawingMemory()
            drawing_system.plotter.initialize()
        
        socketio.emit('drawing_reset', {})
        
        return jsonify({"success": True, "message": "Drawing reset"})
    except Exception as e:
        logger.error(f"Error resetting: {e}")
        return jsonify({"error": str(e)}), 500


@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Client connected")
    emit('connected', {'message': 'Connected to drawing system'})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Client disconnected")


if __name__ == '__main__':
    # Initialize drawing system
    if not initialize_drawing_system():
        logger.error("Failed to initialize drawing system. Exiting.")
        sys.exit(1)
    
    # Run Flask app
    logger.info("Starting Flask web server on http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
