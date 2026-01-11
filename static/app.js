/**
 * Text-driven drawing application
 * Handles text input and canvas drawing
 * Voice mode disabled - using text input only
 */

// Global state
let socket;
let isProcessing = false;
let canvas, ctx;
let currentStrokes = [];
let systemInitialized = false;

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

/**
 * Initialize the application
 */
function initializeApp() {
    // Initialize canvas
    canvas = document.getElementById('drawingCanvas');
    ctx = canvas.getContext('2d');
    setupCanvas();
    
    // Initialize WebSocket
    initializeSocket();
    
    // Setup text input
    setupTextInput();
    
    // Check system status
    checkSystemStatus();
    
    // Update status
    updateStatus('Ready - Enter a drawing instruction', 'ready');
}

/**
 * Setup text input handler
 */
function setupTextInput() {
    const input = document.getElementById('instructionInput');
    const submitButton = document.getElementById('submitButton');
    
    // Submit on button click
    submitButton.addEventListener('click', () => {
        const instruction = input.value.trim();
        if (instruction) {
            processInstruction(instruction);
            input.value = ''; // Clear input
        }
    });
    
    // Submit on Enter key
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const instruction = input.value.trim();
            if (instruction) {
                processInstruction(instruction);
                input.value = ''; // Clear input
            }
        }
    });
    
    // Focus input on load
    input.focus();
}

/**
 * Setup canvas for drawing
 */
function setupCanvas() {
    // Set canvas size
    const container = canvas.parentElement;
    const size = Math.min(800, container.clientWidth - 40);
    canvas.width = size;
    canvas.height = size;
    
    // Setup drawing context
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    // Draw grid
    drawGrid();
}

/**
 * Draw grid on canvas
 */
function drawGrid() {
    ctx.strokeStyle = '#e2e8f0';
    ctx.lineWidth = 1;
    const step = 40;
    
    // Vertical lines
    for (let x = 0; x <= canvas.width; x += step) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
        ctx.stroke();
    }
    
    // Horizontal lines
    for (let y = 0; y <= canvas.height; y += step) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
    }
}

/**
 * Initialize WebSocket connection
 */
function initializeSocket() {
    socket = io();
    
    socket.on('connect', () => {
        console.log('Connected to server');
        updateStatus('Connected', 'ready');
    });
    
    socket.on('connected', (data) => {
        console.log('Server confirmed connection:', data);
    });
    
    socket.on('drawing_update', (data) => {
        handleDrawingUpdate(data);
    });
    
    socket.on('drawing_reset', () => {
        clearCanvas();
        currentStrokes = [];
    });
}

/**
 * Process a text instruction
 */
async function processInstruction(instruction) {
    if (isProcessing) {
        return;
    }
    
    if (!instruction || !instruction.trim()) {
        return;
    }
    
    isProcessing = true;
    updateStatus('Processing...', 'processing');
    
    console.log('Processing instruction:', instruction);
    
    // Send instruction to server
    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ instruction: instruction.trim() })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Display assistant's response
            displayAssistantOutput(data.message);
            
            // Update drawing - always redraw all strokes from memory
            // The server sends all strokes, so we redraw everything
            if (data.strokes && Array.isArray(data.strokes)) {
                console.log('Received strokes from server:', data.strokes);
                // Clear and redraw all strokes
                clearCanvas();
                drawStrokes(data.strokes);
                updateStrokeCount(data.strokes.length);
            } else {
                // If no strokes in response, fetch current state
                checkSystemStatus();
            }
            
            updateStatus('Ready - Enter another instruction', 'ready');
        } else {
            const errorMsg = data.error || 'An error occurred';
            displayAssistantOutput("Sorry, I encountered an error: " + errorMsg);
            console.error('Error:', errorMsg);
            updateStatus('Error occurred', 'error');
        }
    } catch (error) {
        console.error('Error processing instruction:', error);
        displayAssistantOutput("Sorry, I couldn't process that. Please try again.");
        updateStatus('Error occurred', 'error');
    } finally {
        isProcessing = false;
        // Re-focus input for next instruction
        document.getElementById('instructionInput').focus();
    }
}

