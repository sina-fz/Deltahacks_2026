# Preview Mode Feature Documentation

## Overview

The **Preview Mode** feature allows users to review AI-generated drawings before they're sent to the physical hardware. This provides a safety net and allows for adjustments without wasting physical ink/paper.

## Features

### 1. **Preview Mode (Default ON)**
- New strokes appear in **RED** on the canvas
- User can review before committing to hardware
- Confirmation buttons appear when preview strokes exist
- User can either:
  - ✅ **Confirm** - Send to hardware (strokes turn black)
  - ❌ **Reject** - Remove strokes and request changes

### 2. **Feeling Lucky Mode**
- Toggle to turn preview OFF
- Strokes appear in **BLACK** immediately
- Sent directly to hardware without confirmation
- For users who trust the AI and want speed

## How It Works

### User Flow (Preview Mode ON)

```
User: "Draw a cat"
  ↓
[LLM generates strokes]
  ↓
[Strokes appear in RED on canvas]
  ↓
[Confirmation buttons appear]
  ↓
User clicks "✅ Looks Good - Draw It!"
  ↓
[Strokes turn BLACK]
[Strokes sent to hardware]
  ↓
Done!
```

**Alternative Flow:**

```
User: "Draw a cat"
  ↓
[LLM generates strokes]
  ↓
[Strokes appear in RED on canvas]
  ↓
[Confirmation buttons appear]
  ↓
User clicks "❌ Reject - Try Again"
  ↓
[RED strokes removed from canvas]
[User asked: "What would you like to draw instead?"]
  ↓
User: "Draw a dog instead"
  ↓
[New strokes generated and previewed]
```

### User Flow (Feeling Lucky Mode)

```
User: "Draw a cat"
  ↓
[LLM generates strokes]
  ↓
[Strokes appear in BLACK immediately]
[Strokes sent to hardware immediately]
  ↓
Done! (No confirmation needed)
```

## Technical Implementation

### Backend

#### 1. Configuration (`config.py`)
```python
PREVIEW_MODE = True  # Default to preview mode
```

#### 2. Stroke State (`state/memory.py`)
Each stroke has a `state` field:
- `"preview"` - Not yet confirmed, shown in red
- `"confirmed"` - Confirmed and sent to hardware, shown in black

```python
@dataclass
class Stroke:
    id: int
    points: List[Tuple[float, float]]
    label: Optional[str] = None
    state: str = "confirmed"  # "preview" or "confirmed"
```

#### 3. Memory Methods (`state/memory.py`)
```python
# Get all preview strokes
preview_strokes = memory.get_preview_strokes()

# Confirm all preview strokes (change state to "confirmed")
count = memory.confirm_preview_strokes()

# Reject and remove all preview strokes
count = memory.reject_preview_strokes()
```

#### 4. Hardware Execution (`main_loop.py`)
```python
# Determine stroke state based on preview mode
stroke_state = "preview" if PREVIEW_MODE else "confirmed"

# Execute strokes on hardware only if not in preview mode OR if confirming
if not PREVIEW_MODE or stroke_state == "confirmed":
    self._execute_strokes_chunked(validated_strokes)
else:
    logger.info("Preview mode: skipping hardware execution")

# Update memory with state
stroke_ids = self.memory.add_strokes(validated_strokes, response.labels, state=stroke_state)
```

#### 5. API Endpoints (`webapp/app.py`)

**Confirm Preview:**
```
POST /api/preview/confirm
→ Executes preview strokes on hardware
→ Changes state to "confirmed"
→ Returns updated strokes (now black)
```

**Reject Preview:**
```
POST /api/preview/reject
→ Removes preview strokes from memory
→ Returns updated strokes (without rejected ones)
```

**Toggle Preview Mode:**
```
POST /api/preview/toggle
→ Toggles PREVIEW_MODE config
→ Returns new mode state
```

### Frontend

#### 1. Stroke Display (`static/app.js`)
```javascript
function drawStrokes(strokes) {
    strokes.forEach((stroke) => {
        // Red for preview, black for confirmed
        const color = stroke.state === 'preview' ? '#ef4444' : '#1e293b';
        drawStroke(stroke.points, color);
    });
    
    // Show/hide confirmation buttons
    hasPreviewStrokes = (previewCount > 0);
    updatePreviewControls();
}
```

#### 2. Confirmation Buttons (`templates/index.html`)
```html
<div class="preview-controls" id="previewControls" style="display: none;">
    <h3>Preview (Red strokes)</h3>
    <p>Review the drawing before sending to hardware:</p>
    <div class="button-group">
        <button onclick="confirmPreview()">✅ Looks Good - Draw It!</button>
        <button onclick="rejectPreview()">❌ Reject - Try Again</button>
    </div>
</div>
```

Buttons appear **only when** preview strokes exist.

#### 3. Mode Toggle (`templates/index.html`)
```html
<button onclick="togglePreviewMode()" id="previewModeToggle">
    👁️ Preview Mode
</button>
```

Button text changes based on mode:
- **Preview Mode**: 👁️ Preview Mode (gray button)
- **Feeling Lucky**: 🍀 Feeling Lucky (green button)

#### 4. CSS Styling (`static/style.css`)
- Preview controls have red border and red-tinted background
- Confirm button is green
- Reject button is red
- Toggle button changes color based on mode

## API Response Format

All endpoints that return strokes now include the `state` field:

