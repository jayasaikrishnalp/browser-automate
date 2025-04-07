import os
import re
import json
import copy
import argparse
from datetime import datetime

def load_template(template_path):
    """Load a template file"""
    with open(template_path, 'r') as f:
        return f.read()

def process_template(template, data):
    """Replace placeholders in the template with actual data"""
    result = template
    print(f"Processing template with {len(data)} data items")
    
    # Process steps section (loop) first
    steps_match = re.search(r'\{\{#STEPS\}\}(.*?)\{\{/STEPS\}\}', result, re.DOTALL)
    if steps_match and 'STEPS' in data and isinstance(data['STEPS'], list):
        print(f"Found STEPS section with {len(data['STEPS'])} steps")
        step_template = steps_match.group(1)
        steps_content = ""
        
        for i, step in enumerate(data['STEPS'], 1):
            step_content = step_template
            step_data = step.copy()
            step_data['STEP_NUMBER'] = str(i)
            
            print(f"Processing step {i} with keys: {list(step_data.keys())}")
            for key, value in step_data.items():
                if isinstance(value, str):
                    placeholder = "{{" + key + "}}"
                    if placeholder in step_content:
                        print(f"Replacing {placeholder} with value of length {len(value)}")
                        step_content = step_content.replace(placeholder, value)
                    else:
                        print(f"Warning: Placeholder {placeholder} not found in template")
            
            steps_content += step_content
        
        result = result.replace(steps_match.group(0), steps_content)
    else:
        print("No STEPS section found in template or no steps data available")
    
    # Replace simple placeholders
    for key, value in data.items():
        if isinstance(value, str):
            placeholder = "{{" + key + "}}"
            if placeholder in result:
                print(f"Replacing global placeholder {placeholder} with value of length {len(value)}")
                result = result.replace(placeholder, value)
            else:
                print(f"Warning: Global placeholder {placeholder} not found in template")
    
    return result

