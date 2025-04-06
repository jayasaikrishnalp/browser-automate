"""
Markdown Report Generator for Browser Automation Tasks

This script generates beautiful markdown reports from browser automation task logs and screenshots.
It uses LangChain and Claude/GPT models to create comprehensive and well-formatted reports.
"""

import os
import json
import glob
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import base64
import re
from pathlib import Path

# Import LangChain components
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from langchain.tools import tool

# Load environment variables
load_dotenv()

# Determine which model to use based on environment variable
USE_ANTHROPIC = os.getenv("USE_ANTHROPIC", "false").lower() == "true"
TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))

# Initialize the appropriate model
if USE_ANTHROPIC:
    from langchain_anthropic import ChatAnthropic
    
    # Initialize Anthropic model
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
    
    llm = ChatAnthropic(
        model="claude-3-5-sonnet-latest",
        temperature=TEMPERATURE,
        anthropic_api_key=anthropic_api_key
    )
else:
    from langchain_openai import ChatOpenAI
    
    # Initialize OpenAI model
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY not found in environment variables")
    
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=TEMPERATURE,
        openai_api_key=openai_api_key
    )

# Get the react prompt from the hub
react_prompt = hub.pull("hwchase17/react")

# Define tools for the agent
@tool
def read_task_description(run_dir: str) -> str:
    """
    Read the task description from the task.txt file in the run directory.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: Task description
    """
    task_file = os.path.join(run_dir, "task.txt")
    if os.path.exists(task_file):
        with open(task_file, "r") as f:
            return f.read()
    return "Task description not available"

@tool
def read_execution_log(run_dir: str) -> str:
    """
    Read the execution log from the execution.log file in the run directory.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: Execution log content
    """
    log_file = os.path.join(run_dir, "execution.log")
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            return f.read()
    return "Execution log not available"

@tool
def get_screenshots_info(run_dir: str) -> str:
    """
    Get information about all screenshots in the run directory.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: JSON string with information about screenshots
    """
    screenshots = []
    for file in os.listdir(run_dir):
        if file.endswith((".png", ".jpg", ".jpeg", ".gif")):
            file_path = os.path.join(run_dir, file)
            file_size = os.path.getsize(file_path)
            screenshots.append({
                "filename": file,
                "path": file_path,
                "size_bytes": file_size
            })
    return json.dumps(screenshots, indent=2)

@tool
def read_history_json(run_dir: str) -> str:
    """
    Read the history.json file in the run directory.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: JSON string with history information
    """
    history_file = os.path.join(run_dir, "history.json")
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return f.read()
    return "{}"

@tool
def get_run_timestamp(run_dir: str) -> str:
    """
    Extract the timestamp from the run directory name.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: Formatted timestamp
    """
    dir_name = os.path.basename(run_dir)
    match = re.search(r'run_(\d{8})_(\d{6})', dir_name)
    if match:
        date_str = match.group(1)
        time_str = match.group(2)
        try:
            date = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
            return date.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    return "Unknown timestamp"

@tool
def generate_markdown_report(run_dir: str) -> str:
    """
    Generate a beautiful markdown report for the automation run.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: Markdown report content
    """
    # Get all the required information
    task_description = read_task_description(run_dir)
    execution_log = read_execution_log(run_dir)
    screenshots_info = get_screenshots_info(run_dir)
    history_json = read_history_json(run_dir)
    timestamp = get_run_timestamp(run_dir)
    
    # Parse JSON inputs
    try:
        screenshots = json.loads(screenshots_info)
        history = json.loads(history_json)
    except json.JSONDecodeError:
        screenshots = []
        history = {}
    
    # Create a relative path for images that will work in markdown
    run_name = os.path.basename(run_dir)
    
    # Start building the markdown
    markdown = f"""# Browser Automation Task Report

## Task Information
- **Timestamp**: {timestamp}
- **Run ID**: {run_name}

## Task Description
```
{task_description}
```

## Execution Summary
"""
    
    # Add history summary if available
    if history and "steps" in history:
        markdown += "\n### Steps Performed\n\n"
        for i, step in enumerate(history.get("steps", []), 1):
            action = step.get("action", "Unknown action")
            status = step.get("status", "Unknown status")
            markdown += f"{i}. **{action}** - {status}\n"
    
    # Add screenshots section
    if screenshots:
        markdown += "\n## Screenshots\n\n"
        for i, screenshot in enumerate(screenshots, 1):
            filename = screenshot.get("filename", "unknown.png")
            if filename == "session.gif":
                markdown += f"\n### Session Recording\n\n"
                markdown += f"![Session Recording](../agent_screenshots/{run_name}/{filename})\n\n"
            elif "png" in filename or "jpg" in filename or "jpeg" in filename:
                markdown += f"\n### Screenshot: {filename}\n\n"
                markdown += f"![{filename}](../agent_screenshots/{run_name}/{filename})\n\n"
    
    # Add execution log section (truncated if too long)
    markdown += "\n## Execution Log\n\n```\n"
    if len(execution_log) > 2000:
        markdown += execution_log[:1000] + "\n...\n" + execution_log[-1000:]
    else:
        markdown += execution_log
    markdown += "\n```\n"
    
    return markdown

