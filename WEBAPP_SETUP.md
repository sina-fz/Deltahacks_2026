# Web App Setup Instructions

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Make sure your `.env` file has your OpenRouter API key**:
   ```bash
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=your_key_here
   ```

3. **Run the web app**:
   ```bash
   python run_webapp.py
   ```

4. **Open in browser**:
   - Go to: `http://localhost:5000`
   - **Important**: Use Chrome or Edge for best voice recognition support

## Features

### Voice Input
- Click the microphone button or say "start"
- Speak your drawing instructions naturally
- System recognizes your voice and processes commands

### Voice Output
- Tony (the assistant) speaks responses using natural TTS
- Shows what Tony says on screen
- Uses high-quality voices (not robotic)

### Drawing Visualization
- Real-time canvas showing your drawing
- Updates as you add new elements
- Clean, modern interface

### Accessibility
- Hands-free operation
- Large, clear buttons
- Visual feedback for all actions
- Perfect for users with limited mobility

## Voice Commands

- **"start"** or **"begin"** - Start the drawing session
- **"draw a circle"** - Draw a circle
- **"add a square"** - Add a square
- **"draw a house"** - Draw a house
- **"stop"** or **"quit"** - End the session

## Browser Compatibility

### Full Support (Recommended)
- **Chrome/Edge**: Full voice recognition + TTS
- Best experience, all features work

### Limited Support
- **Firefox**: TTS works, but no voice recognition
- **Safari**: Limited support

## Troubleshooting

### Microphone Not Working
1. Check browser permissions (allow microphone access)
2. Make sure you're using Chrome or Edge
3. Check that your microphone is connected and working

### Voice Recognition Not Starting
- Refresh the page
- Check browser console for errors
- Make sure you're on `http://localhost:5000` (not `https://`)

### Drawing Not Appearing
- Check browser console for errors
- Make sure the backend is running
- Check that your API key is set correctly

## Architecture

- **Backend**: Flask server with WebSocket support
- **Frontend**: HTML/CSS/JavaScript with Web Speech API
- **Integration**: Uses existing drawing system (no changes needed)

## Next Steps

1. Test voice input/output
2. Try drawing different shapes
3. Test the full conversation flow
4. Ready for hardware integration!
