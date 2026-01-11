/**
 * Voice-driven drawing application with wake word detection
 * Uses Web Speech API for always-listening mode
 * 
 * Voice Commands:
 * - "Hey Vincent" → Activates listening mode
 * - "Hey Vincent, toggle preview mode" → Switches between Preview and Feeling Lucky modes
 * - "Thanks" → Processes command and Vincent responds before stopping
 */

// Global state
let socket;
let isProcessing = false;
let canvas, ctx;
let currentStrokes = [];
let systemInitialized = false;
let previewMode = true; // Default to preview mode
let hasPreviewStrokes = false;

// Voice state - Web Speech API
let recognition = null;
let isListening = false;
let isActiveListening = false; // True when wake word detected, waiting for command
let wakeWord = "hey vincent";
let stopWord = "thanks";
let speechSynthesis = window.speechSynthesis;
let accumulatedCommand = ''; // Accumulate command text
let commandTimeout = null; // Timeout to process command after pause

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
    
    // Setup voice input (always listening with wake word)
    setupVoiceRecognition();
    
    // Check system status
    checkSystemStatus();
    
    // Update status
    updateStatus('Listening for "Hey Vincent"...', 'ready');
}

/**
 * Setup Web Speech API for always-listening with wake word detection
 */
function setupVoiceRecognition() {
    // Check browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        displayAssistantOutput('Voice recognition not supported in this browser. Please use Chrome or Edge.');
        updateStatus('Voice not supported', 'error');
        return;
    }
    
    // Initialize recognition with improved settings
    recognition = new SpeechRecognition();
    recognition.continuous = true; // Keep listening
    recognition.interimResults = true; // Get interim results for wake word detection
    recognition.lang = 'en-US';
    recognition.maxAlternatives = 1; // Only get the best match
    
    recognition.onstart = () => {
        console.log('Voice recognition started');
        isListening = true;
        updateStatus('Listening for "Hey Vincent"...', 'ready');
    };
    
    recognition.onresult = (event) => {
        // Get the most recent result
        let interimTranscript = '';
        let finalTranscript = '';
        
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript.trim();
            if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
            } else {
                interimTranscript += transcript + ' ';
            }
        }
        
        const fullTranscript = (finalTranscript + interimTranscript).trim();
        const fullTranscriptLower = fullTranscript.toLowerCase();
        console.log('Transcript:', fullTranscript, '| Active:', isActiveListening, '| Final:', finalTranscript);
        
        // Check for wake word (only when not actively listening)
        if (!isActiveListening) {
            // Check both interim and final transcripts for wake word
            if (fullTranscriptLower.includes(wakeWord) || fullTranscriptLower.includes('hey vincent') || 
                (fullTranscriptLower.includes('hey') && fullTranscriptLower.includes('vincent'))) {
                console.log('Wake word detected!');
                isActiveListening = true;
                accumulatedCommand = ''; // Clear any previous command
                // Clear any pending command timeout
                if (commandTimeout) {
                    clearTimeout(commandTimeout);
                    commandTimeout = null;
                }
                // Clear any old messages
                displayAssistantOutput('');
                // Stay SILENT - just activate listening mode
                updateStatus('Listening...', 'listening');
                return; // Don't process the wake word as a command
            }
        }
        
        // Check for stop word (only when actively listening)
        if (isActiveListening) {
            // Check for stop word first - Process command and respond before stopping
            if (fullTranscriptLower.includes(stopWord) || fullTranscriptLower.includes('thank you')) {
                console.log('=== STOP WORD DETECTED ===');
                console.log('Full transcript:', fullTranscript);
                console.log('Current accumulatedCommand:', accumulatedCommand);
                
                // Extract command from current transcript if accumulated is empty
                let commandToProcess = accumulatedCommand ? accumulatedCommand.trim() : '';
                
                // If accumulated is empty, try to extract from current transcript
                if (!commandToProcess || commandToProcess.length === 0) {
                    // Remove wake word and stop word from transcript
                    let extractedCommand = fullTranscript;
                    if (extractedCommand.toLowerCase().includes(wakeWord)) {
                        const wakeWordRegex = new RegExp(wakeWord, 'gi');
                        extractedCommand = extractedCommand.replace(wakeWordRegex, '').trim();
                    }
                    if (extractedCommand.toLowerCase().includes(stopWord) || extractedCommand.toLowerCase().includes('thank you')) {
                        const stopWordRegex = new RegExp(stopWord + '|thank you', 'gi');
                        extractedCommand = extractedCommand.replace(stopWordRegex, '').trim();
                    }
                    if (extractedCommand && extractedCommand.length > 0) {
                        commandToProcess = extractedCommand;
                        console.log('Extracted command from transcript:', commandToProcess);
                    }
                }
                
                // Process the command (if any) and Vincent will respond
                if (commandToProcess && commandToProcess.length > 3) {
                    const commandText = commandToProcess.toLowerCase();
                    // Only process if it's not the wake word or stop word and has meaningful content
                    if (!commandText.includes(wakeWord) && !commandText.includes(stopWord) && 
                        !commandText.includes('thank you')) {
                        console.log('=== PROCESSING COMMAND ===');
                        console.log('Command to process:', commandToProcess);
                        accumulatedCommand = ''; // Clear after processing
                        isActiveListening = false; // Reset listening state BEFORE processing
                        updateStatus('Processing...', 'processing');
                        processInstruction(commandToProcess);
                    } else {
                        // No valid command, just go back to sleep
                        console.log('No valid command to process. Command text:', commandText);
                        isActiveListening = false;
                        updateStatus('Listening for "Hey Vincent"...', 'ready');
                    }
                } else {
                    // No command accumulated, just go back to sleep
                    console.log('No command to process - command is empty or too short');
                    console.log('Command length:', commandToProcess ? commandToProcess.length : 0);
                    isActiveListening = false;
                    updateStatus('Listening for "Hey Vincent"...', 'ready');
                }
                
                // Clear any pending command timeout
                if (commandTimeout) {
                    clearTimeout(commandTimeout);
                    commandTimeout = null;
                }
                return;
            }
            
            // Check for toggle preview/feeling lucky command
            if (finalTranscript) {
                const hasToggle = fullTranscriptLower.includes('toggle');
                const hasPreview = fullTranscriptLower.includes('preview');
                const hasFeeling = fullTranscriptLower.includes('feeling');
                const hasLucky = fullTranscriptLower.includes('lucky');
                
                if (hasToggle && (hasPreview || (hasFeeling && hasLucky))) {
                    console.log('=== TOGGLE MODE COMMAND DETECTED ===');
                    isActiveListening = false;
                    accumulatedCommand = '';
                    
                    // Clear any pending command timeout
                    if (commandTimeout) {
                        clearTimeout(commandTimeout);
                        commandTimeout = null;
                    }
                    
                    updateStatus('Toggling mode...', 'processing');
                    togglePreviewMode(true); // Speak the mode change
                    return;
                }
            }
            
            // Check for preview confirmation/rejection commands if we have preview strokes
            if (hasPreviewStrokes && finalTranscript) {
                const transcriptLower = fullTranscriptLower;
                // Check for confirmation words
                const confirmWords = ['good', 'yes', 'keep', 'confirm', 'ok', 'okay', 'proceed', 'go ahead', 'looks good', 'that works'];
                const rejectWords = ['reject', 'no', 'remove', 'delete', 'cancel', 'try again', 'different', 'change'];
                
                let isConfirm = confirmWords.some(word => transcriptLower.includes(word));
                let isReject = rejectWords.some(word => transcriptLower.includes(word));
                
                if (isConfirm && !isReject) {
                    console.log('Preview confirmation detected via voice');
                    waitingForPreviewResponse = false;
                    isActiveListening = false;
                    accumulatedCommand = '';
                    updateStatus('Confirming preview...', 'processing');
                    confirmPreview();
                    return;
                } else if (isReject) {
                    console.log('Preview rejection detected via voice');
                    waitingForPreviewResponse = false;
                    isActiveListening = false;
                    accumulatedCommand = '';
                    updateStatus('Rejecting preview...', 'processing');
                    rejectPreview();
                    return;
                }
            }
            
            // Check for preview confirmation/rejection commands if we have preview strokes
            if (hasPreviewStrokes && finalTranscript) {
                const transcriptLower = fullTranscriptLower;
                // Check for confirmation words
                const confirmWords = ['good', 'yes', 'keep', 'confirm', 'ok', 'okay', 'proceed', 'go ahead', 'looks good', 'that works'];
                const rejectWords = ['reject', 'no', 'remove', 'delete', 'cancel', 'try again', 'different', 'change'];
                
                let isConfirm = confirmWords.some(word => transcriptLower.includes(word));
                let isReject = rejectWords.some(word => transcriptLower.includes(word));
                
                if (isConfirm && !isReject) {
                    console.log('Preview confirmation detected via voice');
                    waitingForPreviewResponse = false;
                    isActiveListening = false;
                    accumulatedCommand = '';
                    updateStatus('Confirming preview...', 'processing');
                    confirmPreview();
                    return;
                } else if (isReject) {
                    console.log('Preview rejection detected via voice');
                    waitingForPreviewResponse = false;
                    isActiveListening = false;
                    accumulatedCommand = '';
                    updateStatus('Rejecting preview...', 'processing');
                    rejectPreview();
                    return;
                }
            }
            
            // Accumulate command text continuously (both interim and final)
            // Remove wake word if it appears in the transcript
            let cleanTranscript = fullTranscript;
            if (cleanTranscript.toLowerCase().includes(wakeWord)) {
                // Remove wake word from transcript
                const wakeWordRegex = new RegExp(wakeWord, 'gi');
                cleanTranscript = cleanTranscript.replace(wakeWordRegex, '').trim();
            }
            
            // Remove stop word from accumulation (we'll process on stop word detection)
            if (cleanTranscript.toLowerCase().includes(stopWord) || cleanTranscript.toLowerCase().includes('thank you')) {
                const stopWordRegex = new RegExp(stopWord + '|thank you', 'gi');
                cleanTranscript = cleanTranscript.replace(stopWordRegex, '').trim();
            }
            
            // Only accumulate if we have meaningful content (not just wake/stop words)
            if (cleanTranscript && cleanTranscript.length > 0) {
                // Accumulate continuously - append new text to existing
                if (finalTranscript) {
                    // When we get final results, append to accumulated command
                    // Remove the stop word from the final transcript before accumulating
                    let transcriptToAdd = cleanTranscript;
                    if (transcriptToAdd.toLowerCase().includes(stopWord) || transcriptToAdd.toLowerCase().includes('thank you')) {
                        const stopWordRegex = new RegExp(stopWord + '|thank you', 'gi');
                        transcriptToAdd = transcriptToAdd.replace(stopWordRegex, '').trim();
                    }
                    
                    if (transcriptToAdd && transcriptToAdd.length > 0) {
                        if (accumulatedCommand) {
                            // Append with space if not empty
                            accumulatedCommand += ' ' + transcriptToAdd;
                        } else {
                            accumulatedCommand = transcriptToAdd;
                        }
                        console.log('Accumulated command (final):', accumulatedCommand);
                    }
                } else if (interimTranscript) {
                    // For interim results, just log what we're hearing
                    console.log('Interim command:', cleanTranscript);
                }
                updateStatus('Listening...', 'listening');
            }
        }
    };
    
    recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'no-speech') {
            // This is normal, just continue listening
            return;
        }
        displayAssistantOutput('Voice recognition error: ' + event.error);
        updateStatus('Voice error', 'error');
    };
    
    recognition.onend = () => {
        console.log('Voice recognition ended, restarting...');
        isListening = false;
        
        // DON'T process commands on recognition end - only process on "Thanks"
        // Just keep listening and accumulating
        
        // Restart recognition to keep listening
        if (recognition) {
            try {
                recognition.start();
            } catch (e) {
                // Ignore errors when restarting
                console.log('Restarting recognition...');
                setTimeout(() => {
                    if (recognition) {
                        recognition.start();
                    }
                }, 100);
            }
        }
    };
    
    // Load voices when available (some browsers need this)
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = () => {
            console.log('Voices loaded:', speechSynthesis.getVoices().length);
        };
    }
    
    // Start listening with a small delay to ensure everything is ready
    setTimeout(() => {
        try {
            recognition.start();
            console.log('Voice recognition initialized and started');
        } catch (e) {
            console.error('Error starting recognition:', e);
            displayAssistantOutput('Could not start voice recognition. Please allow microphone access.');
        }
    }, 500);
}