@tool
def save_markdown_report(markdown_data: dict) -> str:
    """
    Save the markdown report to a file.
    
    Args:
        markdown_data: Dictionary containing run_dir and markdown_content
        
    Returns:
        str: Path to the saved markdown file
    """
    run_dir = markdown_data.get("run_dir", "")
    markdown_content = markdown_data.get("markdown_content", "")
    
    if not run_dir or not markdown_content:
        return "Error: Missing run_dir or markdown_content"
    
    run_name = os.path.basename(run_dir)
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(run_dir)), "reports")
    
    # Create reports directory if it doesn't exist
    os.makedirs(reports_dir, exist_ok=True)
    
    # Save the markdown file
    report_path = os.path.join(reports_dir, f"{run_name}_report.md")
    with open(report_path, "w") as f:
        f.write(markdown_content)
    
    return f"Report saved to {report_path}"

@tool
def list_run_directories() -> str:
    """
    List all run directories in the agent_screenshots folder.
    
    Returns:
        str: JSON string with run directories information
    """
    base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_screenshots")
    run_dirs = []
    
    if os.path.exists(base_dir):
        for dir_name in os.listdir(base_dir):
            dir_path = os.path.join(base_dir, dir_name)
            if os.path.isdir(dir_path) and dir_name.startswith("run_"):
                run_dirs.append({
                    "name": dir_name,
                    "path": dir_path,
                    "timestamp": get_run_timestamp(dir_path)
                })
    
    return json.dumps(run_dirs, indent=2)

# Create the tools list
tools = [
    read_task_description,
    read_execution_log,
    get_screenshots_info,
    read_history_json,
    get_run_timestamp,
    generate_markdown_report,
    save_markdown_report,
    list_run_directories
]

# Create the agent
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=react_prompt
)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)

