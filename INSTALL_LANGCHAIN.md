# Installing LangChain Dependencies

The LangChain agent system requires additional Python packages.

## Installation

Run this command to install all required LangChain packages:

```bash
pip install langchain langchain-openai langchain-anthropic langchain-community
```

Or install from requirements.txt (which includes LangChain):

```bash
pip install -r requirements.txt
```

## Verification

After installation, verify it works:

```bash
python -c "from agent.langchain_wrapper import get_agent_llm; print('LangChain OK')"
```

## Fallback

If LangChain packages are not installed, the system will automatically fall back to the legacy system. You'll see a warning in the logs:

```
LangChain packages not installed. Falling back to legacy system.
```

## Troubleshooting

- **ModuleNotFoundError**: Make sure you're in the correct virtual environment
- **Version conflicts**: Try installing specific versions:
  ```bash
  pip install langchain==0.1.0 langchain-openai==0.0.5 langchain-anthropic==0.1.0 langchain-community==0.0.20
  ```