/**
 * Setup canvas for drawing
 */
function setupCanvas() {
    // Set canvas size to fill available space in right column
    const container = canvas.parentElement.parentElement; // Get the glass-effect container
    const availableWidth = container.clientWidth - 48; // Account for padding (p-6 = 24px * 2)
    const availableHeight = container.clientHeight - 48; // Account for padding
    
    // Use the smaller dimension to maintain square aspect ratio, but maximize space
    const size = Math.min(availableWidth, availableHeight, 800);
    canvas.width = size;
    canvas.height = size;
    
    // Setup drawing context (black ink for sketched look)
    ctx.strokeStyle = '#1a1a1a'; // Black ink
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    
    // Draw grid
    drawGrid();
    
    // Handle window resize
    window.addEventListener('resize', () => {
        const newSize = Math.min(container.clientWidth - 48, container.clientHeight - 48, 800);
        if (newSize !== size) {
            canvas.width = newSize;
            canvas.height = newSize;
            drawGrid();
            // Redraw all strokes
            if (currentStrokes && currentStrokes.length > 0) {
                drawStrokes(currentStrokes);
            }
        }
    });
}

/**
 * Draw grid on canvas (sketched style - black and white)
 */
function drawGrid() {
    ctx.strokeStyle = '#cccccc';
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.4;
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
    
    ctx.globalAlpha = 1.0;
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
    
    console.log('=== PROCESSING INSTRUCTION ===');
    console.log('Processing instruction:', instruction);
    console.log('Instruction length:', instruction.trim().length);
    console.log('Instruction (full):', JSON.stringify(instruction));
    console.log('Instruction trimmed:', instruction.trim());
    
    // Validate instruction is not empty
    const trimmedInstruction = instruction.trim();
    if (!trimmedInstruction || trimmedInstruction.length === 0) {
        console.error('ERROR: Empty instruction received!');
        displayAssistantOutput('Error: No instruction received. Please try again.');
        isProcessing = false;
        return;
    }
    
    // Send instruction to server
    try {
        const requestBody = { instruction: trimmedInstruction };
        console.log('Sending request body:', JSON.stringify(requestBody));
        
        const response = await fetch('/api/process', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            // Display assistant's response (ALWAYS show the message)
            const message = data.message || "Processing...";
            console.log('Assistant message:', message);
            displayAssistantOutput(message);
            
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
            
            // Don't speak here - let handleDrawingUpdate handle it to avoid duplicates
            
            // Update status based on message content
            if (message.toLowerCase().includes('clarify') || message.toLowerCase().includes('?')) {
                updateStatus('Waiting for your answer...', 'processing');
            } else {
                updateStatus('Ready - Enter another instruction', 'ready');
            }
        } else {
            const errorMsg = data.error || 'An error occurred';
            displayAssistantOutput("Sorry, I encountered an error: " + errorMsg);
            console.error('Error:', errorMsg);
            updateStatus('Error occurred', 'error');
            
            // Speak error using browser TTS
            setTimeout(() => {
                speakText('Sorry, I encountered an error: ' + errorMsg);
            }, 300);
        }
    } catch (error) {
        console.error('Error processing instruction:', error);
        displayAssistantOutput("Sorry, I couldn't process that. Please try again.");
        updateStatus('Error occurred', 'error');
        
        // Speak error using browser TTS
        setTimeout(() => {
            speakText('Sorry, I could not process that. Please try again.');
        }, 300);
    } finally {
        isProcessing = false;
        // Return to listening state
        if (!isActiveListening) {
            updateStatus('Listening for "Hey Vincent"...', 'ready');
        }
    }
}