def generate_report_for_run(run_dir: str) -> str:
    """
    Generate a markdown report for a specific run directory.
    
    Args:
        run_dir: Path to the run directory
        
    Returns:
        str: Path to the generated report
    """
    try:
        # Generate markdown report directly without using the agent
        # This avoids issues with complex tool calling
        task_description = read_task_description(run_dir)
        execution_log = read_execution_log(run_dir)
        screenshots_info = get_screenshots_info(run_dir)
        history_json = read_history_json(run_dir)
        timestamp = get_run_timestamp(run_dir)
        
        # Parse JSON inputs
        try:
            screenshots = json.loads(screenshots_info)
            history = json.loads(history_json)
        except json.JSONDecodeError:
            screenshots = []
            history = {}
        
        # Create a relative path for images that will work in markdown
        run_name = os.path.basename(run_dir)
        
        # Extract task title from description
        task_lines = task_description.strip().split('\n')
        task_title = "Browser Automation Task"
        if len(task_lines) > 0:
            # Try to create a meaningful title from the first line
            first_line = task_lines[0].strip()
            if "browser automation" in first_line.lower() or "google" in first_line.lower():
                task_title = "Browser Automation: Researching AI-Powered Browser Automation"
        
        # Start building the markdown
        markdown = f"""# {task_title}

## Overview
This tutorial demonstrates how to use browser automation to research information about AI-powered browser automation tools. Follow along with the step-by-step guide below.

## Tutorial Steps
"""
        
        # Parse the task description to extract steps
        steps = []
        current_step = ""
        current_screenshot = ""
        
        for line in task_lines:
            line = line.strip()
            if line.startswith('[SCREENSHOT:'):
                # Extract screenshot name
                screenshot_match = re.search(r'\[SCREENSHOT: (.*?) - (.*?)\]', line)
                if screenshot_match:
                    current_screenshot = screenshot_match.group(2)
            elif line and not line.startswith('['):
                # This is a step description
                if current_step:
                    steps.append((current_step, current_screenshot))
                current_step = line
                current_screenshot = ""
        
        # Add the last step if there is one
        if current_step:
            steps.append((current_step, current_screenshot))
        
        # Find matching screenshots for each step
        step_screenshots = {}
        for filename in [s.get("filename") for s in screenshots if s.get("filename") != "session.gif"]:
            for i, (step, screenshot) in enumerate(steps):
                # Try to match screenshot to step
                if screenshot and screenshot.lower() in filename.lower():
                    step_screenshots[i] = filename
                    break
                # For steps without explicit screenshot matches
                elif i not in step_screenshots:
                    keywords = step.lower().split()
                    for keyword in keywords:
                        if len(keyword) > 3 and keyword in filename.lower():
                            step_screenshots[i] = filename
                            break
        
        # Add detailed step-by-step tutorial with screenshots
        for i, (step, _) in enumerate(steps):
            step_num = i + 1
            markdown += f"\n### Step {step_num}: {step}\n\n"
            
            # Add detailed description based on the step
            if "navigate to google" in step.lower():
                markdown += "Open your browser and navigate to Google's homepage. This is the starting point for our research.\n\n"
            elif "search for" in step.lower():
                search_term = re.search(r'"(.+?)"', step)
                if search_term:
                    markdown += f"In the Google search box, type **\"{search_term.group(1)}\"** and press Enter. This will return the most relevant results about AI-powered browser automation tools and techniques.\n\n"
            elif "click" in step.lower():
                markdown += "Review the search results and click on a relevant article that provides comprehensive information about browser automation using AI. Look for articles from reputable sources like Hugging Face, GitHub, or technical blogs.\n\n"
            elif "scroll" in step.lower():
                markdown += "Once the article is open, scroll down to read more content. Pay attention to sections about implementation details, benefits, and use cases of AI-powered browser automation.\n\n"
            else:
                markdown += f"Complete the action: {step}\n\n"
            
            # Add the corresponding screenshot if available
            if i in step_screenshots:
                filename = step_screenshots[i]
                markdown += f"![{step}](../agent_screenshots/{run_name}/{filename})\n\n"
        
        # Add session recording at the end
        markdown += "\n## Complete Session Recording\n\n"
        markdown += "The following GIF shows the entire automation session from start to finish:\n\n"
        markdown += f"![Complete Session Recording](../agent_screenshots/{run_name}/session.gif)\n\n"
        
        # Add execution log section (truncated if too long)
        markdown += "\n## Execution Log\n\n```\n"
        if len(execution_log) > 2000:
            markdown += execution_log[:1000] + "\n...\n" + execution_log[-1000:]
        else:
            markdown += execution_log
        markdown += "\n```\n"
        
        # Save the markdown report
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(run_dir)), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, f"{run_name}_report.md")
        
        with open(report_path, "w") as f:
            f.write(markdown)
        
        return f"Report successfully generated and saved to {report_path}"
    except Exception as e:
        return f"Error generating report: {str(e)}"

def generate_reports_for_all_runs() -> List[str]:
    """
    Generate markdown reports for all run directories.
    
    Returns:
        List[str]: List of paths to the generated reports
    """
    try:
        result = agent_executor.invoke({
            "input": "List all run directories, then generate a beautiful and comprehensive markdown report for each run. "
                    "Use the available tools to gather all necessary information and create well-formatted reports. "
                    "Make sure to include task description, execution log, screenshots, and any other relevant information for each run. "
                    "Save each report to a file and return the paths to all saved reports."
        })
        return result["output"]
    except Exception as e:
        return f"Error generating reports: {str(e)}"

def main():
    """Main function to parse arguments and generate reports."""
    parser = argparse.ArgumentParser(description="Generate markdown reports for browser automation runs")
    parser.add_argument("--run", help="Generate report for a specific run directory")
    parser.add_argument("--all", action="store_true", help="Generate reports for all runs")
    parser.add_argument("--latest", action="store_true", help="Generate report for the latest run")
    
    args = parser.parse_args()
    
    if args.run:
        run_dir = args.run
        if not os.path.isabs(run_dir):
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_screenshots")
            run_dir = os.path.join(base_dir, run_dir)
        
        if os.path.exists(run_dir) and os.path.isdir(run_dir):
            print(f"Generating report for run directory: {run_dir}")
            result = generate_report_for_run(run_dir)
            print(result)
        else:
            print(f"Run directory not found: {run_dir}")
    
    elif args.latest:
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_screenshots")
        run_dirs = glob.glob(os.path.join(base_dir, "run_*"))
        
        if run_dirs:
            latest_run = max(run_dirs, key=os.path.getctime)
            print(f"Generating report for latest run: {latest_run}")
            result = generate_report_for_run(latest_run)
            print(result)
        else:
            print("No run directories found")
    
    elif args.all:
        print("Generating reports for all runs")
        result = generate_reports_for_all_runs()
        print(result)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