```json
{
  "success": true,
  "strokes": [
    {
      "id": 0,
      "points": [[0.3, 0.4], [0.7, 0.4], ...],
      "label": "body",
      "state": "preview"  // ← NEW FIELD
    },
    {
      "id": 1,
      "points": [[0.4, 0.6], [0.6, 0.6], ...],
      "label": "head",
      "state": "confirmed"
    }
  ],
  "preview_count": 1,
  "preview_mode": true
}
```

## Visual Design

### Color Scheme
- **Preview strokes**: `#ef4444` (bright red)
- **Confirmed strokes**: `#1e293b` (dark slate)
- **Confirm button**: Green gradient
- **Reject button**: Red gradient
- **Preview Mode toggle**: Gray gradient
- **Feeling Lucky toggle**: Green gradient

### Button States
- **Hover**: Slight lift effect (translateY -2px)
- **Active**: Press down effect (translateY 0)
- **Focus**: Outline for accessibility

## User Experience

### When Preview Mode is ON:
1. User enters drawing instruction
2. LLM generates strokes incrementally (body → head → ears → etc.)
3. Each component appears in RED as it's generated
4. Confirmation buttons appear after all components drawn
5. User reviews the complete drawing
6. User clicks "Looks Good" → strokes turn BLACK → sent to hardware
7. OR user clicks "Reject" → RED strokes removed → can try again

### When Preview Mode is OFF (Feeling Lucky):
1. User enters drawing instruction
2. LLM generates strokes incrementally
3. Each component appears in BLACK immediately
4. Each component is sent to hardware immediately as it's drawn
5. No confirmation needed - faster but less safe

## Benefits

### For Users:
✅ **Safety net** - Review before committing to hardware
✅ **Flexibility** - Can reject and modify without waste
✅ **Visual feedback** - Clear distinction between preview (red) and confirmed (black)
✅ **Speed option** - Can toggle to "Feeling Lucky" for faster workflow

### For Hardware:
✅ **Prevents waste** - No drawing of unwanted results
✅ **Reduces wear** - Fewer unnecessary movements
✅ **User confidence** - Users more likely to try complex drawings

### For Development:
✅ **Easy testing** - Can review AI output without hardware
✅ **Debugging** - Can see exactly what LLM generated before execution
✅ **Iterative improvement** - Users can refine prompts based on previews

## Configuration

### Environment Variable
```bash
# .env file
PREVIEW_MODE=true   # Enable preview mode (default)
PREVIEW_MODE=false  # Disable preview mode (Feeling Lucky)
```

### Runtime Toggle
Users can toggle preview mode at runtime using the UI button. This changes the `config.PREVIEW_MODE` value dynamically (doesn't require restart).

## Edge Cases Handled

1. **Multiple preview sessions**: Only one set of preview strokes at a time (new previews replace old ones if not confirmed)
2. **Confirmation with no previews**: API returns error message
3. **Rejection with no previews**: API returns error message
4. **WebSocket updates**: All clients receive updated stroke states in real-time
5. **Page refresh**: Preview strokes are lost (intentional - they weren't confirmed)

## Testing

### Test Scenarios:

**Test 1: Preview Flow**
```
1. Ensure PREVIEW_MODE=true
2. Open webapp
3. Type "draw a square"
4. Verify: Square appears in RED
5. Verify: Confirmation buttons appear
6. Click "Looks Good"
7. Verify: Square turns BLACK
8. Verify: Buttons disappear
```

**Test 2: Rejection Flow**
```
1. Ensure PREVIEW_MODE=true
2. Type "draw a circle"
3. Verify: Circle appears in RED
4. Click "Reject"
5. Verify: Circle disappears
6. Verify: Assistant says "What would you like to draw instead?"
```

**Test 3: Feeling Lucky Flow**
```
1. Click "Preview Mode" toggle (changes to "Feeling Lucky")
2. Type "draw a triangle"
3. Verify: Triangle appears in BLACK immediately
4. Verify: No confirmation buttons appear
```

**Test 4: Incremental Drawing**
```
1. Ensure PREVIEW_MODE=true
2. Type "draw a cat"
3. Verify: Body appears in RED
4. Wait for head to be added in RED
5. Wait for ears to be added in RED
6. Verify: All components in RED
7. Click "Looks Good"
8. Verify: All components turn BLACK at once
```

## Files Modified/Created

### Backend:
- ✅ `config.py` - Added `PREVIEW_MODE` flag
- ✅ `state/memory.py` - Added stroke `state` field and methods
- ✅ `main_loop.py` - Added preview mode handling
- ✅ `webapp/app.py` - Added preview API endpoints

### Frontend:
- ✅ `static/app.js` - Added color-based rendering and preview functions
- ✅ `templates/index.html` - Added preview controls and toggle button
- ✅ `static/style.css` - Added preview control styles

### Documentation:
- ✅ `PREVIEW_MODE_FEATURE.md` - This file

## Future Enhancements

Potential improvements:
1. **Preview timeout**: Auto-confirm after X seconds
2. **Edit mode**: Allow users to manually adjust preview strokes before confirming
3. **Preview history**: Save rejected previews for comparison
4. **Confidence score**: Show LLM confidence level for each preview
5. **Partial confirmation**: Confirm some components while rejecting others

---

**Status**: ✅ FULLY IMPLEMENTED AND READY TO USE

The preview mode feature is complete and production-ready. Users can now safely review AI-generated drawings before committing to physical hardware!