/**
 * Handle drawing updates from server
 */
function handleDrawingUpdate(data) {
    console.log('Drawing update received:', data);
    
    // Don't process updates while actively listening (waiting for "Thanks")
    if (isActiveListening) {
        console.log('Ignoring drawing update while actively listening');
        return;
    }
    
    if (data.strokes && Array.isArray(data.strokes)) {
        console.log('Updating canvas with', data.strokes.length, 'strokes');
        // Clear and redraw all strokes
        clearCanvas();
        drawStrokes(data.strokes);
        updateStrokeCount(data.strokes.length);
    }
    
    if (data.message) {
        displayAssistantOutput(data.message);
        // Only speak if we're not actively listening and not processing
        if (!isActiveListening && !isProcessing) {
            setTimeout(() => {
                speakText(data.message);
            }, 500);
        }
    }
}

/**
 * Draw strokes on canvas
 */
function drawStrokes(strokes) {
    console.log('Drawing strokes:', strokes);
    
    // Clear canvas first to redraw everything from memory
    clearCanvas();
    
    // Count preview strokes
    let previewCount = 0;
    
    // Draw all strokes from memory (complete state)
    strokes.forEach((stroke, index) => {
        if (stroke.points && stroke.points.length > 0) {
            // Choose color based on stroke state (black and white sketched theme)
            const color = stroke.state === 'preview' ? '#cc0000' : '#1a1a1a'; // red for preview, black for confirmed
            console.log(`Drawing stroke ${index} (ID: ${stroke.id}, state: ${stroke.state}) with ${stroke.points.length} points in color ${color}`);
            drawStroke(stroke.points, color);
            
            if (stroke.state === 'preview') {
                previewCount++;
            }
        }
    });
    
    // Update preview controls visibility
    hasPreviewStrokes = previewCount > 0;
    waitingForPreviewResponse = previewCount > 0; // Set flag when preview strokes exist
    updatePreviewControls();
    
    currentStrokes = strokes;
}

