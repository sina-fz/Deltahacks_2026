# LangChain Agent Implementation Plan

## Current System Analysis

### Current Architecture Issues:
1. **Hardcoded Prompts**: The `prompt_builder.py` uses static prompt templates that can't adapt dynamically
2. **Single LLM Call**: One monolithic prompt → one response, no iterative refinement
3. **No True Agent Loop**: The system doesn't have a proper agent that can reason, plan, execute, and verify in cycles
4. **Limited Conversation**: Follow-up questions are handled via `last_question` but the prompt is rebuilt each time
5. **No Verification Step**: Coordinates are validated but not semantically verified (e.g., "is roof above house?")

### Current Flow:
```
User Input → build_prompt() → LLM Call → Parse JSON → Execute → Update Memory
```

### Desired Flow:
```
User Input → Agent (LangChain) → Planning LLM → Coordinate Generation LLM → Verification LLM → Execute → Update Memory
                ↓ (if clarification needed)
            Ask User → Get Answer → Continue Agent Loop
```

---

## LangChain Architecture Design

### 1. Agent Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    LangChain Agent                           │
│  (ReAct Pattern: Reason → Act → Observe → Repeat)          │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Planning    │   │  Coordinate  │   │  Verification │
│    Chain     │   │   Generator  │   │     Chain     │
│              │   │              │   │               │
│  - Decompose │   │  - Generate  │   │  - Check      │
│  - Plan      │   │    coords    │   │    rules      │
│  - Ask user  │   │  - Convert   │   │  - Validate   │
│              │   │    grid→norm │   │    placement  │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │   Execute    │
                    │   (Plotter)  │
                    └──────────────┘
