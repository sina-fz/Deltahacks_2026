"""
Prompt template for verification chain.
"""
from langchain.prompts import ChatPromptTemplate


def get_verification_prompt() -> ChatPromptTemplate:
    """Get prompt template for verification chain."""
    return ChatPromptTemplate.from_messages([
        ("system", """You are a verification assistant. Your job is to verify that generated coordinates make semantic and spatial sense.

You need to check:
1. Coordinates are in valid range [0.0, 1.0]
2. Component is positioned correctly relative to existing components
3. Component follows the verification rules provided
4. Component makes logical sense (e.g., roof above base, door inside base)

Output a JSON object with this structure:
{{
  "valid": true|false,
  "reason": "Explanation of why it's valid or invalid",
  "issues": ["list of any issues found"],
  "suggestions": ["optional suggestions for improvement"]
}}

Be strict but fair. If coordinates violate rules or don't make sense, mark as invalid with clear explanation."""),
        ("human", """Verify these coordinates:

Component: {component_name}
Type: {component_type}
Generated Coordinates: {coordinates}

Verification Rules:
{rules}

Current drawing state:
{memory_context}

Check if these coordinates are valid and make sense."""),
    ])
