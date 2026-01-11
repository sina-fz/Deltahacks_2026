"""
LLM wrapper with strict JSON output enforcement.
Supports OpenAI, Anthropic, and OpenRouter APIs.
"""
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from config import LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY, LLM_MODEL
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMResponse:
    """Structured response from LLM."""
    strokes: List[List[Tuple[float, float]]]
    anchors: Dict[str, Any]
    labels: Dict[str, str]
    assistant_message: str
    done: bool
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMResponse":
        """Create from dictionary."""
        # Convert strokes to list of tuples
        strokes = []
        for stroke in data.get("strokes", []):
            stroke_tuples = [(float(p[0]), float(p[1])) for p in stroke]
            strokes.append(stroke_tuples)
        
        # Handle case where plan/components are at root level (wrong format)
        anchors = data.get("anchors", {})
        if "plan" in data and "plan" not in anchors:
            # Plan is at root level - move it to anchors
            anchors = anchors.copy() if anchors else {}
            anchors["plan"] = data["plan"]
            if "components" in data:
                anchors["components"] = data["components"]
            if "current_stage" in data:
                anchors["current_stage"] = data["current_stage"]
            else:
                # Default to planning stage (0) if missing
                anchors["current_stage"] = 0
            if "total_stages" in data:
                anchors["total_stages"] = data["total_stages"]
            else:
                # Default to 1 stage if missing
                anchors["total_stages"] = 1
        
        # Generate assistant_message from plan if missing
        assistant_message = data.get("assistant_message")
        if not assistant_message or assistant_message == "Ready for next instruction.":
            # Check if we have a plan
            plan = anchors.get("plan") or data.get("plan")
            if plan:
                # Generate message from plan
                assistant_message = f"{plan} Should I proceed?"
            else:
                assistant_message = "Ready for next instruction."
        
        return cls(
            strokes=strokes,
            anchors=anchors,
            labels=data.get("labels", {}),
            assistant_message=assistant_message,
            done=data.get("done", False)
        )


