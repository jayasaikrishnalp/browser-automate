import os
import json
import argparse
from datetime import datetime
import shutil
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langchain_core.prompts import PromptTemplate
import re

def generate_step_description(step_data, language="english"):
    """Generate concise description for a step using LangChain (50-100 tokens)"""
    # Initialize the language model
    chat = ChatOpenAI(temperature=0.3, model="gpt-4o")
    
    # Create a prompt template for generating step descriptions
    prompt_template = """
    Create a very concise description (50-100 tokens only) for this browser automation step:
    
    Step Number: {step_number}
    Goal: {goal}
    Description: {description}
    URL: {url}
    Page Title: {title}
    
    Be extremely brief but include:
    - The main action performed
    - Any key result or outcome
    
    Use simple, direct language. Avoid unnecessary details.
    Keep your response to 1-2 short sentences maximum.
    
    Write your response ONLY in {language} language.
    """
    
    # Format the prompt with step data
    prompt = prompt_template.format(
        step_number=step_data.get("step", ""),
        goal=step_data.get("goal", ""),
        description=step_data.get("description", ""),
        url=step_data.get("url", ""),
        title=step_data.get("title", ""),
        language=language
    )
    
    # Get response from the language model
    response = chat.invoke([HumanMessage(content=prompt)])
    
    return response.content.strip()

def translate_title(title, language="english"):
    """Translate a title to the specified language"""
    if language.lower() == "english":
        return title
    
    # Initialize the language model
    chat = ChatOpenAI(temperature=0.3, model="gpt-4o")
    
    # Create a prompt for translation
    prompt = f"Translate the following title ONLY to {language}, preserving any formatting: {title}"
    
    # Get response from the language model
    response = chat.invoke([HumanMessage(content=prompt)])
    
    return response.content.strip()

def generate_markdown_from_history(run_dir, output_path=None, language="english"):
    """Generate a markdown report from history.json"""
    # Get run information
    run_name = os.path.basename(run_dir)
    
    # Read history.json
    history_path = os.path.join(run_dir, "history.json")
    if not os.path.exists(history_path):
        print(f"Error: history.json not found at {history_path}")
        return None
    
    with open(history_path, 'r') as f:
        history = json.loads(f.read())
    
    # Filter out step 0 if present
    history = [step for step in history if step.get("step", 0) != 0]
    
    # Sort history by step number
    history.sort(key=lambda x: x.get("step", 0))
    
    # Create report directory if needed
    reports_dir = os.path.join(os.path.dirname(run_dir), "reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir)
    
    # Create images directory for the report
    report_images_dir = os.path.join(reports_dir, f"{run_name}_images")
    if not os.path.exists(report_images_dir):
        os.makedirs(report_images_dir)
    
    # Copy screenshots to the report images directory
    for step_data in history:
        screenshot_path = step_data.get("screenshot_path", "")
        if screenshot_path and os.path.exists(os.path.join(run_dir, screenshot_path)):
            source_path = os.path.join(run_dir, screenshot_path)
            dest_path = os.path.join(report_images_dir, os.path.basename(screenshot_path))
            
            # Create destination directory if it doesn't exist
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Copy the file
            shutil.copy2(source_path, dest_path)
            
            # Update the screenshot path in the step data
            step_data["screenshot_path"] = os.path.basename(screenshot_path)
    
    # Generate markdown content
    markdown_content = f"# Browser Automation Report: {run_name}\n\n"
    markdown_content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # Add each step to the markdown
    for step_data in history:
        # Get step information
        step_num = step_data.get("step", "")
        goal = step_data.get("goal", "")
        screenshot_path = step_data.get("screenshot_path", "")
        
        # Skip if no goal is provided
        if not goal:
            continue
        
        # Translate the title if needed
        title = translate_title(goal, language)
        
        # Add step heading
        markdown_content += f"# {title}\n\n"
        
        # Generate and add detailed description
        description = generate_step_description(step_data, language)
        markdown_content += f"{description}\n\n"
        
        # Add screenshot
        if screenshot_path:
            # For web viewing in the browser UI - use the get-image endpoint
            web_path = f"/get-image/{run_name}/{os.path.basename(screenshot_path)}"
            # For viewing in the downloaded markdown file (relative path)
            file_path = f"./{os.path.basename(screenshot_path)}"
            
            # Use web_path for the UI and file_path for the downloaded markdown
            # We'll use a special comment that will be replaced when downloading
            markdown_content += f"![Step {step_num} Screenshot]({web_path})<!-- LOCAL_PATH:{file_path} -->\n\n"
        else:
            markdown_content += "[No screenshot available]\n\n"
    
    # Determine output path
    if not output_path:
        lang_suffix = "" if language.lower() == "english" else f"_{language.lower()}"
        output_path = os.path.join(reports_dir, f"{run_name}{lang_suffix}_history_report.md")
    
    # Save markdown to file
    with open(output_path, "w") as f:
        f.write(markdown_content)
    
    # Create downloadable version with relative paths
    download_markdown = markdown_content
    # Replace web paths with relative paths for downloadable version
    download_markdown = re.sub(
        r'!\[Step \d+ Screenshot\]\([^/]+_images/([^\)]+)\)',
        r'![Step Screenshot](./\1)',
        download_markdown
    )
    
    # Save downloadable version
    download_path = os.path.join(report_images_dir, f"{run_name}{'' if language.lower() == 'english' else f'_{language.lower()}'}_history_report.md")
    with open(download_path, "w") as f:
        f.write(download_markdown)
    
    print(f"Markdown report generated at {output_path}")
    print(f"Downloadable version saved at {download_path}")
    
    return output_path

def main():
    parser = argparse.ArgumentParser(description="Generate markdown reports from history.json")
    parser.add_argument("--run", help="Run directory to generate report for")
    parser.add_argument("--output", help="Output file path for the report")
    parser.add_argument("--language", default="english", help="Language for the report (default: english)")
    args = parser.parse_args()
    
    # Find run directory
    run_dir = args.run
    if not run_dir or not os.path.exists(run_dir):
        print("Error: Please provide a valid run directory")
        return
    
    # Generate report
    try:
        report_path = generate_markdown_from_history(run_dir, args.output, args.language)
        if report_path:
            print(f"Report successfully generated and saved to {report_path}")
    except Exception as e:
        print(f"Error generating report: {str(e)}")

if __name__ == "__main__":
    main()