/**
 * Handle drawing updates from server
 */
function handleDrawingUpdate(data) {
    console.log('Drawing update received:', data);
    
    if (data.strokes && Array.isArray(data.strokes)) {
        console.log('Updating canvas with', data.strokes.length, 'strokes');
        // Clear and redraw all strokes
        clearCanvas();
        drawStrokes(data.strokes);
        updateStrokeCount(data.strokes.length);
    }
    
    if (data.message) {
        displayAssistantOutput(data.message);
    }
}

/**
 * Draw strokes on canvas
 */
function drawStrokes(strokes) {
    console.log('Drawing strokes:', strokes);
    
    // Clear canvas first to redraw everything from memory
    clearCanvas();
    
    // Draw all strokes from memory (complete state)
    strokes.forEach((stroke, index) => {
        if (stroke.points && stroke.points.length > 0) {
            console.log(`Drawing stroke ${index} (ID: ${stroke.id}) with ${stroke.points.length} points`);
            drawStroke(stroke.points);
        }
    });
    
    currentStrokes = strokes;
}

/**
 * Draw a single stroke
 */
function drawStroke(points) {
    if (!points || points.length < 2) {
        console.warn('Invalid stroke points:', points);
        return;
    }
    
    console.log('Drawing stroke with points:', points);
    
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    // Map normalized coordinates [0,1] to canvas coordinates
    const firstPoint = points[0];
    let x = firstPoint[0] * canvas.width;
    let y = (1 - firstPoint[1]) * canvas.height; // Flip Y axis (normalized: 0=bottom, canvas: 0=top)
    
    ctx.moveTo(x, y);
    console.log(`Move to: (${x}, ${y})`);
    
    for (let i = 1; i < points.length; i++) {
        const point = points[i];
        x = point[0] * canvas.width;
        y = (1 - point[1]) * canvas.height; // Flip Y axis
        ctx.lineTo(x, y);
        console.log(`Line to: (${x}, ${y})`);
    }
    
    ctx.stroke();
    console.log('Stroke drawn');
}

/**
 * Clear the canvas
 */
function clearCanvas() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawGrid();
}

/**
 * Update status display
 */
function updateStatus(text, state) {
    const statusText = document.getElementById('statusText');
    const statusIndicator = document.getElementById('statusIndicator');
    
    if (statusText) {
        statusText.textContent = text;
    }
    
    if (statusIndicator) {
        statusIndicator.className = 'status-indicator ' + (state || 'ready');
    }
}

/**
 * Display user input
 */
function displayUserInput(text) {
    const userInputEl = document.getElementById('userInput');
    if (userInputEl) {
        userInputEl.textContent = text;
    }
}

/**
 * Display assistant output
 */
function displayAssistantOutput(text) {
    const assistantOutput = document.getElementById('assistantOutput');
    if (assistantOutput) {
        assistantOutput.textContent = text;
    }
}

/**
 * Update stroke count
 */
function updateStrokeCount(count) {
    const strokeCount = document.getElementById('strokeCount');
    if (strokeCount) {
        strokeCount.textContent = count;
    }
}

/**
 * Check system status and load existing strokes
 */
async function checkSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        if (data.status === 'ready') {
            systemInitialized = true;
            const systemModeEl = document.getElementById('systemMode');
            if (systemModeEl) {
                systemModeEl.textContent = data.simulation_mode ? 'Simulation' : 'Hardware';
            }
            updateStrokeCount(data.strokes_count || 0);
            
            // If there are existing strokes, draw them
            if (data.strokes && Array.isArray(data.strokes) && data.strokes.length > 0) {
                console.log('Loading existing strokes:', data.strokes.length);
                clearCanvas();
                drawStrokes(data.strokes);
            }
        }
    } catch (error) {
        console.error('Error checking status:', error);
    }
}
