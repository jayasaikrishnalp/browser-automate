"""
An advanced LangChain agent example with memory and additional tools.
This agent builds on the simple agent but adds conversation memory and
more sophisticated tools.
"""

import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import datetime
import json

# Load environment variables from .env file
load_dotenv()

# Determine which model to use based on environment variable
USE_ANTHROPIC = os.getenv("USE_ANTHROPIC", "false").lower() == "true"
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))

# Import memory modules
from langchain.memory import ConversationBufferMemory
from langchain.schema import messages_from_dict, messages_to_dict

# Import agents/tools modules
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

if USE_ANTHROPIC:
    # Import Anthropic modules
    from langchain_anthropic import ChatAnthropic
    
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

@tool
def get_date_time() -> str:
    """
    Get the current date and time.
    
    Returns:
        str: Current date and time information
    """
    now = datetime.datetime.now()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

@tool
def store_information(key: str, value: str) -> str:
    """
    Store information in the agent's memory that can be retrieved later.
    
    Args:
        key: The key to store the information under
        value: The information to store
        
    Returns:
        str: Confirmation message
    """
    # Use a simple JSON file for persistent storage
    storage_file = "langchain_agent/memory_storage.json"
    
    try:
        # Load existing data
        if os.path.exists(storage_file):
            with open(storage_file, 'r') as f:
                data = json.load(f)
        else:
            data = {}
        
        # Update with new information
        data[key] = value
        
        # Save back to file
        with open(storage_file, 'w') as f:
            json.dump(data, f, indent=2)
            
        return f"Successfully stored information under key: {key}"
    except Exception as e:
        return f"Error storing information: {str(e)}"

@tool
def retrieve_information(key: str) -> str:
    """
    Retrieve information previously stored in the agent's memory.
    
    Args:
        key: The key to retrieve information for
        
    Returns:
        str: The stored information or an error message
    """
    storage_file = "langchain_agent/memory_storage.json"
    
    try:
        # Check if storage file exists
        if not os.path.exists(storage_file):
            return f"No information found for key: {key}"
        
        # Load data
        with open(storage_file, 'r') as f:
            data = json.load(f)
        
        # Retrieve information
        if key in data:
            return f"Retrieved information for {key}: {data[key]}"
        else:
            return f"No information found for key: {key}"
    except Exception as e:
        return f"Error retrieving information: {str(e)}"

# Create the tools list
tools = [search_web, calculator, get_date_time, store_information, retrieve_information]

# Setup conversation memory
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

# Create a custom system message that includes tool descriptions and Telugu capabilities
system_message = """You are an advanced AI assistant with various capabilities. 
You can search for information, perform calculations, check the current date and time, 
and store/retrieve information.

You are also able to understand and respond in both English and Telugu languages.
If the user speaks in Telugu, try to respond in Telugu if appropriate.

Follow these rules:
1. Use tools when appropriate to find or process information
2. Always provide clear, accurate responses
3. For Telugu inputs, first understand them clearly before responding
4. Maintain a consistent conversation by remembering previous interactions
5. Be helpful, respectful, and informative
"""

# Create the agent
prompt = ChatPromptTemplate.from_messages([
    ("system", system_message),
    MessagesPlaceholder(variable_name="chat_history"),
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
    memory=memory,
    verbose=VERBOSE,
    handle_parsing_errors=True
)

# Save and load conversation functionality
def save_conversation(filename="langchain_agent/conversation.json"):
    """Save the current conversation to a file."""
    try:
        # Convert memory messages to a serializable format
        messages_dict = messages_to_dict(memory.chat_memory.messages)
        
        # Save to file
        with open(filename, "w") as f:
            json.dump(messages_dict, f, indent=2)
            
        return f"Conversation saved to {filename}"
    except Exception as e:
        return f"Error saving conversation: {str(e)}"

def load_conversation(filename="langchain_agent/conversation.json"):
    """Load a saved conversation from a file."""
    try:
        if not os.path.exists(filename):
            return "No saved conversation found."
            
        # Load from file
        with open(filename, "r") as f:
            messages_dict = json.load(f)
            
        # Convert back to message objects
        messages = messages_from_dict(messages_dict)
        
        # Replace memory with loaded messages
        memory.chat_memory.messages = messages
            
        return f"Conversation loaded from {filename}"
    except Exception as e:
        return f"Error loading conversation: {str(e)}"

# Main function to handle user interaction
def main():
    print("🤖 Advanced LangChain Agent")
    print("---------------------------")
    print(f"Using {'Anthropic Claude' if USE_ANTHROPIC else 'OpenAI GPT'} model")
    print("Special commands:")
    print("  /save - Save the conversation")
    print("  /load - Load a saved conversation")
    print("  /clear - Clear the conversation history")
    print("  /exit - Exit the program")
    print("\nStart chatting with the agent!\n")
    
    while True:
        user_input = input("\n👤 Enter your message: ")
        
        # Handle special commands
        if user_input.strip().lower() == "/exit":
            print("Goodbye!")
            break
        elif user_input.strip().lower() == "/save":
            result = save_conversation()
            print(f"🖥️ System: {result}")
            continue
        elif user_input.strip().lower() == "/load":
            result = load_conversation()
            print(f"🖥️ System: {result}")
            continue
        elif user_input.strip().lower() == "/clear":
            memory.clear()
            print("🖥️ System: Conversation history cleared.")
            continue
            
        # Process regular input
        try:
            result = agent_executor.invoke({"input": user_input})
            response = result["output"]
            print(f"\n🤖 Assistant: {response}")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    # Create storage directory if it doesn't exist
    os.makedirs("langchain_agent", exist_ok=True)
    main() 