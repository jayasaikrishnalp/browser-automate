"""
Example demonstrating how to capture screenshots when using browser-use with an Agent.
This shows how to save both the full history and individual screenshots.
"""

import asyncio
import base64
import os
import json
import sys
from pathlib import Path
from datetime import datetime
import platform

# Try to import dotenv - if not available, continue without it
try:
    from dotenv import load_dotenv
    
    # Load environment variables from .env file
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded environment variables from {env_path}")
    else:
        print("No .env file found. Using environment variables from system.")
except ImportError:
    print("dotenv package not found. Using environment variables from system.")

# Configure browser-use logging level
browser_logging_level = os.getenv("BROWSER_USE_LOGGING_LEVEL", "info")
print(f"Browser-use logging level: {browser_logging_level}")

# Configure telemetry
anonymized_telemetry = os.getenv("ANONYMIZED_TELEMETRY", "true").lower() in ("true", "t", "1", "yes", "y")
print(f"Anonymized telemetry: {'Enabled' if anonymized_telemetry else 'Disabled'}")

# Set browser-use specific environment variables
os.environ["BROWSER_USE_LOGGING_LEVEL"] = browser_logging_level
os.environ["ANONYMIZED_TELEMETRY"] = str(anonymized_telemetry).lower()

# Ensure screenshot directories exist
screenshots_dir = os.getenv("SCREENSHOTS_DIR", "agent_screenshots")
os.makedirs(screenshots_dir, exist_ok=True)

# Get log file path from environment if provided
log_file = os.getenv("LOG_FILE")
if log_file:
    # Set up a file handler for logging
    import logging
    
    # Create a custom formatter that includes time
    class DetailedFormatter(logging.Formatter):
        def format(self, record):
            # Add timestamp to all log messages
            return f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} {record.levelname:<8} [{record.name}] {record.getMessage()}"
    
    # Configure more detailed logging to properly capture all agent logs
    file_handler = logging.FileHandler(log_file)
    detailed_formatter = DetailedFormatter()
    file_handler.setFormatter(detailed_formatter)
    
    # Add the handler to the root logger to capture all logs
    root_logger = logging.getLogger()
    root_logger.addHandler(file_handler)
    
    # Also add a stream handler to print to stderr for debugging
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(stream_handler)
    
    # Set root level to INFO to capture most relevant logs
    if root_logger.level == 0:  # If not already set
        root_logger.setLevel(logging.INFO)
    
    # Ensure browser_use logger also logs to this file
    for logger_name in ['browser_use', 'browser_use.agent', 'browser_use.controller']:
        logger = logging.getLogger(logger_name)
        # Force the logger to use the root logger's handlers
        logger.handlers = []
        logger.propagate = True
        if logger.level == 0:  # If not already set
            logger.setLevel(logging.INFO)
    
    logging.info(f"Logging to file: {log_file}")

# Additional logging for tracking agent progress
def log_agent_step(step_number, message):
    """Log a detailed agent step with a step number."""
    logging.info(f"📍 Step {step_number}: {message}")

def log_agent_goal(goal):
    """Log the agent's current goal."""
    logging.info(f"🎯 Next goal: {goal}")

def log_agent_action(action_number, total_actions, action_details):
    """Log an agent action with detailed information."""
    logging.info(f"🛠️ Action {action_number}/{total_actions}: {action_details}")

def log_agent_success(message):
    """Log a successful agent action."""
    logging.info(f"👍 Success - {message}")

def log_agent_completion(message, success=True):
    """Log the completion of an agent task."""
    status = "✅" if success else "❌"
    logging.info(f"{status} {message}")