def generate_report_from_template(run_dir, template_path):
    """Generate a markdown report using a template"""
    print(f"Generating report from template for run_dir: {run_dir}")
    print(f"Using template: {template_path}")
    
    # Get run information
    run_name = os.path.basename(run_dir)
    print(f"Run name: {run_name}")
    
    # Read task description
    task_path = os.path.join(run_dir, "task.txt")
    task_description = ""
    if os.path.exists(task_path):
        with open(task_path, 'r') as f:
            task_description = f.read().strip()
        print(f"Found task description: {task_description[:100]}...")
    else:
        print(f"Task file not found at {task_path}")
    
    # Read execution log
    log_path = os.path.join(run_dir, "execution.log")
    execution_log = ""
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            execution_log = f.read()
    
    # Read screenshots info
    screenshots_path = os.path.join(run_dir, "screenshots.json")
    screenshots = []
    if os.path.exists(screenshots_path):
        with open(screenshots_path, 'r') as f:
            screenshots = json.loads(f.read())
    
    # Read history
    history_path = os.path.join(run_dir, "history.json")
    history = {}
    if os.path.exists(history_path):
        with open(history_path, 'r') as f:
            history = json.loads(f.read())
    
    # Get timestamp
    timestamp_path = os.path.join(run_dir, "timestamp.txt")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if os.path.exists(timestamp_path):
        with open(timestamp_path, 'r') as f:
            timestamp = f.read().strip()
    
    # Parse task description to extract steps
    task_lines = task_description.strip().split('\n')
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
    
    # First try to use history.json for more accurate screenshot mapping
    if history and isinstance(history, list):
        print(f"Using history.json for screenshot mapping with {len(history)} entries")
        # Sort history entries by step number to ensure correct order
        sorted_history = sorted(history, key=lambda x: x.get("step", 0) if isinstance(x.get("step"), int) else 0)
        
        # Create a mapping of steps to screenshots from history
        for i, (step, _) in enumerate(steps):
            if i < len(sorted_history) and sorted_history[i].get("screenshot_path"):
                screenshot_file = sorted_history[i].get("screenshot_path")
                # Make sure the file exists in the run directory
                if os.path.exists(os.path.join(run_dir, screenshot_file)):
                    step_screenshots[i] = screenshot_file
                    print(f"Matched step {i+1} with screenshot {screenshot_file} from history")
    
    # Fallback to the original matching logic if history didn't provide matches for all steps
    screenshot_files = [f for f in os.listdir(run_dir) if f.endswith(".png") and f != "session.gif"]
    # Sort screenshot files to ensure consistent order
    screenshot_files.sort()
    
    for i, (step, screenshot) in enumerate(steps):
        if i not in step_screenshots:  # Only process steps that don't have a screenshot yet
            # First try to match by explicit screenshot name
            for filename in screenshot_files:
                if screenshot and screenshot.lower() in filename.lower():
                    step_screenshots[i] = filename
                    print(f"Matched step {i+1} with screenshot {filename} using screenshot name")
                    break
            
            # If still no match, try keyword matching
            if i not in step_screenshots:
                for filename in screenshot_files:
                    keywords = step.lower().split()
                    for keyword in keywords:
                        if len(keyword) > 3 and keyword in filename.lower():
                            step_screenshots[i] = filename
                            print(f"Matched step {i+1} with screenshot {filename} using keyword {keyword}")
                            break
                    if i in step_screenshots:
                        break
            
            # If still no match and we have screenshots left, use the next available one
            if i not in step_screenshots and i < len(screenshot_files):
                step_screenshots[i] = screenshot_files[i]
                print(f"Assigned step {i+1} with screenshot {screenshot_files[i]} by position")
    
    # Prepare template data
    # Extract a title from the task description
    title = "Browser Automation Task"
    if task_description:
        # Try to extract a meaningful title from the task
        first_line = task_description.split('\n')[0].strip()
        if first_line and len(first_line) < 100:
            title = f"Browser Automation: {first_line}"
    
    # Create a meaningful overview
    overview = "This tutorial demonstrates how to use browser automation to complete a task. Follow along with the step-by-step guide below."
    if task_description:
        # Split the task description and get the first line
        first_line = task_description.split('\n')[0].lower()
        overview = "This tutorial demonstrates how to use browser automation to " + first_line + ". Follow along with the step-by-step guide below."
    
    template_data = {
        "TITLE": title,
        "OVERVIEW": overview,
        "DATE": timestamp,
        "SESSION_ID": run_name,
        "EXECUTION_LOG": execution_log,
        "SESSION_GIF_PATH": f"../agent_screenshots/{run_name}/session.gif",
        "STEPS": []
    }
    
    print(f"Created template data with title: {title}")
    
    # Print for debugging
    print(f"Template data before steps: {template_data}")
    
    # Add steps data
    for i, (step, _) in enumerate(steps):
        step_description = ""
        if "navigate to google" in step.lower():
            step_description = "Open your browser and navigate to Google's homepage. This is the starting point for our research."
        elif "search for" in step.lower():
            search_term = re.search(r'"(.+?)"', step)
            if search_term:
                term = search_term.group(1)
                step_description = "In the Google search box, type **\"" + term + "\"** and press Enter. This will return the most relevant results about AI-powered browser automation tools and techniques."
        elif "click" in step.lower():
            step_description = "Review the search results and click on a relevant article that provides comprehensive information about browser automation using AI. Look for articles from reputable sources like Hugging Face, GitHub, or technical blogs."
        elif "scroll" in step.lower():
            step_description = "Once the article is open, scroll down to read more content. Pay attention to sections about implementation details, benefits, and use cases of AI-powered browser automation."
        else:
            step_description = f"Complete the action: {step}"
        
        print(f"Processing step {i+1}: {step}")
        print(f"Step description: {step_description}")
        screenshot_path = ""
        if i in step_screenshots:
            # Check if the screenshot file actually exists
            actual_file_path = os.path.join(run_dir, step_screenshots[i])
            if os.path.exists(actual_file_path):
                # Use the correct path format for the web interface
                screenshot_path = f"/images/{run_name}/{step_screenshots[i]}"
            else:
                print(f"Warning: Screenshot file {actual_file_path} does not exist")
        
        template_data["STEPS"].append({
            "STEP_TITLE": step,
            "STEP_DESCRIPTION": step_description,
            "SCREENSHOT_PATH": screenshot_path
        })
    
    # Load and process template
    template = load_template(template_path)
    markdown = process_template(template, template_data)
    
    # Create a folder for the report and its images
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(run_dir)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    
    # Create a subfolder for this specific report's images
    report_images_dir = os.path.join(reports_dir, f"{run_name}_images")
    os.makedirs(report_images_dir, exist_ok=True)
    
    # Copy all screenshots to the report images folder
    print(f"Copying screenshots from {run_dir} to {report_images_dir}")
    
    # List all the screenshot files in the run directory
    screenshot_files = [f for f in os.listdir(run_dir) if f.endswith(".png") and f != "session.gif"]
    print(f"Found {len(screenshot_files)} screenshot files: {screenshot_files}")
    
    # Copy each screenshot file to the report images directory
    import shutil
    for filename in screenshot_files:
        source_path = os.path.join(run_dir, filename)
        dest_path = os.path.join(report_images_dir, filename)
        
        if os.path.exists(source_path):
            shutil.copy2(source_path, dest_path)
            print(f"Copied {filename} to {report_images_dir}")
    
    # Create a copy of template data for the downloadable version
    download_template_data = copy.deepcopy(template_data)
    
    # Update the paths in the template data
    for i, step_data in enumerate(template_data["STEPS"]):
        # Check if this step has a matched screenshot
        if i in step_screenshots:
            filename = step_screenshots[i]
            # Use the correct route for serving images in web version
            template_data["STEPS"][i]["SCREENSHOT_PATH"] = f"/get-image/{run_name}/{run_name}_images/{filename}"
            # Use relative paths for downloadable version
            download_template_data["STEPS"][i]["SCREENSHOT_PATH"] = f"./{filename}"
        # Fallback to ordered screenshots if no match found
        elif i < len(screenshot_files):
            filename = screenshot_files[i]
            # Use the correct route for serving images in web version
            template_data["STEPS"][i]["SCREENSHOT_PATH"] = f"/get-image/{run_name}/{run_name}_images/{filename}"
            # Use relative paths for downloadable version
            download_template_data["STEPS"][i]["SCREENSHOT_PATH"] = f"./{filename}"
    
    # Also copy the session.gif if it exists
    session_gif_source = os.path.join(run_dir, "session.gif")
    if os.path.exists(session_gif_source):
        session_gif_dest = os.path.join(report_images_dir, "session.gif")
        import shutil
        shutil.copy2(session_gif_source, session_gif_dest)
        # Web version path
        template_data["SESSION_GIF_PATH"] = f"/get-image/{run_name}/{run_name}_images/session.gif"
        # Downloadable version path
        download_template_data["SESSION_GIF_PATH"] = f"./session.gif"
    
    # Process the template with web paths
    markdown = process_template(template, template_data)
    
    # Save the markdown report with web paths
    report_path = os.path.join(reports_dir, f"{run_name}_report.md")
    with open(report_path, "w") as f:
        f.write(markdown)
    
    # Process the template with relative paths for downloading
    download_markdown = process_template(template, download_template_data)
    
    # Save the downloadable markdown report with relative paths
    download_report_path = os.path.join(report_images_dir, f"{run_name}_report.md")
    with open(download_report_path, "w") as f:
        f.write(download_markdown)
    
    return report_path

def main():
    parser = argparse.ArgumentParser(description="Generate markdown reports from templates")
    parser.add_argument("--run", help="Run directory to generate report for")
    parser.add_argument("--latest", action="store_true", help="Generate report for the latest run")
    parser.add_argument("--template", default="templates/tutorial_template.md", help="Template file to use")
    args = parser.parse_args()
    
    # Find run directory
    run_dir = args.run
    if args.latest:
        screenshots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agent_screenshots")
        if os.path.exists(screenshots_dir):
            runs = [os.path.join(screenshots_dir, d) for d in os.listdir(screenshots_dir) if os.path.isdir(os.path.join(screenshots_dir, d))]
            if runs:
                run_dir = max(runs, key=os.path.getmtime)
                print(f"Generating report for latest run: {run_dir}")
    
    if not run_dir:
        print("Error: No run directory specified")
        return
    
    # Find template file
    template_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(template_dir, args.template)
    if not os.path.exists(template_path):
        print(f"Error: Template file not found: {template_path}")
        return
    
    # Generate report
    try:
        report_path = generate_report_from_template(run_dir, template_path)
        print(f"Report successfully generated and saved to {report_path}")
    except Exception as e:
        print(f"Error generating report: {str(e)}")

if __name__ == "__main__":
    main()