class LLMWrapper:
    """Wrapper for LLM API calls with JSON enforcement."""
    
    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize LLM wrapper.
        
        Args:
            provider: "openai", "anthropic", or "openrouter"
            model: Model name
        """
        self.provider = provider or LLM_PROVIDER
        self.model = model or LLM_MODEL
        
        if self.provider == "openai":
            try:
                from openai import OpenAI
                if not OPENAI_API_KEY:
                    raise ValueError("OPENAI_API_KEY not set in environment")
                self.client = OpenAI(api_key=OPENAI_API_KEY)
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        elif self.provider == "anthropic":
            try:
                from anthropic import Anthropic
                if not ANTHROPIC_API_KEY:
                    raise ValueError("ANTHROPIC_API_KEY not set in environment")
                self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        elif self.provider == "openrouter":
            try:
                from openai import OpenAI
                if not OPENROUTER_API_KEY:
                    raise ValueError("OPENROUTER_API_KEY not set in environment")
                # OpenRouter uses OpenAI-compatible API with different base URL
                self.client = OpenAI(
                    api_key=OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1"
                )
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    def call_llm(self, prompt: str, max_retries: int = 3) -> LLMResponse:
        """
        Call LLM and parse JSON response.
        
        Args:
            prompt: The prompt to send
            max_retries: Maximum retries if JSON parsing fails
        
        Returns:
            LLMResponse object
        """
        logger.debug(f"Calling LLM ({self.provider}/{self.model})")
        logger.debug(f"Prompt length: {len(prompt)} chars")
        
        for attempt in range(max_retries):
            try:
                # Call LLM
                if self.provider == "openai":
                    response = self._call_openai(prompt)
                elif self.provider == "openrouter":
                    response = self._call_openrouter(prompt)
                else:
                    response = self._call_anthropic(prompt)
                
                # Extract JSON from response
                json_str = self._extract_json(response)
                
                # Parse JSON
                data = json.loads(json_str)
                
                # Log raw response for debugging
                logger.info(f"LLM raw JSON response: {json.dumps(data, indent=2)[:1000]}...")
                
                # Validate and create response object
                llm_response = LLMResponse.from_dict(data)
                
                # Log assistant message for debugging
                if llm_response.assistant_message:
                    logger.info(f"LLM assistant_message: {llm_response.assistant_message}")
                    # Check if it's a generic message
                    generic_patterns = [
                        "ready for next instruction",
                        "i need more information",
                        "could you clarify",
                        "can you clarify",
                        "please clarify"
                    ]
                    msg_lower = llm_response.assistant_message.lower()
                    if any(pattern in msg_lower for pattern in generic_patterns) and "?" not in llm_response.assistant_message:
                        logger.warning(f"LLM returned generic message without specific question: {llm_response.assistant_message}")
                else:
                    logger.warning("LLM returned empty assistant_message!")
                
                logger.info(f"LLM returned {len(llm_response.strokes)} strokes")
                return llm_response
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error (attempt {attempt + 1}/{max_retries}): {e}")
                logger.debug(f"Raw response that failed: {response[:200]}...")
                if attempt < max_retries - 1:
                    # Add instruction to fix JSON with more specific guidance
                    prompt += "\n\nERROR: Invalid JSON detected. CRITICAL: You must output ONLY a valid JSON object. Requirements:\n"
                    prompt += "- Start with { and end with }\n"
                    prompt += "- No markdown code blocks (no ```json or ```)\n"
                    prompt += "- No text before or after the JSON\n"
                    prompt += "- All strings properly quoted\n"
                    prompt += "- No trailing commas\n"
                    prompt += "- Valid JSON syntax only. Try again:"
                else:
                    # Log the problematic response for debugging
                    logger.error(f"Failed to parse JSON. Raw response: {response}")
                    raise ValueError(f"Failed to parse JSON after {max_retries} attempts: {e}")
            except Exception as e:
                logger.error(f"LLM call error: {e}")
                if attempt < max_retries - 1:
                    continue
                raise
    
    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        # Log what's being sent (first 500 chars of state section for verification)
        if "CURRENT DRAWING STATE:" in prompt:
            state_section = prompt.split("CURRENT DRAWING STATE:")[1].split("COORDINATE SYSTEM:")[0]
            logger.debug(f"[LLM CALL] State section preview (first 500 chars): {state_section[:500]}...")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a drawing assistant. Always respond with valid JSON only. No markdown, no comments."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent responses
            max_tokens=800,  # Reduced for faster response
            response_format={"type": "json_object"}  # Force JSON mode if supported
        )
        return response.choices[0].message.content
    
    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text
    
    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API with optimized settings for speed."""
        # Log what's being sent (first 500 chars of state section for verification)
        if "CURRENT DRAWING STATE:" in prompt:
            state_section = prompt.split("CURRENT DRAWING STATE:")[1].split("COORDINATE SYSTEM:")[0]
            logger.debug(f"[LLM CALL] State section preview (first 500 chars): {state_section[:500]}...")
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a drawing assistant. Always respond with valid JSON only. No markdown, no comments."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent, accurate responses
            max_tokens=800,  # Reduced for faster response (prompt is now shorter)
            extra_headers={
                "HTTP-Referer": "https://github.com/deltahacks/drawing-system",
                "X-Title": "Drawing System"
            }
        )
        return response.choices[0].message.content
    
    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from LLM response.
        Handles cases where LLM wraps JSON in markdown or adds extra text.
        Also removes JSON comments (// and /* */) which are invalid in JSON.
        """
        # Remove markdown code blocks if present
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```\s*', '', text)
        
        # Remove single-line comments (// comment) - more aggressive
        # Remove // comments that appear after ], }, or , on the same line
        text = re.sub(r'(\]|}|,)\s*//.*?$', r'\1', text, flags=re.MULTILINE)
        # Also remove // comments at start of lines (but preserve strings)
        text = re.sub(r'^\s*//.*?$', '', text, flags=re.MULTILINE)
        
        # Remove multi-line comments (/* comment */)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        
        # Try to find JSON object - improved pattern
        # Match balanced braces more accurately
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if matches:
            # Return the longest match (most likely the full JSON)
            candidate = max(matches, key=len)
            # Clean up candidate (remove any remaining comments)
            candidate = re.sub(r'(\]|}|,)\s*//.*?$', r'\1', candidate, flags=re.MULTILINE)
            candidate = re.sub(r'^\s*//.*?$', '', candidate, flags=re.MULTILINE)
            candidate = re.sub(r'/\*.*?\*/', '', candidate, flags=re.DOTALL)
            # Try to validate it's actually JSON
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON starting from first {
        start_idx = text.find('{')
        if start_idx != -1:
            # Try to find matching closing }
            brace_count = 0
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        candidate = text[start_idx:i+1]
                        # Remove comments from candidate
                        candidate = re.sub(r'(\]|}|,)\s*//.*?$', r'\1', candidate, flags=re.MULTILINE)
                        candidate = re.sub(r'^\s*//.*?$', '', candidate, flags=re.MULTILINE)
                        candidate = re.sub(r'/\*.*?\*/', '', candidate, flags=re.DOTALL)
                        try:
                            json.loads(candidate)
                            return candidate
                        except json.JSONDecodeError:
                            pass
        
        # If no match, try to parse the whole text (with comments removed)
        cleaned = re.sub(r'(\]|}|,)\s*//.*?$', r'\1', text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'^\s*//.*?$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
        return cleaned
    
    def validate_response(self, response: LLMResponse, 
                         max_strokes: int = 5,
                         max_points_per_stroke: int = 50) -> bool:
        """
        Validate LLM response against constraints.
        
        Returns:
            True if valid, raises ValueError if invalid
        """
        if len(response.strokes) > max_strokes:
            raise ValueError(f"Too many strokes: {len(response.strokes)} > {max_strokes}")
        
        for i, stroke in enumerate(response.strokes):
            if len(stroke) > max_points_per_stroke:
                raise ValueError(f"Stroke {i} has too many points: {len(stroke)} > {max_points_per_stroke}")
            
            # Validate coordinates
            for j, (x, y) in enumerate(stroke):
                if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                    raise ValueError(f"Invalid coordinate at stroke {i}, point {j}: ({x}, {y})")
                if x < 0.0 or x > 1.0 or y < 0.0 or y > 1.0:
                    logger.warning(f"Coordinate out of bounds at stroke {i}, point {j}: ({x}, {y}) - will be clamped")
        
        return True
