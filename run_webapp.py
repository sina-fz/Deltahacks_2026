"""
Run the web application.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webapp.app import app, socketio, initialize_drawing_system

if __name__ == '__main__':
    # Initialize drawing system
    if not initialize_drawing_system():
        print("ERROR: Failed to initialize drawing system. Exiting.")
        sys.exit(1)
    
    # Run Flask app
    print("=" * 70)
    print("Voice Drawing Assistant - Web Application")
    print("=" * 70)
    print("Starting server on http://localhost:5000")
    print("Open this URL in Chrome or Edge for best voice recognition support")
    print("=" * 70)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