# Extract screenshot info from task description
def extract_screenshot_info_from_task(task):
    """Extract screenshot descriptions and filenames from a task using the pattern [SCREENSHOT] or [SCREENSHOT: Description - filename.png]"""
    import re
    
    # First try the detailed pattern with description and filename
    detailed_pattern = r'\[SCREENSHOT:\s*(.*?)\s*-\s*(.*?)\]'
    detailed_matches = re.findall(detailed_pattern, task)
    
    # Then try the simple pattern
    simple_pattern = r'\[SCREENSHOT\]'
    simple_matches = re.findall(simple_pattern, task)
    
    # Create a list of {description, filename} dictionaries
    screenshot_info = []
    
    # Process detailed matches first
    for match in detailed_matches:
        if len(match) == 2:
            description, filename = match
            screenshot_info.append({
                'description': description.strip(),
                'filename': filename.strip()
            })
    
    # Process simple matches - no description or filename provided
    # So we'll just create placeholder entries
    for _ in simple_matches:
        screenshot_info.append({
            'description': '',
            'filename': ''
        })
    
    # If we still have no matches but have screenshots in the task, 
    # fallback to just counting [SCREENSHOT] occurrences
    if not screenshot_info and '[SCREENSHOT]' in task:
        count = task.count('[SCREENSHOT]')
        for i in range(count):
            screenshot_info.append({
                'description': f'Screenshot {i+1}',
                'filename': f'screenshot_{i+1}.png'
            })
    
    return screenshot_info

# Function to save screenshots from agent history
def save_screenshots_from_history(history, screenshot_dir, task=""):
    """Extract and save all screenshots from agent history using names from task if available."""
    # Create directories
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # Try to extract screenshot info from task
    screenshot_info = extract_screenshot_info_from_task(task)
    print(f"Found {len(screenshot_info)} screenshot definitions in task")
    # Print number of history items
    print(f"Processing {len(history.history)} history items")
    
    # Process each history item
    for i, item in enumerate(history.history):
        # Skip the first screenshot as it's usually just a blank page
        if i == 0 and (not hasattr(item.state, 'url') or not item.state.url):
            print(f"Skipping first blank page screenshot")
            continue
        
        if not item.state or not item.state.screenshot:
            continue
        
        # Get URL and title if available for better filename generation
        url = item.state.url if hasattr(item.state, 'url') and item.state.url else ""
        title = item.state.title if hasattr(item.state, 'title') and item.state.title else ""
        
        # Skip about:blank pages as they're typically just black/empty screens
        if url == "about:blank" or (not url and not title):
            print(f"Skipping about:blank or empty page screenshot")
            continue
        
        # Determine filename - use task-defined name if available
        if i < len(screenshot_info) and screenshot_info[i]['filename']:
            # Use the filename from the task
            filename = screenshot_info[i]['filename']
            description = screenshot_info[i]['description'] or title or f"Step_{i}"
            print(f"Using task-defined name for step {i}: {description} -> {filename}")
        else:
            # Generate a descriptive name based on page title and URL
            description = title or f"Step_{i}"
            
            # Create a descriptive filename
            # Extract domain from URL
            if url:
                domain_parts = url.replace("https://", "").replace("http://", "").split('/')
                domain = domain_parts[0] if domain_parts else ""
                # Clean up domain
                domain = domain.replace("www.", "").split(':')[0]  # Remove www. and port if any
            else:
                domain = "unknown"
            
            # Create a clean, simplified filename that's not overly long
            if title:
                # Remove any special characters from title and limit length
                clean_title = ''.join(c if c.isalnum() or c == ' ' else '_' for c in title)
                clean_title = clean_title.strip().replace(' ', '_')[:20]  # First 20 chars of title
                filename = f"{domain}_{clean_title}_{i}.png"
            else:
                filename = f"{domain}_step_{i}.png"
            
            print(f"Generated name for step {i}: {filename}")
        
        # Make sure filename is valid - only use alphanumeric, periods, underscores and hyphens
        filename = ''.join(c for c in filename if c.isalnum() or c in '._-')
        # Limit filename length to avoid path issues
        if len(filename) > 80:
            extension = filename.split('.')[-1] if '.' in filename else 'png'
            filename = filename[:75] + '.' + extension
            
        file_path = os.path.join(screenshot_dir, filename)
        
        # Decode and save
        img_data = base64.b64decode(item.state.screenshot)
        with open(file_path, 'wb') as f:
            f.write(img_data)
        print(f"Saved screenshot: {file_path}")