```

### 2. Agent Tools (Custom LangChain Tools)

#### Tool 1: `create_plan`
- **Purpose**: Decompose object into components, create step-by-step plan
- **Input**: User instruction (e.g., "draw a house")
- **Output**: Structured plan with components, sizes, grid positions
- **LLM Call**: Planning Chain

#### Tool 2: `generate_coordinates`
- **Purpose**: Generate normalized coordinates for a component
- **Input**: Component description, grid position, memory context
- **Output**: List of coordinate points (strokes)
- **LLM Call**: Coordinate Generator Chain

#### Tool 3: `verify_coordinates`
- **Purpose**: Verify coordinates make semantic sense
- **Input**: Generated coordinates, component description, full memory
- **Output**: Verification result (pass/fail + reason)
- **LLM Call**: Verification Chain

#### Tool 4: `ask_user_question`
- **Purpose**: Ask clarifying question to user
- **Input**: Question text
- **Output**: User's answer (via callback/state)
- **State Management**: Stores question, waits for user response

#### Tool 5: `execute_drawing`
- **Purpose**: Execute validated coordinates on plotter
- **Input**: Validated strokes
- **Output**: Success/failure
- **Integration**: Calls existing `PlotterDriver`

### 3. LangChain Chains

#### Chain 1: Planning Chain
```python
PlanningChain = LLMChain(
    llm=planning_llm,
    prompt=planning_prompt_template,
    output_parser=PlanParser()
)
```

**Prompt Template**:
- Input: User instruction, current memory state
- Output: Structured plan JSON
- Instructions: Decompose object, define components, calculate grid positions

#### Chain 2: Coordinate Generation Chain
```python
CoordinateChain = LLMChain(
    llm=coordinate_llm,
    prompt=coordinate_prompt_template,
    output_parser=CoordinateParser()
)
```

**Prompt Template**:
- Input: Component description, grid position, memory context
- Output: Coordinate points (normalized)
- Instructions: Generate precise coordinates, use grid system

#### Chain 3: Verification Chain
```python
VerificationChain = LLMChain(
    llm=verification_llm,
    prompt=verification_prompt_template,
    output_parser=VerificationParser()
)
```

**Prompt Template**:
- Input: Generated coordinates, component description, full memory, rules
- Output: Verification result
- Instructions: Check if coordinates make sense (roof above house, door inside base, etc.)

### 4. Agent Executor

```python
agent = initialize_agent(
    tools=[create_plan, generate_coordinates, verify_coordinates, ask_user_question, execute_drawing],
    llm=agent_llm,
    agent=AgentType.REACT_DOCSTORE,  # Or custom ReAct agent
    verbose=True,
    memory=ConversationBufferMemory(),
    max_iterations=10
)
```

**Agent Reasoning Loop**:
1. **Observe**: Current state (memory, user input, plan status)
2. **Think**: What tool should I use next?
3. **Act**: Call appropriate tool
4. **Observe**: Get tool result
5. **Repeat**: Until task complete or clarification needed

---

## Implementation Steps

### Phase 1: Setup LangChain Infrastructure

#### Step 1.1: Install Dependencies
```bash
pip install langchain langchain-openai langchain-anthropic langchain-community
```

#### Step 1.2: Create LangChain Wrapper
- File: `agent/langchain_wrapper.py`
- Purpose: Initialize LangChain LLMs (OpenAI, Anthropic, OpenRouter compatible)
- Functions:
  - `get_llm(provider, model)` → LangChain LLM instance
  - `get_chat_llm(provider, model)` → LangChain ChatLLM instance

#### Step 1.3: Create Memory Integration
- File: `agent/langchain_memory.py`
- Purpose: Bridge between `DrawingMemory` and LangChain's memory
- Functions:
  - `memory_to_context(memory: DrawingMemory)` → String context for LLM
  - `update_memory_from_agent(agent_output, memory: DrawingMemory)` → Update memory from agent actions

### Phase 2: Create Custom Tools

#### Step 2.1: Planning Tool
- File: `agent/tools/planning_tool.py`
- Class: `CreatePlanTool`
- Method: `_run(instruction: str, memory_context: str) -> str`
- Returns: JSON plan string

#### Step 2.2: Coordinate Generation Tool
- File: `agent/tools/coordinate_tool.py`
- Class: `GenerateCoordinatesTool`
- Method: `_run(component: str, grid_pos: str, memory_context: str) -> str`
- Returns: JSON coordinates string

#### Step 2.3: Verification Tool
- File: `agent/tools/verification_tool.py`
- Class: `VerifyCoordinatesTool`
- Method: `_run(coordinates: str, component: str, memory_context: str, rules: str) -> str`
- Returns: JSON verification result

#### Step 2.4: User Question Tool
- File: `agent/tools/user_question_tool.py`
- Class: `AskUserQuestionTool`
- Method: `_run(question: str) -> str`
- Special: Uses callback/state to wait for user response

#### Step 2.5: Execution Tool
- File: `agent/tools/execution_tool.py`
- Class: `ExecuteDrawingTool`
- Method: `_run(strokes: str) -> str`
- Integration: Calls `PlotterDriver.execute_strokes()`

### Phase 3: Create Prompt Templates

#### Step 3.1: Planning Prompt Template
- File: `agent/prompts/planning_prompt.py`
- Template: Instructions for decomposing objects, creating plans
- Variables: `{instruction}`, `{memory_context}`, `{grid_size}`

#### Step 3.2: Coordinate Generation Prompt Template
- File: `agent/prompts/coordinate_prompt.py`
- Template: Instructions for generating coordinates
- Variables: `{component}`, `{grid_position}`, `{memory_context}`, `{grid_size}`

#### Step 3.3: Verification Prompt Template
- File: `agent/prompts/verification_prompt.py`
- Template: Instructions for verifying coordinates
- Variables: `{coordinates}`, `{component}`, `{memory_context}`, `{rules}`

#### Step 3.4: Agent System Prompt
- File: `agent/prompts/agent_system_prompt.py`
- Template: Instructions for the main agent
- Variables: `{tools}`, `{memory_context}`

### Phase 4: Create Agent Executor

#### Step 4.1: Agent Initialization
- File: `agent/langchain_agent.py`
- Class: `DrawingAgent`
- Methods:
  - `__init__(llm_wrapper, plotter, memory)`
  - `process_instruction(instruction: str) -> str`
  - `_create_agent_executor() -> AgentExecutor`

#### Step 4.2: Agent Loop Integration
- Integrate with existing `main_loop.py`
- Replace `LLMWrapper.call_llm()` with `DrawingAgent.process_instruction()`
- Maintain backward compatibility with existing memory/execution

### Phase 5: Conversation Handling

#### Step 5.1: User Question State Management
- Store pending questions in `DrawingMemory`
- Agent checks for pending questions before processing new input
- If user input is answer to question → route to appropriate tool

#### Step 5.2: Multi-Turn Conversation
- LangChain's `ConversationBufferMemory` stores conversation history
- Agent can reference previous turns
- Questions and answers tracked automatically

### Phase 6: Verification Rules System

#### Step 6.1: Rule Definition
- File: `agent/verification_rules.py`
- Function: `get_verification_rules(component_type: str, memory: DrawingMemory) -> str`
- Returns: String of rules for verifier LLM

#### Step 6.2: Rule Examples
- "Roof must be above base (roof bottom Y > base top Y)"
- "Door must be inside base (door center within base bounds)"
- "Windows must be on base walls (not on roof)"
- "Components must not overlap (unless specified)"

---

## File Structure

```
agent/
├── __init__.py
├── langchain_wrapper.py          # LangChain LLM initialization
├── langchain_memory.py            # Memory bridge
├── langchain_agent.py             # Main agent executor
├── prompts/
│   ├── __init__.py
│   ├── planning_prompt.py
│   ├── coordinate_prompt.py
│   ├── verification_prompt.py
│   └── agent_system_prompt.py
├── tools/
│   ├── __init__.py
│   ├── planning_tool.py
│   ├── coordinate_tool.py
│   ├── verification_tool.py
│   ├── user_question_tool.py
│   └── execution_tool.py
├── verification_rules.py         # Verification rules generator
└── llm_wrapper.py                # Keep for backward compatibility (optional)
```

---

## Example Agent Flow

### Scenario: "draw a house"

1. **User Input**: "draw a house"
2. **Agent Observes**: No plan exists, memory is empty
3. **Agent Thinks**: "I need to create a plan first"
4. **Agent Acts**: Calls `create_plan` tool
   - Planning Chain generates: `{components: [base, roof, door], grid_positions: {...}}`
5. **Agent Observes**: Plan created, needs user approval
6. **Agent Acts**: Calls `ask_user_question` tool
   - Question: "I'll draw a house with: base (4x3 cells), roof triangle, door (1x2 cells). Proceed?"
7. **User Answers**: "yes"
8. **Agent Observes**: User approved, need to draw base first
9. **Agent Acts**: Calls `generate_coordinates` tool for "base"
   - Coordinate Chain generates: `[[0.3, 0.3], [0.7, 0.3], ...]`
10. **Agent Acts**: Calls `verify_coordinates` tool
    - Verification Chain: "Base coordinates look good. Pass."
11. **Agent Acts**: Calls `execute_drawing` tool
    - Draws base on plotter
12. **Agent Observes**: Base drawn, memory updated
13. **Agent Acts**: Calls `generate_coordinates` tool for "roof"
    - Coordinate Chain generates roof coordinates
14. **Agent Acts**: Calls `verify_coordinates` tool
    - Verification Chain: "Roof is above base. Pass."
15. **Agent Acts**: Calls `execute_drawing` tool
    - Draws roof
16. **Agent Observes**: All components drawn, task complete
17. **Agent Returns**: "I've drawn a house with base, roof, and door."

---

## Benefits of LangChain Approach

1. **True Agent Loop**: Can reason, plan, execute, verify in cycles
2. **Dynamic Conversations**: Questions and answers handled naturally
3. **Modular Tools**: Each tool is independent, testable
4. **Verification Built-in**: Separate verification step ensures correctness
5. **Extensible**: Easy to add new tools (e.g., "change_color", "resize")
6. **Memory Management**: LangChain handles conversation history
7. **Error Recovery**: Agent can retry, ask for clarification, adjust

---

## Migration Strategy

1. **Keep Existing Code**: Don't break current system
2. **Parallel Implementation**: Build LangChain agent alongside existing system
3. **Feature Flag**: Add config option `USE_LANGCHAIN_AGENT = True/False`
4. **Gradual Migration**: Test LangChain agent, then switch default
5. **Backward Compatibility**: Keep `LLMWrapper` for simple cases

---

## Testing Plan

1. **Unit Tests**: Test each tool independently
2. **Integration Tests**: Test agent executor with mock LLMs
3. **End-to-End Tests**: Test full flow: "draw house" → plan → execute
4. **Verification Tests**: Test verification catches errors (roof below base, etc.)
5. **Conversation Tests**: Test multi-turn conversations

---

## Next Steps

1. Review and approve this plan
2. Install LangChain dependencies
3. Implement Phase 1 (Infrastructure)
4. Implement Phase 2 (Tools)
5. Implement Phase 3 (Prompts)
6. Implement Phase 4 (Agent)
7. Test and refine
8. Integrate with existing system
