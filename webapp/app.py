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
from config import LLM_PROVIDER, LLM_MODEL, SIMULATION_MODE, PREVIEW_MODE
import config
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
            "label": s.label,
            "state": s.state
        }
        for s in drawing_system.memory.strokes_history
    ]
    
    preview_strokes = drawing_system.memory.get_preview_strokes()
    
    return jsonify({
        "status": "ready",
        "strokes_count": len(drawing_system.memory.strokes_history),
        "preview_count": len(preview_strokes),
        "strokes": strokes,
        "simulation_mode": SIMULATION_MODE,
        "preview_mode": PREVIEW_MODE
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
                "label": s.label,
                "state": s.state
            }
            for s in drawing_system.memory.strokes_history
        ]
        
        preview_strokes = drawing_system.memory.get_preview_strokes()
        
        logger.info(f"Returning {len(strokes)} strokes to frontend ({len(preview_strokes)} in preview), message: {response[:100] if response else 'None'}...")
        
        # Emit update via WebSocket immediately (non-blocking)
        socketio.emit('drawing_update', {
            'strokes': strokes,
            'preview_count': len(preview_strokes),
            'state': state_summary,
            'message': response
        })
        
        # Return response immediately
        return jsonify({
            "success": True,
            "message": response,
            "strokes": strokes,
            "preview_count": len(preview_strokes),
            "preview_mode": PREVIEW_MODE,
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


@app.route('/api/preview/confirm', methods=['POST'])
def confirm_preview():
    """Confirm preview strokes and send to hardware."""
    if drawing_system is None:
        return jsonify({"error": "System not initialized"}), 503
    
    try:
        preview_strokes = drawing_system.memory.get_preview_strokes()
        
        if not preview_strokes:
            return jsonify({"success": False, "message": "No preview strokes to confirm"}), 400
        
        logger.info(f"Confirming {len(preview_strokes)} preview strokes")
        
        # Execute preview strokes on hardware
        stroke_points = [s.points for s in preview_strokes]
        drawing_system._execute_strokes_chunked(stroke_points)
        
        # Mark as confirmed in memory
        count = drawing_system.memory.confirm_preview_strokes()
        
        # Get updated strokes
        strokes = [
            {
                "id": s.id,
                "points": s.points,
                "label": s.label,
                "state": s.state
            }
            for s in drawing_system.memory.strokes_history
        ]
        
        # Emit update
        socketio.emit('preview_confirmed', {
            'strokes': strokes,
            'count': count
        })
        
        return jsonify({
            "success": True,
            "message": f"Confirmed {count} strokes and sent to hardware",
            "strokes": strokes
        })
        
    except Exception as e:
        logger.error(f"Error confirming preview: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/preview/reject', methods=['POST'])
def reject_preview():
    """Reject and remove preview strokes."""
    if drawing_system is None:
        return jsonify({"error": "System not initialized"}), 503
    
    try:
        count = drawing_system.memory.reject_preview_strokes()
        
        if count == 0:
            return jsonify({"success": False, "message": "No preview strokes to reject"}), 400
        
        logger.info(f"Rejected and removed {count} preview strokes")
        
        # Get updated strokes
        strokes = [
            {
                "id": s.id,
                "points": s.points,
                "label": s.label,
                "state": s.state
            }
            for s in drawing_system.memory.strokes_history
        ]
        
        # Emit update
        socketio.emit('preview_rejected', {
            'strokes': strokes,
            'count': count
        })
        
        return jsonify({
            "success": True,
            "message": f"Rejected {count} strokes",
            "strokes": strokes
        })
        
    except Exception as e:
        logger.error(f"Error rejecting preview: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/preview/toggle', methods=['POST'])
def toggle_preview_mode():
    """Toggle preview mode on/off."""
    try:
        # Toggle the config value
        config.PREVIEW_MODE = not config.PREVIEW_MODE
        
        mode_name = "Preview Mode" if config.PREVIEW_MODE else "Feeling Lucky Mode"
        logger.info(f"Switched to {mode_name}")
        
        return jsonify({
            "success": True,
            "preview_mode": config.PREVIEW_MODE,
            "message": f"Switched to {mode_name}"
        })
        
    except Exception as e:
        logger.error(f"Error toggling preview mode: {e}")
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
