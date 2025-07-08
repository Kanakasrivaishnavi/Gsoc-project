# OLS Fetch from GitHub Module

## Quick Start

**Main Entry Point**: `main_workflow.py`

```bash
python main_workflow.py
```

## Overall Logic Flow

```
1. Check GitHub for SBO file updates
2. If updates found:
   → Ask user: "Do you want to execute the update?" (Yes/No)
   → If Yes:
     - Download and compare changes
     - Show detailed changes
     - Ask user: "Apply these updates?" (y/n)  ← Second confirmation
     - If y: Apply updates
     - If n: Offer alternatives (upload file or use current file)
   → If No: Offer alternatives (upload file or use current file)
3. If no updates found:
   → Directly use existing file
  
```

## Key Features

- **Two-step confirmation**: First asks if you want to check for updates, then shows changes before final application
- **Change preview**: See exactly what will change before applying updates
- **File validation**: Supports both OBO and JSON formats with conversion and validation
- **Version management**: Keeps latest versions and cleans up old files

## Module Files

- **`main_workflow.py`** - Main entry point, user interaction and workflow orchestration
- **`github_file_updater.py`** - Download, update, and compare files from GitHub
- **`user_file_processor.py`** - Process and validate user uploaded files  
- **`change_logger.py`** - Track and log changes between versions

## Usage

### As Main Program
```bash
python main_workflow.py
```

### As Module
```python
from main_workflow import SBOWorkflowManager

workflow = SBOWorkflowManager()
workflow.run_workflow()
active_file = workflow.get_active_file()  # Returns path to active JSON file
workflow.cleanup()  # Clean up resources
```

## User Interaction Example

```
🚀 Starting SBO file workflow
🔍 Checking for remote file updates...

📋 File updates found!
Do you want to execute the update?
1. Yes
2. No
Please enter choice (number): 1

🔄 Executing update...
📊 Change Summary
================================================================================
📋 Terms changes:
  ➕ Added: 5
  🔄 Updated: 12
📈 Total changes: 17 items
================================================================================

Apply these updates? (y/n): y
✅ Update completed!
```

## Input/Output

- **Input**: SBO files from GitHub or user uploads (.obo or .json)
- **Output**: Validated JSON file ready for SBO annotation processing
- **Location**: `SBO_OBO_Files/localfiles/SBO_OBO_YYYYMMDD_HHMMSS.json`

## Directory Structure

```
SBO_OBO_Files/
├── localfiles/     # Final processed files (OBO, JSON, metadata)
├── logs/          # Change tracking logs between versions
└── customerfile/  # Temporary storage for user uploaded files
```

## Dependencies

- Python standard library (no external packages required)
- Git (for file comparison operations)
- Internet connection (for GitHub API access)