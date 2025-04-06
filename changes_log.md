# Changes Log

## 2025-04-06

### AI Model Updates in simple_agent.py

1. Changed OpenAI model from "gpt-3.5-turbo" to "gpt-4o"
2. Changed Claude model from "claude-3-sonnet-20240229" to "claude-3-5-sonnet-latest"
3. Fixed prompt issues by using the react_prompt from the hub directly for both models
4. Successfully tested with Claude model (USE_ANTHROPIC=true in .env file)

The agent now works correctly with both models and can be switched between them by changing the USE_ANTHROPIC environment variable.
