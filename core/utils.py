"""
Utility functions for file system operations and context reading.
"""

import os
from pathlib import Path
from typing import List, Optional

def save_file(file_path: Path, content: str | bytes) -> None:
    """
    Saves content to a file, creating parent directories if they don't exist.
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    encoding = None if isinstance(content, bytes) else "utf-8"
    
    with open(file_path, mode, encoding=encoding) as f:
        f.write(content)

def read_directory_context(cl_dir: Path, max_lines: int = 10000) -> str:
    """
    Reads all text files in a directory to build a combined context string.
    Ensures that 'diff.patch' and 'summary' are placed at the very end.
    Skips binary files or files exceeding max_lines.
    """
    contents = []
    delayed_files: List[Path] = []
    
    # Files to ignore completely
    ignore_files = {"pre_review", "extra_context_files", "code_review.md", "full_context"}
    
    # Files to push to the end of the context (recency bias)
    end_files = {"diff.patch", "summary"}

    for root, _, files in os.walk(cl_dir):
        for file in files:
            if file in ignore_files:
                continue
                
            file_path = Path(root) / file
            
            if file in end_files:
                delayed_files.append(file_path)
                continue
            
            _append_file_content(file_path, contents, max_lines)
            
    # Sort delayed files to ensure diff.patch is absolutely last if present
    delayed_files.sort(key=lambda p: 1 if p.name == "diff.patch" else 0)
    
    for file_path in delayed_files:
        _append_file_content(file_path, contents, max_lines)
        
    return "\n".join(contents)

def _append_file_content(file_path: Path, contents_list: List[str], max_lines: int) -> None:
    """Helper to read a single file and append it to the context list."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if len(lines) > max_lines:
                print(f"Skipping {file_path} (more than {max_lines} lines)")
                return
            
            file_content = "".join(lines)
            contents_list.append(f"--- File: {file_path} ---\n{file_content}\n")
    except UnicodeDecodeError:
        print(f"Skipping {file_path} (binary or non-UTF-8 content)")
    except Exception as e:
        print(f"Skipping {file_path} due to error: {e}")
