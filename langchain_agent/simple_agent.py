"""
A simple LangChain agent example that can use either OpenAI or Anthropic models.
The agent can search for information and perform calculations.
"""

import os
from dotenv import load_dotenv
from typing import List, Dict, Any

# Load environment variables from .env file
load_dotenv()

# Determine which model to use based on environment variable
USE_ANTHROPIC = os.getenv("USE_ANTHROPIC", "false").lower() == "true"
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))

if USE_ANTHROPIC:
    # Import Anthropic modules
    from langchain_anthropic import ChatAnthropic
    from langchain.agents import AgentType, AgentExecutor, create_react_agent
    from langchain.tools import tool
    from langchain.agents.format_scratchpad.tools import format_to_tool_messages

    # Initialize Anthropic model
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    
    llm = ChatAnthropic(
        model="claude-3-sonnet-20240229",
        temperature=TEMPERATURE,
        anthropic_api_key=anthropic_api_key
    )
else:
    # Import OpenAI modules
    from langchain_openai import ChatOpenAI
    from langchain.agents import AgentType, AgentExecutor, create_react_agent
    from langchain.tools import tool
    
    # Initialize OpenAI model
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    llm = ChatOpenAI(
        model="gpt-3.5-turbo",
        temperature=TEMPERATURE,
        openai_api_key=openai_api_key
    )

# Define tools for the agent
@tool
def search_web(query: str) -> str:
    """
    Search the web for information about a query.
    
    Args:
        query: The search query
        
    Returns:
        str: Search results
    """
    # This is a simulated search function
    if "weather" in query.lower():
        return "The current weather is sunny with a high of 75°F."
    elif "population" in query.lower():
        return "The world population is approximately 8 billion people as of 2023."
    elif "president" in query.lower() and "united states" in query.lower():
        return "Joe Biden is the current President of the United States."
    else:
        return f"Found some information about: {query}"

@tool
def calculator(expression: str) -> str:
    """
    Calculate the result of a mathematical expression.
    
    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2")
        
    Returns:
        str: The result of the calculation
    """
    try:
        # Using eval is generally not recommended for production applications,
        # but is used here for simplicity
        result = eval(expression)
        return f"The result of {expression} is {result}"
    except Exception as e:
        return f"Error calculating {expression}: {str(e)}"

# Create the tools list
tools = [search_web, calculator]

# Create the agent
if USE_ANTHROPIC:
    # For Anthropic models, we need to format the scratchpad differently
    from langchain.agents.format_scratchpad.tools import format_to_tool_messages
    from langchain.agents.output_parsers.tools import ToolsAgentOutputParser

    # Create the agent with the appropriate prompt
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI assistant that helps with information retrieval and calculations."),
        ("user", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=VERBOSE,
        handle_parsing_errors=True
    )
else:
    # For OpenAI models, we can use a simpler setup
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        verbose=VERBOSE
    )
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=VERBOSE,
        handle_parsing_errors=True
    )

# Main function to handle user queries
def process_query(query: str) -> str:
    """
    Process a user query using the agent.
    
    Args:
        query: User's question or instruction
        
    Returns:
        str: Agent's response
    """
    try:
        result = agent_executor.invoke({"input": query})
        return result["output"]
    except Exception as e:
        return f"Error processing your query: {str(e)}"

if __name__ == "__main__":
    print("🤖 Simple LangChain Agent")
    print("------------------------")
    print(f"Using {'Anthropic Claude' if USE_ANTHROPIC else 'OpenAI GPT'} model")
    print("Type 'exit' to quit\n")
    
    while True:
        user_input = input("\n👤 Enter your query: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Goodbye!")
            break
            
        print("\n🔍 Processing...")
        response = process_query(user_input)
        print(f"\n🤖 Response: {response}") 