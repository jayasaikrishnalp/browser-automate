from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
import re
from dotenv import load_dotenv
import asyncio
import zipfile
import io
import shutil

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    print("Warning: .env file not found. Using default environment variables.")

# Get configuration from environment variables
PORT = int(os.getenv("PORT", 8000))
HOST = os.getenv("HOST", "0.0.0.0")
SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", "agent_screenshots")
DEFAULT_CHROME_PATH = os.getenv("DEFAULT_CHROME_PATH", "")

# Set platform-specific default Chrome path if not set
if not DEFAULT_CHROME_PATH:
    import platform
    system = platform.system()
    if system == "Darwin":  # macOS
        DEFAULT_CHROME_PATH = os.getenv("CHROME_PATH_MACOS", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    elif system == "Windows":
        DEFAULT_CHROME_PATH = os.getenv("CHROME_PATH_WINDOWS", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
    elif system == "Linux":
        DEFAULT_CHROME_PATH = os.getenv("CHROME_PATH_LINUX", "/usr/bin/google-chrome")

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files to serve the HTML interface
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_root():
    return FileResponse("static/index.html")

@app.get("/stream-logs/{screenshot_dir}")
async def stream_logs(screenshot_dir: str):
    """Stream logs from the agent execution in real-time."""
    
    # Function to generate log stream
    async def log_generator():
        # Make sure we have the correct full path
        if os.path.basename(screenshot_dir) == screenshot_dir:
            # If it's just a directory name, assume it's in web-ui/agent_screenshots
            current_dir = os.path.dirname(os.path.abspath(__file__))
            log_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/execution.log")
        else:
            log_file = f"{screenshot_dir}/execution.log"
        
        # Create the log file if it doesn't exist
        if not os.path.exists(os.path.dirname(log_file)):
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        if not os.path.exists(log_file):
            with open(log_file, "w") as f:
                f.write("")
        
        # Keep track of the current file position
        position = 0
        
        # Flag to check if process is still alive
        process_completed = False
        no_new_content_count = 0
        max_no_content_checks = 10  # Check 10 times before assuming completion if no new content
        
        while True:
            try:
                with open(log_file, "r") as f:
                    # Get file size to check if there's anything new
                    f.seek(0, os.SEEK_END)
                    file_size = f.tell()
                    
                    if file_size > position:
                        # New content available
                        f.seek(position)
                        new_content = f.read()
                        if new_content:
                            position = f.tell()
                            yield f"data: {json.dumps({'log': new_content})}\n\n"
                            no_new_content_count = 0  # Reset counter since we got content
                    else:
                        # No new content
                        no_new_content_count += 1
                    
                    # Check if execution is complete
                    completion_markers = ["Task completed", "Browser closed", "✅ Task completed"]
                    if process_completed:
                        yield f"data: {json.dumps({'status': 'completed'})}\n\n"
                        break
                    
                    # Check for completion markers
                    with open(log_file, "r") as check_file:
                        log_content = check_file.read()
                        if any(marker in log_content for marker in completion_markers):
                            process_completed = True
                    
                    # Check for history file to determine if execution is done
                    history_file = os.path.join(os.path.dirname(log_file), "history.json")
                    if os.path.exists(history_file):
                        try:
                            with open(history_file, "r") as hf:
                                history = json.load(hf)
                                # If history exists and is valid, process is likely complete
                                if isinstance(history, list) and len(history) > 0:
                                    process_completed = True
                        except json.JSONDecodeError:
                            # History file might be still being written, continue waiting
                            pass
                    
                    # If we've checked several times with no new content and a substantial log exists,
                    # assume the process might be complete
                    if no_new_content_count >= max_no_content_checks and file_size > 100:
                        # Do a final check of the agent process
                        process_dir = os.path.dirname(log_file)
                        pid_file = os.path.join(process_dir, "agent_pid.txt")
                        if os.path.exists(pid_file):
                            try:
                                with open(pid_file, "r") as pf:
                                    pid = int(pf.read().strip())
                                    # Check if process is still running
                                    try:
                                        os.kill(pid, 0)  # Signal 0 doesn't kill but checks existence
                                    except OSError:
                                        # Process is not running
                                        process_completed = True
                            except (ValueError, FileNotFoundError):
                                # If we can't read the PID or file is gone, assume completion
                                process_completed = True
                        else:
                            process_completed = True
            except Exception as e:
                print(f"Error reading log file: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                await asyncio.sleep(1)  # Wait a bit longer on error
                continue
            
            await asyncio.sleep(0.5)
    
    return StreamingResponse(log_generator(), media_type="text/event-stream")

@app.get("/get-step-screenshots/{screenshot_dir}")
async def get_step_screenshots(screenshot_dir: str):
    """Get all step screenshots organized by step number."""
    # Handle the case where screenshot_dir might be a full path or just the directory name
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        screenshot_path = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}")
    else:
        screenshot_path = screenshot_dir
    
    if not os.path.exists(screenshot_path):
        return JSONResponse({"error": "Screenshot directory not found"}, status_code=404)
    
    # Get all image files in the directory
    image_files = [f for f in os.listdir(screenshot_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
    
    # Read history file to match screenshots with steps if available
    history_file = os.path.join(screenshot_path, "history.json")
    
    steps_array = []
    
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            history_data = json.load(f)
            
        # Process history data into an array format
        for i, item in enumerate(history_data):
            # Skip about:blank or empty pages
            url = item.get("url", "")
            title = item.get("title", "")
            if url == "about:blank" or (not url and not title):
                continue
                
            if "screenshot_path" in item and item["screenshot_path"] in image_files:
                step_num = i  # 0-indexed for the array
                
                # Get description and goal if available
                description = item.get("description", f"Step {step_num+1}")
                goal = item.get("goal", "")
                
                # For AWS login page, enhance the description 
                if "aws.amazon.com" in url and "signin" in url.lower():
                    if "Web Services Sign" in title:
                        # This appears to be an AWS sign-in page - modify the description
                        description = "Amazon Web Services Sign"
                
                # For EC2 dashboard, handle similarly
                if "console.aws.amazon.com/ec2" in url and "Dashboard" in title:
                    description = "Dashboard | EC2"
                
                steps_array.append({
                    "screenshot_path": item["screenshot_path"],
                    "url": url,
                    "title": title,
                    "description": description,
                    "goal": goal,
                    "step": step_num
                })
    else:
        # If no history file, try to organize by filenames
        for idx, image in enumerate(sorted(image_files)):
            # Skip images with "about_blank" or similar in their filename
            if "about_blank" in image.lower() or "about:blank" in image.lower():
                continue
                
            # Try to extract step number from filename
            match = re.search(r'step_?(\d+)', image.lower())
            if match:
                step_num = int(match.group(1)) - 1  # Convert to 0-indexed
            else:
                # If no step number, use position in sorted list
                step_num = idx
            
            # Try to infer description from filename
            description = f"Step {step_num+1}"
            if "signin.aws" in image or "amazon" in image.lower() and "sign" in image.lower():
                description = "Amazon Web Services Sign"
            elif "ec2" in image.lower() and "dashboard" in image.lower():
                description = "Dashboard | EC2"
            
            steps_array.append({
                "screenshot_path": image,
                "url": "",
                "title": "",
                "description": description,
                "goal": "",
                "step": step_num
            })
    
    # Sort the steps by step number
    steps_array.sort(key=lambda x: x["step"])
    
    return {"steps": steps_array}

@app.post("/run-task/")
async def run_task(
    task: str = Form(...), 
    highlight_elements: bool = Form(True),
    headless_mode: bool = Form(False),
    use_local_browser: bool = Form(False),
    chrome_path: str = Form(None)
):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create screenshot directory directly in web-ui folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    screenshot_dir = os.path.join(current_dir, f"{SCREENSHOTS_DIR}/run_{timestamp}")
    os.makedirs(screenshot_dir, exist_ok=True)
    
    print(f"Creating screenshot directory: {screenshot_dir}")
    print(f"Highlight elements setting: {highlight_elements}")
    print(f"Headless mode setting: {headless_mode}")
    print(f"Use local browser setting: {use_local_browser}")
    
    # Use provided Chrome path or fall back to default
    effective_chrome_path = chrome_path or DEFAULT_CHROME_PATH
    if effective_chrome_path:
        print(f"Using Chrome path: {effective_chrome_path}")
        if not os.path.exists(effective_chrome_path):
            print(f"Warning: Chrome executable not found at {effective_chrome_path}")

    # Save task to a temporary file
    task_file = os.path.join(screenshot_dir, "task.txt")
    with open(task_file, "w") as f:
        f.write(task)
    
    # Create a log file
    log_file = os.path.join(screenshot_dir, "execution.log")
    with open(log_file, "w") as f:
        f.write(f"Starting task execution at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Get the absolute path to agent_working.py
    agent_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_working.py")
    
    # Run the agent script as a subprocess
    env_vars = {
        **os.environ, 
        "TASK_FILE": task_file, 
        "SCREENSHOT_DIR": screenshot_dir,
        "HIGHLIGHT_ELEMENTS": str(highlight_elements),
        "HEADLESS_MODE": str(headless_mode),
        "USE_LOCAL_BROWSER": str(use_local_browser),
        "LOG_FILE": log_file,
        # Set browser-use specific environment variables
        "BROWSER_USE_LOGGING_LEVEL": "info",  # Ensure we get adequate logging without overwhelming
        "PYTHONUNBUFFERED": "1"  # Ensure logs are written immediately
    }
    
    # Add Chrome path to environment variables
    if effective_chrome_path:
        env_vars["CHROME_PATH"] = effective_chrome_path
    
    # Run the agent script as a subprocess with redirected output
    process = subprocess.Popen(
        ["python", agent_script], 
        env=env_vars,
        stdout=open(log_file, "a"),
        stderr=subprocess.STDOUT,
        bufsize=0  # No buffering to ensure logs are written immediately
    )
    
    # Save the process ID for monitoring
    with open(os.path.join(screenshot_dir, "agent_pid.txt"), "w") as f:
        f.write(str(process.pid))

    return {"message": "Task started", "screenshot_dir": screenshot_dir}

@app.get("/generate-markdown/{screenshot_dir}")
async def generate_markdown(screenshot_dir: str, language: str = "english"):
    """Generate a markdown file from the history.json file using template processor or history_markdown_generator"""
    # Handle relative paths
    if os.path.basename(screenshot_dir) == screenshot_dir:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_screenshot_dir = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}")
    else:
        full_screenshot_dir = screenshot_dir
    
    history_file = os.path.join(full_screenshot_dir, "history.json")
    if not os.path.exists(history_file):
        return JSONResponse({"error": "History file not found"}, status_code=404)
    
    # Check if a report in the requested language already exists
    run_name = os.path.basename(full_screenshot_dir)
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_screenshots/reports")
    lang_suffix = "" if language.lower() == "english" else f"_{language.lower()}"
    existing_report = os.path.join(reports_dir, f"{run_name}{lang_suffix}_history_report.md")
    
    if os.path.exists(existing_report):
        # Use the existing report
        with open(existing_report, "r") as f:
            markdown_content = f.read()
        
        return {
            "status": "success", 
            "markdown_file": existing_report,
            "content": markdown_content
        }
    
    try:
        # Import the history markdown generator module
        import sys
        import importlib
        langchain_agent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "langchain_agent")
        sys.path.append(langchain_agent_path)
        
        # Try to use history_markdown_generator first
        try:
            # Force reload the module to ensure we get the latest version
            if "history_markdown_generator" in sys.modules:
                importlib.reload(sys.modules["history_markdown_generator"])
            from history_markdown_generator import generate_markdown_from_history
            
            # Generate the report using the history markdown generator
            report_path = generate_markdown_from_history(full_screenshot_dir, None, language)
            
            # Read the generated report
            with open(report_path, "r") as f:
                markdown_content = f.read()
            
            # Also save a copy in the screenshot directory
            markdown_file = os.path.join(full_screenshot_dir, f"report{lang_suffix}.md")
            with open(markdown_file, "w") as f:
                f.write(markdown_content)
            
            return {
                "status": "success", 
                "markdown_file": markdown_file,
                "content": markdown_content
            }
        except Exception as e:
            print(f"Error using history markdown generator: {e}")
            print("Falling back to template processor")
            
            # Force reload the module to ensure we get the latest version
            if "template_processor" in sys.modules:
                importlib.reload(sys.modules["template_processor"])
            from template_processor import generate_report_from_template
            
            # Get the template path
            template_path = os.path.join(langchain_agent_path, "templates", "tutorial_template.md")
            
            # Generate the report using the template processor
            report_path = generate_report_from_template(full_screenshot_dir, template_path)
            
            # Read the generated report
            with open(report_path, "r") as f:
                markdown_content = f.read()
            
            # Also save a copy in the screenshot directory
            markdown_file = os.path.join(full_screenshot_dir, "report.md")
            with open(markdown_file, "w") as f:
                f.write(markdown_content)
            
            return {
                "status": "success", 
                "markdown_file": markdown_file,
                "content": markdown_content
            }
    except Exception as e:
        # Fallback to the original method if template processing fails
        print(f"Error using template processor: {e}")
        print("Falling back to default markdown generation")
        
        # Load history
        with open(history_file, "r") as f:
            history = json.load(f)
        
        # Create markdown content
        markdown_content = f"# Browser Automation Task Report\n\n"
        markdown_content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Extract task description
        task_file = os.path.join(full_screenshot_dir, "task.txt")
        if os.path.exists(task_file):
            with open(task_file, "r") as f:
                task_text = f.read()
            markdown_content += f"## Task Description\n\n```\n{task_text}\n```\n\n"
        
        # Process each step in history
        markdown_content += f"## Steps Executed\n\n"
        
        for item in history:
            step_num = item["step"] + 1
            description = item.get("description", f"Step {step_num}")
            url = item.get("url", "")
            title = item.get("title", "")
            screenshot_path = item.get("screenshot_path", "")
            requested_filename = item.get("requested_filename", "")
            goal = item.get("goal", "")
            
            # Check if this page should have URL/title hidden
            should_skip_url_title = (
                ("aws.amazon.com" in url and "signin" in url.lower()) or
                ("console.aws.amazon.com/ec2" in url and "Dashboard" in title) or
                ("Web Services Sign" in title) or
                (description and "Amazon Web Services Sign" in description) or
                (description and "Dashboard | EC2" in description)
            )
            
            # Combine step number, description, and goal in a single line
            header_text = f"### Step {step_num}: {description}"
            if goal:
                header_text += f" - Goal: {goal}"
            markdown_content += f"{header_text}\n\n"
            
            # Only include URL and title if not in the skip list
            if url and not should_skip_url_title:
                markdown_content += f"**URL:** [{url}]({url})\n\n"
            
            if title and title != description and not should_skip_url_title:
                markdown_content += f"**Page Title:** {title}\n\n"
            
            if screenshot_path:
                # Fix image path for markdown - use the actual screenshot filename from history.json
                dir_name = os.path.basename(full_screenshot_dir)
                
                # Create a more reliable markdown image reference
                # Use the filename as the alt text if no description
                img_alt = description or os.path.basename(screenshot_path)
                markdown_content += f"![{img_alt}](/images/{dir_name}/{screenshot_path})\n\n"
                
                # Show filename information (simplified to reduce clutter)
                if requested_filename and requested_filename != screenshot_path:
                    markdown_content += f"*Requested filename: `{requested_filename}`*\n\n"
                    markdown_content += f"*Actual filename: `{screenshot_path}`*\n\n"
                else:
                    markdown_content += f"*Filename: `{screenshot_path}`*\n\n"
        
        # Add results section if final step has a result
        if history and "goal" in history[-1] and history[-1]["goal"].lower().startswith("complete"):
            markdown_content += f"## Results\n\n"
            markdown_content += f"Task completed successfully.\n\n"
        
        # Add a summary of screenshot mapping
        markdown_content += f"## Screenshot Summary\n\n"
        
        # Create a cleaner table format
        markdown_content += f"| Step | Description | Actual Filename |\n"
        markdown_content += f"|:----:|-------------|----------------|\n"
        
        for item in history:
            if not item.get("screenshot_path"):
                continue
                
            step_num = item["step"] + 1
            description = item.get("description", f"Step {step_num}")
            # Truncate description if too long to avoid breaking the table
            if len(description) > 40:
                description = description[:37] + "..."
            
            actual = item.get("screenshot_path", "-")
            
            markdown_content += f"| {step_num} | {description} | `{actual}` |\n"
        
        # Save markdown file
        markdown_file = os.path.join(full_screenshot_dir, "report.md")
        with open(markdown_file, "w") as f:
            f.write(markdown_content)
        
        return {
            "status": "success", 
            "markdown_file": markdown_file,
            "content": markdown_content
        }

@app.get("/get-results/{screenshot_dir}")
async def get_results(screenshot_dir: str):
    # Handle the case where screenshot_dir might be a full path or just the directory name
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        history_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/history.json")
    else:
        # If it's a full path, use it directly
        history_file = f"{screenshot_dir}/history.json"
    
    print(f"Looking for history file at: {history_file}")
    
    if not os.path.exists(history_file):
        return JSONResponse({"status": "processing"}, status_code=202)

    with open(history_file, "r") as f:
        history = json.load(f)
    
    # Generate markdown report when results are ready
    try:
        markdown_result = await generate_markdown(screenshot_dir)
        markdown_content = markdown_result.get("content", "")
    except Exception as e:
        print(f"Error generating markdown: {e}")
        markdown_content = ""

    return {
        "status": "completed", 
        "history": history,
        "markdown": markdown_content
    }

@app.get("/images/{screenshot_dir}/{image_name}")
async def get_image(screenshot_dir: str, image_name: str):
    # Similar path handling as get_results
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/{image_name}")
    else:
        image_path = f"{screenshot_dir}/{image_name}"
    
    if not os.path.exists(image_path):
        return JSONResponse({"error": "Image not found"}, status_code=404)
        
    return FileResponse(image_path)

@app.get("/get-image/{screenshot_dir}/{image_folder}/{image_name}")
async def get_report_image(screenshot_dir: str, image_folder: str, image_name: str):
    """Serve images from the reports folder"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    image_path = os.path.join(current_dir, f"reports/{image_folder}/{image_name}")
    
    if not os.path.exists(image_path):
        print(f"Image not found: {image_path}")
        return JSONResponse({"error": "Image not found"}, status_code=404)
        
    return FileResponse(image_path)

@app.get("/get-image/{screenshot_dir}/{image_name}")
async def get_screenshot_image(screenshot_dir: str, image_name: str):
    """Serve images directly from the screenshots folder"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try to find the image in several possible locations
    possible_paths = [
        # In the screenshots directory
        os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/{image_name}"),
        # In the reports images directory
        os.path.join(current_dir, f"agent_screenshots/reports/{screenshot_dir}_images/{image_name}"),
        # In the root of reports images directory
        os.path.join(current_dir, f"agent_screenshots/reports/{screenshot_dir}_images", image_name)
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
    
    # If image not found in any location
    print(f"Image not found: {image_name} for {screenshot_dir}")
    print(f"Tried paths: {possible_paths}")
    return JSONResponse({"error": "Image not found"}, status_code=404)

@app.get("/download-logs/{screenshot_dir}")
async def download_logs(screenshot_dir: str):
    """Download execution logs as a text file."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/execution.log")
    else:
        log_file = f"{screenshot_dir}/execution.log"
    
    if not os.path.exists(log_file):
        return JSONResponse({"error": "Log file not found"}, status_code=404)
    
    return FileResponse(log_file, media_type="text/plain", filename=f"{screenshot_dir}_logs.txt")

@app.get("/download-gif/{screenshot_dir}")
async def download_gif(screenshot_dir: str):
    """Download session recording GIF."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gif_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/session.gif")
    else:
        gif_file = f"{screenshot_dir}/session.gif"
    
    if not os.path.exists(gif_file):
        return JSONResponse({"error": "GIF recording not found"}, status_code=404)
    
    return FileResponse(gif_file, media_type="image/gif", filename=f"{screenshot_dir}_recording.gif")

@app.get("/download-screenshots/{screenshot_dir}")
async def download_screenshots(screenshot_dir: str):
    """Download all screenshots as a ZIP file."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        screenshots_dir = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}")
    else:
        screenshots_dir = screenshot_dir
    
    if not os.path.exists(screenshots_dir):
        return JSONResponse({"error": "Screenshots directory not found"}, status_code=404)
    
    # Create a BytesIO object to store the ZIP file
    zip_io = io.BytesIO()
    
    # Create a ZIP file
    with zipfile.ZipFile(zip_io, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
        # Get all image files in the directory
        image_files = [f for f in os.listdir(screenshots_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
        
        # Add each image to the ZIP file
        for image_file in image_files:
            image_path = os.path.join(screenshots_dir, image_file)
            zip_file.write(image_path, arcname=image_file)
            
        # Also add history.json if it exists
        history_file = os.path.join(screenshots_dir, "history.json")
        if os.path.exists(history_file):
            zip_file.write(history_file, arcname="history.json")
            
        # Add task.txt if it exists
        task_file = os.path.join(screenshots_dir, "task.txt")
        if os.path.exists(task_file):
            zip_file.write(task_file, arcname="task.txt")
    
    # Reset the pointer to the beginning of the BytesIO object
    zip_io.seek(0)
    
    # Return the ZIP file
    return StreamingResponse(
        zip_io, 
        media_type="application/zip", 
        headers={"Content-Disposition": f"attachment; filename={screenshot_dir}_screenshots.zip"}
    )

@app.get("/check-gif/{screenshot_dir}")
async def check_gif(screenshot_dir: str):
    """Check if a GIF recording exists for the given run."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gif_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/session.gif")
    else:
        gif_file = f"{screenshot_dir}/session.gif"
    
    return {"exists": os.path.exists(gif_file)}

@app.get("/convert-gif-to-mp4/{screenshot_dir}")
async def convert_gif_to_mp4(screenshot_dir: str):
    """Convert session.gif to MP4 format with the same quality and subtitles."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gif_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/session.gif")
        output_dir = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}")
    else:
        gif_file = f"{screenshot_dir}/session.gif"
        output_dir = os.path.dirname(gif_file)
    
    if not os.path.exists(gif_file):
        return JSONResponse({"error": "GIF recording not found"}, status_code=404)
    
    # Output MP4 filename
    mp4_file = os.path.join(output_dir, "session.mp4")
    
    # Check if ffmpeg is installed
    try:
        # Try to run ffmpeg -version to check if it's installed
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode != 0:
            return JSONResponse(
                {"error": "FFmpeg not found. Please install FFmpeg to enable GIF to MP4 conversion."}, 
                status_code=500
            )
    except FileNotFoundError:
        # FFmpeg is not installed or not in PATH
        return JSONResponse(
            {"error": "FFmpeg not found. Please install FFmpeg to enable GIF to MP4 conversion."}, 
            status_code=500
        )
    
    try:
        # Convert GIF to MP4 using FFmpeg with high quality settings
        # -i: input file
        # -pix_fmt yuv420p: Use appropriate pixel format for video players
        # -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2": Make sure dimensions are even (required by some codecs)
        # -movflags +faststart: Optimize for web playback
        # -crf 18: High quality (lower is better, range 0-51)
        # -preset veryslow: Better compression at the cost of encoding time
        result = subprocess.run([
            "ffmpeg", 
            "-i", gif_file,
            "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-movflags", "+faststart",
            "-crf", "18",
            "-preset", "medium",
            mp4_file
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            # If conversion failed, return error message with ffmpeg output
            return JSONResponse(
                {"error": f"Failed to convert GIF to MP4: {result.stderr}"}, 
                status_code=500
            )
        
        # Successfully converted
        return {"mp4_file": mp4_file, "status": "success"}
    except Exception as e:
        return JSONResponse({"error": f"Error converting GIF to MP4: {str(e)}"}, status_code=500)

@app.get("/download-mp4/{screenshot_dir}")
async def download_mp4(screenshot_dir: str):
    """Download the MP4 converted from GIF."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        mp4_file = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}/session.mp4")
    else:
        mp4_file = f"{screenshot_dir}/session.mp4"
    
    # If MP4 doesn't exist yet, try to convert it
    if not os.path.exists(mp4_file):
        try:
            # Try to convert GIF to MP4
            result = await convert_gif_to_mp4(screenshot_dir)
            if "error" in result:
                return JSONResponse(result, status_code=500)
        except Exception as e:
            return JSONResponse({"error": f"Error creating MP4: {str(e)}"}, status_code=500)
    
    # Check again if MP4 exists after potential conversion
    if not os.path.exists(mp4_file):
        return JSONResponse({"error": "MP4 file not found"}, status_code=404)
    
    return FileResponse(mp4_file, media_type="video/mp4", filename=f"{screenshot_dir}_recording.mp4")

@app.get("/download-markdown/{screenshot_dir}")
async def download_markdown(screenshot_dir: str):
    """Download the markdown report for a run with all images as a zip file."""
    # Make sure we have the correct full path
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_screenshot_dir = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}")
        # Check if the report exists in the reports folder
        reports_dir = os.path.join(current_dir, "reports")
        report_images_dir = os.path.join(reports_dir, f"{screenshot_dir}_images")
    else:
        full_screenshot_dir = screenshot_dir
        # Extract the run name from the path
        run_name = os.path.basename(screenshot_dir)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        reports_dir = os.path.join(current_dir, "reports")
        report_images_dir = os.path.join(reports_dir, f"{run_name}_images")
    
    # If markdown file doesn't exist yet, try to generate it
    if not os.path.exists(report_images_dir):
        try:
            # Try to generate markdown report
            result = await generate_markdown(screenshot_dir)
            if "error" in result:
                return JSONResponse({"error": result["error"]}, status_code=500)
        except Exception as e:
            return JSONResponse({"error": f"Error generating markdown report: {str(e)}"}, status_code=500)
    
    # Create the report images directory if it doesn't exist
    if not os.path.exists(report_images_dir):
        os.makedirs(report_images_dir, exist_ok=True)
        
        # Copy all images from the screenshot directory to the report images directory
        screenshot_images_dir = os.path.join(full_screenshot_dir)
        if os.path.exists(screenshot_images_dir):
            for file in os.listdir(screenshot_images_dir):
                if file.endswith(".png") or file.endswith(".jpg") or file.endswith(".jpeg") or file.endswith(".gif"):
                    source_path = os.path.join(screenshot_images_dir, file)
                    dest_path = os.path.join(report_images_dir, file)
                    shutil.copy2(source_path, dest_path)
    
    # Create a zip file
    import zipfile
    import io
    
    # Create a BytesIO object to hold the zip file in memory
    zip_buffer = io.BytesIO()
    
    # Find the markdown file
    run_name = os.path.basename(full_screenshot_dir)
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_screenshots/reports")
    markdown_files = [f for f in os.listdir(reports_dir) if f.startswith(run_name) and f.endswith(".md")]
    
    with zipfile.ZipFile(zip_buffer, 'w') as zipf:
        # Add the markdown file to the zip with modified image paths for local viewing
        if markdown_files:
            for md_file in markdown_files:
                md_path = os.path.join(reports_dir, md_file)
                
                # Read the markdown content
                with open(md_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                # Replace web image paths with local paths for downloaded version
                # Look for pattern: ![Step X Screenshot](/get-image/run_name/image.png)<!-- LOCAL_PATH:./image.png -->
                # Replace with: ![Step X Screenshot](./image.png)
                import re
                md_content = re.sub(r'!\[(.*?)\]\([^)]+\)<!-- LOCAL_PATH:(.*?) -->', r'![\1](\2)', md_content)
                
                # Write the modified content to a temporary file
                temp_md_path = os.path.join(os.path.dirname(md_path), f"temp_{md_file}")
                with open(temp_md_path, 'w', encoding='utf-8') as f:
                    f.write(md_content)
                
                # Add the modified file to the zip
                zipf.write(temp_md_path, arcname=md_file)
                
                # Remove the temporary file
                os.remove(temp_md_path)
        
        # Add all files from the report_images_dir to the zip file
        if os.path.exists(report_images_dir):
            for root, _, files in os.walk(report_images_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Add the file to the zip with a relative path to preserve folder structure
                    rel_path = os.path.join(f"{run_name}_images", os.path.basename(file_path))
                    zipf.write(file_path, arcname=rel_path)
    
    # Seek to the beginning of the BytesIO object
    zip_buffer.seek(0)
    
    # Return the zip file as a streaming response
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={screenshot_dir}_report.zip"}
    )

@app.post("/stop-task/{screenshot_dir}")
async def stop_task(screenshot_dir: str):
    """Forcefully stop a running task by killing its process"""
    # Handle the case where screenshot_dir might be a full path or just the directory name
    if os.path.basename(screenshot_dir) == screenshot_dir:
        # If it's just a directory name, assume it's in web-ui/agent_screenshots
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_screenshot_dir = os.path.join(current_dir, f"agent_screenshots/{screenshot_dir}")
    else:
        full_screenshot_dir = screenshot_dir
    
    # Check if the pid file exists
    pid_file = os.path.join(full_screenshot_dir, "agent_pid.txt")
    
    if not os.path.exists(pid_file):
        return JSONResponse({"error": "Process ID file not found. Task may have completed or not started correctly."}, status_code=404)
    
    try:
        # Read the PID from the file
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        import signal
        import psutil
        
        # Check if the process exists
        if psutil.pid_exists(pid):
            # Get the process
            process = psutil.Process(pid)
            
            # Kill the process and all its children
            for child in process.children(recursive=True):
                try:
                    child.kill()
                except Exception as e:
                    print(f"Error killing child process {child.pid}: {e}")
            
            # Kill the main process
            process.kill()
            
            # Add a note to the log file
            log_file = os.path.join(full_screenshot_dir, "execution.log")
            if os.path.exists(log_file):
                with open(log_file, "a") as f:
                    f.write(f"\n\n--- Task forcefully terminated by user at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            
            # Create a more visible terminated.txt file
            with open(os.path.join(full_screenshot_dir, "terminated.txt"), "w") as f:
                f.write(f"Task forcefully terminated by user at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return {"status": "success", "message": "Task forcefully terminated"}
        else:
            return {"status": "warning", "message": "Process not found. Task may have already completed."}
    
    except Exception as e:
        return JSONResponse({"error": f"Error stopping task: {str(e)}"}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    
    # Print startup configuration
    print(f"Starting server on {HOST}:{PORT}")
    if DEFAULT_CHROME_PATH:
        print(f"Default Chrome path: {DEFAULT_CHROME_PATH}")
    
    uvicorn.run(app, host=HOST, port=PORT) 