async def main():
    # Check for required dependencies
    missing_dependencies = []
    try:
        import PIL
    except ImportError:
        missing_dependencies.append("Pillow")
        print("WARNING: Pillow (PIL) is not installed. Screenshot processing and GIF creation will be limited.")
        print("To enable full functionality, install: pip install Pillow")
    
    try:
        # Import browser-use components
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        print("Required packages not found. Install with:")
        print("pip install browser-use langchain-anthropic")
        return
    
    # Setup timestamp for unique folder names
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get task from environment variable or file
    task_file = os.getenv("TASK_FILE")
    if task_file and os.path.exists(task_file):
        with open(task_file, "r") as f:
            task = f.read()
        print(f"Task loaded from file: {task_file}")
    else:
        task = """
        Default task: Navigate to google.com and search for "browser automation".
        [SCREENSHOT: Google Homepage - google_home.png]
        [SCREENSHOT: Search Results - search_results.png]
        """
        print("Using default task")
    
    # Get screenshot directory from environment variable or use default
    screenshot_dir = os.getenv("SCREENSHOT_DIR", f"agent_screenshots/run_{timestamp}")
    print(f"Using screenshot directory: {screenshot_dir}")
    
    # Make sure directory exists
    os.makedirs(screenshot_dir, exist_ok=True)
    
    # Get highlight elements setting from environment variable
    highlight_elements = os.getenv("HIGHLIGHT_ELEMENTS", "True").lower() in ("true", "t", "1", "yes", "y")
    print(f"Element highlighting: {'Enabled' if highlight_elements else 'Disabled'}")

    # Get headless mode setting from environment variable
    headless_mode = os.getenv("HEADLESS_MODE", "False").lower() in ("true", "t", "1", "yes", "y")
    print(f"Headless mode: {'Enabled' if headless_mode else 'Disabled'}")

    # Get local browser setting from environment variable
    use_local_browser = os.getenv("USE_LOCAL_BROWSER", "False").lower() in ("true", "t", "1", "yes", "y")
    print(f"Local browser: {'Enabled' if use_local_browser else 'Disabled'}")
    
    # Configure browser with platform-specific Chrome paths
    chrome_path = None
    
    # First check if a specific Chrome path was provided via environment variable
    chrome_path = os.getenv("CHROME_PATH")
    if chrome_path and os.path.exists(chrome_path):
        print(f"Using provided Chrome path: {chrome_path}")
    elif use_local_browser:
        # Auto-detect Chrome path based on platform
        system = platform.system()
        
        if system == "Darwin":  # macOS
            default_path = os.getenv("CHROME_PATH_MACOS", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            if os.path.exists(default_path):
                chrome_path = default_path
        elif system == "Windows":
            # Check common Windows Chrome paths
            windows_path = os.getenv("CHROME_PATH_WINDOWS")
            if windows_path and os.path.exists(windows_path):
                chrome_path = windows_path
            else:
                # Try common locations
                potential_paths = [
                    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe")
                ]
                for path in potential_paths:
                    if os.path.exists(path):
                        chrome_path = path
                        break
        elif system == "Linux":
            # Check Linux Chrome path
            linux_path = os.getenv("CHROME_PATH_LINUX")
            if linux_path and os.path.exists(linux_path):
                chrome_path = linux_path
            else:
                # Try common locations
                potential_paths = [
                    "/usr/bin/google-chrome",
                    "/usr/bin/chromium-browser",
                    "/usr/bin/chromium"
                ]
                for path in potential_paths:
                    if os.path.exists(path):
                        chrome_path = path
                        break
        
        if chrome_path:
            print(f"Auto-detected Chrome at: {chrome_path}")
        else:
            print("Could not auto-detect Chrome installation. Will use default browser.")
    
    # Configure browser
    browser_args = []
    debug_port_detected = False
    debug_port = int(os.getenv("DEBUG_PORT", "9222"))
    
    # Check if Chrome is running in debug mode on port 9222
    if use_local_browser:
        print(f"Checking if Chrome is running in debug mode on port {debug_port}...")
        try:
            import httpx
            response = httpx.get(f"http://localhost:{debug_port}/json/version", timeout=3.0)
            if response.status_code == 200:
                browser_info = response.json()
                print(f"Found Chrome running in debug mode: {browser_info.get('Browser', 'Unknown version')}")
                debug_port_detected = True
                # Add debug-specific args if needed
                browser_args.append(f"--remote-debugging-port={debug_port}")
            else:
                print(f"No Chrome instance found running in debug mode on port {debug_port}")
        except Exception as e:
            print(f"Error checking debug port: {e}")
    
    # Setup the config for the browser
    browser_config = BrowserConfig(
        headless=headless_mode,  # Use the headless mode setting from environment
    )
    
    # Configure logging
    if browser_logging_level == "debug":
        # Enable debug mode
        os.environ["BROWSER_USE_DEBUG"] = "true"
    
    # Add custom Chrome executable if found
    if use_local_browser and chrome_path and os.path.exists(chrome_path):
        print(f"Using Chrome at path: {chrome_path}")
        # Set environment variable for the browser-use package
        os.environ["BROWSER_PATH"] = chrome_path
        os.environ["BROWSER_USE_CHROME_PATH"] = chrome_path
        os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = chrome_path
        
        # Set the chrome_instance_path in the BrowserConfig
        browser_config = BrowserConfig(
            headless=headless_mode,  # Use the headless mode setting from environment
            chrome_instance_path=chrome_path,  # This is the key setting needed to use the custom Chrome path
        )
        # Preserve highlight_elements setting
        browser_config.new_context_config.highlight_elements = highlight_elements
        print(f"BrowserConfig configured with chrome_instance_path: {chrome_path}")
    else:
        # Configure element highlighting only for the default case
        browser_config.new_context_config.highlight_elements = highlight_elements
    
    # Create a browser instance
    print("Starting browser...")
    browser = Browser(config=browser_config)
    
    # Initialize LLM (Claude) with vision capabilities
    try:
        llm = ChatAnthropic(
            model_name="claude-3-7-sonnet-20250219",  # Updated model name
            temperature=0.7,
            timeout=600,  # 10 minutes timeout
            stop=None,
        )
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        print("Make sure you have set ANTHROPIC_API_KEY environment variable")
        await browser.close()
        return
    
    # Configure the agent with automatic history saving
    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        use_vision=True,  # Enable vision capabilities
        
        # Save all conversation history including screenshots
        save_conversation_path=screenshot_dir,
        
        # Generate a GIF of the interaction only if PIL is available
        generate_gif=f"{screenshot_dir}/session.gif" if "Pillow" not in missing_dependencies else False,
    )
    
    try:
        # Run the agent
        print(f"Running agent with task: {task}")
        history = await agent.run()
        
        # Display final result
        final_result = history.final_result()
        if final_result:
            print("\nFinal result:")
            print(final_result)
        
        # Extract and save individual screenshots
        print("Extracting individual screenshots...")
        try:
            # Pass the task to extract screenshot info from it
            save_screenshots_from_history(history, screenshot_dir, task)
            
            # Try to create GIF manually if automatic creation failed
            try:
                # Check if session.gif exists
                if not os.path.exists(f"{screenshot_dir}/session.gif"):
                    print("Automatic GIF creation failed. Creating GIF manually...")
                    try:
                        from browser_use.agent.gif import create_history_gif
                        # Let's create it manually
                        create_history_gif(
                            task=task,
                            history=history,
                            output_path=f"{screenshot_dir}/session.gif",
                            duration=2000,  # 2 seconds per frame
                            show_goals=True,
                            show_task=True,
                        )
                        print(f"Manual GIF created at {screenshot_dir}/session.gif")
                    except ImportError as e:
                        print(f"Could not create GIF: Missing dependency - {e}")
                        print("To enable GIF creation, install the required dependencies:")
                        print("pip install Pillow")
            except Exception as gif_ex:
                print(f"Manual GIF creation failed: {gif_ex}")
            
            # Record successful GIF creation in log
            if os.path.exists(f"{screenshot_dir}/session.gif"):
                print(f"✅ Session recording GIF created successfully")
            
            # Create and save a proper history.json file
            try:
                # Create a serializable representation of the history
                serializable_history = []
                screenshot_info = extract_screenshot_info_from_task(task)
                
                for i, item in enumerate(history.history):
                    if not hasattr(item, 'state') or not item.state:
                        continue
                        
                    # Get URL and title if available
                    url = item.state.url if hasattr(item.state, 'url') else ""
                    title = item.state.title if hasattr(item.state, 'title') else ""
                    
                    # Get model output and goal if available
                    goal = ""
                    if hasattr(item, "model_output") and item.model_output:
                        if hasattr(item.model_output, "current_state"):
                            if hasattr(item.model_output.current_state, "next_goal"):
                                goal = item.model_output.current_state.next_goal
                    
                    # Generate a clean description for the step
                    step_description = f"Step {i+1}"
                    
                    # Clean up the title for better display
                    clean_title = ""
                    if title:
                        # Extract the main part of the title (before any separator like | or -)
                        main_parts = title.split("|")[0].split("-")[0].strip()
                        # Remove any trailing region or instance information
                        clean_title = main_parts.split(" us-east")[0].strip()
                        if clean_title:
                            step_description = clean_title
                    
                    # Get filename used for this screenshot
                    if i < len(screenshot_info) and screenshot_info[i].get('filename'):
                        description = screenshot_info[i]['description'] or step_description
                        template_filename = screenshot_info[i]['filename']
                    else:
                        description = step_description
                        # Generate a descriptive name for step if no title but we have a goal
                        if not clean_title and goal:
                            # Use the first few words of the goal as description
                            description = ' '.join(goal.split()[:5])
                            if len(goal.split()) > 5:
                                description += "..."
                        
                        template_filename = None
                        
                    # Generate the actual filename that was used to save the screenshot
                    # This must match the logic in save_screenshots_from_history
                    if url:
                        domain_parts = url.replace("https://", "").replace("http://", "").split('/')
                        domain = domain_parts[0] if domain_parts else ""
                        domain = domain.replace("www.", "").split(':')[0]
                    else:
                        domain = "unknown"
                        
                    if template_filename:
                        # Use template filename but ensure it's valid
                        safe_filename = ''.join(c for c in template_filename if c.isalnum() or c in '._-')
                    elif title:
                        # Generate from title
                        clean_title = ''.join(c if c.isalnum() or c == ' ' else '_' for c in title)
                        clean_title = clean_title.strip().replace(' ', '_')[:20]
                        safe_filename = f"{domain}_{clean_title}_{i}.png"
                    else:
                        # Fallback to step number
                        safe_filename = f"{domain}_step_{i}.png"
                    
                    # Ensure filename is valid and not too long
                    safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c in '._-')
                    if len(safe_filename) > 80:
                        extension = safe_filename.split('.')[-1] if '.' in safe_filename else 'png'
                        safe_filename = safe_filename[:75] + '.' + extension
                    
                    # Create history entry
                    entry = {
                        "step": i,
                        "description": description,
                        "url": url,
                        "title": title,
                        "timestamp": datetime.now().isoformat(),
                        "screenshot_path": safe_filename,
                        "requested_filename": template_filename,
                        "goal": goal
                    }
                    
                    serializable_history.append(entry)
                
                # Write to file
                history_file = f"{screenshot_dir}/history.json"
                with open(history_file, 'w') as f:
                    json.dump(serializable_history, f, indent=2)
                print(f"Created detailed history file: {history_file}")
            except Exception as json_ex:
                print(f"Note: Couldn't save JSON history: {json_ex}")
        except Exception as ex:
            print(f"Error saving screenshots: {ex}")
        
    except Exception as e:
        print(f"Error during agent execution: {e}")
    
    finally:
        # Clean up
        await browser.close()
        print("Browser closed")

if __name__ == "__main__":
    # Run the demo
    asyncio.run(main()) 
