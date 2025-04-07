# Changes Log

## 2025-04-07

### Improved Markdown Report Generation

1. Fixed image paths in markdown reports to ensure they display correctly in both web UI and downloaded reports
2. Added special comment tags to handle different image path formats for web viewing vs local viewing
3. Enhanced the download_markdown endpoint to replace web image paths with local paths when downloading
4. Added a new API endpoint (/get-image/{screenshot_dir}/{image_name}) to serve images directly from screenshots folder
5. Moved "Generate Markdown Report" button from Downloads tab to Markdown tab for better user experience
6. Updated the UI text to reflect the new button location
7. Ensured step descriptions are concise (50-100 tokens) for better readability

## 2025-04-06

### Added Markdown Report Viewing and Downloading in Web Interface

1. Added a new Markdown tab in the HTML interface to display generated markdown reports
2. Enhanced the renderMarkdown function to properly format and display markdown content
3. Added a download button to download the generated markdown reports
4. Created a new API endpoint in app.py (/download-markdown/{screenshot_dir}) for downloading reports
5. Fixed URL formatting issues to ensure proper report generation and display
6. Fixed error in stopTask function by adding null check for downloadOptions element
7. Integrated template_processor.py with the generate_markdown endpoint to use the custom templates
8. Added fallback to the original markdown generation if template processing fails

### Added Template-Based Markdown Report System

1. Created a template system for generating customizable markdown reports
2. Added template_processor.py to process templates with placeholders
3. Created a templates directory with tutorial_template.md and simple_template.md
4. Reports are now generated in a clean, tutorial-style format with step-by-step instructions
5. Templates can be modified without changing the underlying code

### Added Markdown Report Generator (markdown_generator.py)

1. Created a new script to generate beautiful markdown reports from browser automation task logs and screenshots
2. The script can process all screenshots, logs, and task information from automation runs
3. Reports are saved in the /reports directory with proper formatting and image links
4. Supports generating reports for the latest run, a specific run, or all runs
5. Uses the same AI models as simple_agent.py (GPT-4o or Claude 3.5 Sonnet)

### AI Model Updates in simple_agent.py

1. Changed OpenAI model from "gpt-3.5-turbo" to "gpt-4o"
2. Changed Claude model from "claude-3-sonnet-20240229" to "claude-3-5-sonnet-latest"
3. Fixed prompt issues by using the react_prompt from the hub directly for both models
4. Successfully tested with Claude model (USE_ANTHROPIC=true in .env file)

The agent now works correctly with both models and can be switched between them by changing the USE_ANTHROPIC environment variable.