/**
 * Draw a single stroke (black and white sketched style)
 */
function drawStroke(points, color = '#1a1a1a') {
    if (!points || points.length < 2) {
        console.warn('Invalid stroke points:', points);
        return;
    }
    
    console.log('Drawing stroke with points:', points, 'color:', color);
    
    ctx.strokeStyle = color;
    ctx.lineWidth = 2.5;
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
        // Update indicator color based on state
        statusIndicator.className = 'w-3 h-3 rounded-full';
        if (state === 'listening' || state === 'processing') {
            statusIndicator.style.background = '#10b981'; // Green when active
            statusIndicator.style.animation = 'pulse 1s infinite';
        } else if (state === 'error') {
            statusIndicator.style.background = '#ef4444'; // Red on error
        } else {
            statusIndicator.style.background = '#6b7280'; // Gray when waiting
        }
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
            
            // Update preview mode
            previewMode = data.preview_mode || false;
            updatePreviewModeDisplay();
            
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

/**
 * Update preview controls visibility
 */
function updatePreviewControls() {
    const previewControls = document.getElementById('previewControls');
    if (previewControls) {
        if (hasPreviewStrokes) {
            previewControls.classList.remove('hidden');
            previewControls.classList.add('block', 'animate-unroll');
            // Remove animation class after animation completes to allow re-triggering
            setTimeout(() => {
                previewControls.classList.remove('animate-unroll');
            }, 500);
            
            // Disable buttons (keep visible but non-clickable) - use voice commands instead
            const confirmBtn = previewControls.querySelector('button[onclick="confirmPreview()"]');
            const rejectBtn = previewControls.querySelector('button[onclick="rejectPreview()"]');
            if (confirmBtn) {
                confirmBtn.disabled = true;
                confirmBtn.style.opacity = '0.6';
                confirmBtn.style.cursor = 'not-allowed';
                confirmBtn.title = 'Use voice: Say "Good" or "Yes" to confirm';
            }
            if (rejectBtn) {
                rejectBtn.disabled = true;
                rejectBtn.style.opacity = '0.6';
                rejectBtn.style.cursor = 'not-allowed';
                rejectBtn.title = 'Use voice: Say "Reject" or "No" to reject';
            }
        } else {
            previewControls.classList.remove('block', 'animate-unroll');
            previewControls.classList.add('hidden');
        }
    }
}

/**
 * Update preview mode display
 */
function updatePreviewModeDisplay() {
    const toggleBtn = document.getElementById('previewModeToggle');
    if (toggleBtn) {
        toggleBtn.textContent = previewMode ? 'Preview Mode' : 'Feeling Lucky';
        
        // Remove old classes
        toggleBtn.className = '';
        
        // Add base sketch button classes
        toggleBtn.className = 'sketch-button px-6 py-3 text-base rounded-lg transition-all duration-300';
        toggleBtn.style.position = 'relative';
        toggleBtn.style.zIndex = '1';
        
        // Both modes use same black and white style (sketched look)
        // The button already has the sketch-button styling
    }
}

/**
 * Confirm preview strokes
 */
async function confirmPreview() {
    try {
        updateStatus('Confirming and sending to hardware...', 'processing');
        
        const response = await fetch('/api/preview/confirm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            displayAssistantOutput(data.message);
            
            // Redraw with confirmed strokes (black)
            if (data.strokes) {
                clearCanvas();
                drawStrokes(data.strokes);
            }
            
            waitingForPreviewResponse = false;
            updateStatus('Ready - Enter another instruction', 'ready');
            
            // Speak confirmation
            setTimeout(() => {
                speakText(data.message);
            }, 300);
        } else {
            displayAssistantOutput('Error: ' + (data.message || data.error));
            updateStatus('Error occurred', 'error');
        }
    } catch (error) {
        console.error('Error confirming preview:', error);
        displayAssistantOutput('Failed to confirm preview');
        updateStatus('Error occurred', 'error');
    }
}

/**
 * Reject preview strokes
 */
async function rejectPreview() {
    try {
        updateStatus('Rejecting preview...', 'processing');
        
        const response = await fetch('/api/preview/reject', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            displayAssistantOutput(data.message + '. What would you like to draw instead?');
            
            // Redraw without preview strokes
            if (data.strokes) {
                clearCanvas();
                drawStrokes(data.strokes);
            }
            
            waitingForPreviewResponse = false;
            updateStatus('Ready - Enter another instruction', 'ready');
            
            // Speak rejection message
            setTimeout(() => {
                speakText(data.message + '. What would you like to draw instead?');
            }, 300);
        } else {
            displayAssistantOutput('Error: ' + (data.message || data.error));
            updateStatus('Error occurred', 'error');
        }
    } catch (error) {
        console.error('Error rejecting preview:', error);
        displayAssistantOutput('Failed to reject preview');
        updateStatus('Error occurred', 'error');
    }
}

/**
 * Toggle preview mode
 */
async function togglePreviewMode(shouldSpeak = true) {
    try {
        const response = await fetch('/api/preview/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            previewMode = data.preview_mode;
            updatePreviewModeDisplay();
            displayAssistantOutput(data.message);
            
            // Speak the mode change if requested
            if (shouldSpeak) {
                setTimeout(() => {
                    speakText(data.message);
                }, 300);
            }
            
            // Return to listening state
            updateStatus('Listening for "Hey Vincent"...', 'ready');
        } else {
            console.error('Error toggling preview mode:', data.error);
        }
    } catch (error) {
        console.error('Error toggling preview mode:', error);
    }
}

/**
 * Speak text using browser's built-in Text-to-Speech with improved quality
 */
function speakText(text) {
    if (!text || !text.trim()) {
        return;
    }
    
    // Cancel any ongoing speech
    speechSynthesis.cancel();
    
    // Wait a moment for cancellation to complete
    setTimeout(() => {
        // Get available voices and select the best male voice
        const voices = speechSynthesis.getVoices();
        let selectedVoice = null;
        
        // Prefer natural-sounding MALE voices
        const preferredMaleVoices = [
            'Microsoft David',      // Windows male voice
            'Google UK English Male',
            'Alex',                 // macOS male voice
            'Daniel',               // macOS male voice
            'Fred',                 // macOS male voice
            'Microsoft Mark',       // Windows male voice
            'Google US English Male'
        ];
        
        // Try to find a preferred male voice
        for (const preferred of preferredMaleVoices) {
            selectedVoice = voices.find(v => v.name.includes(preferred));
            if (selectedVoice) {
                console.log('Found preferred male voice:', selectedVoice.name);
                break;
            }
        }
        
        // If no preferred voice found, try to find any male English voice
        if (!selectedVoice) {
            selectedVoice = voices.find(v => 
                v.lang.startsWith('en') && 
                (v.name.toLowerCase().includes('male') || 
                 v.name.toLowerCase().includes('david') ||
                 v.name.toLowerCase().includes('mark') ||
                 v.name.toLowerCase().includes('alex') ||
                 v.name.toLowerCase().includes('daniel'))
            );
            if (selectedVoice) {
                console.log('Found male voice:', selectedVoice.name);
            }
        }
        
        // Last resort: any English voice
        if (!selectedVoice) {
            selectedVoice = voices.find(v => 
                v.lang.startsWith('en') && 
                !v.name.includes('Enhanced') &&
                !v.name.includes('Compact')
            );
        }
        
        // Create speech utterance with improved settings
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Use selected voice if available
        if (selectedVoice) {
            utterance.voice = selectedVoice;
            console.log('Using voice:', selectedVoice.name);
        }
        
        // Improved settings for natural speech
        utterance.rate = 0.95;  // Slightly slower for more natural sound
        utterance.pitch = 1.0;  // Normal pitch
        utterance.volume = 1.0;  // Full volume
        utterance.lang = 'en-US'; // US English
        
        utterance.onstart = () => {
            console.log('Speech started');
        };
        
        utterance.onend = () => {
            console.log('Speech finished');
        };
        
        utterance.onerror = (event) => {
            console.error('Speech error:', event.error);
        };
        
        // Speak
        speechSynthesis.speak(utterance);
    }, 100);
}

