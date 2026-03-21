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

def build_analysis_context(cl_dir: Path, max_lines: int = 10000) -> str:
    """
    Builds the context string specifically for the initial Context Analyzer LLM.
    Includes the project tree, historically coupled files, commit info, original files, and the diff.
    """
    contents = []
    
    # 1. Add Commit Info
    _append_file_content(cl_dir / "commit_info", contents, max_lines)
    
    # 2. Add Project Tree (Crucial for analysis)
    _append_file_content(cl_dir / "project_tree", contents, max_lines)
    
    # 3. Add Historically Coupled Files (If they exist)
    if (cl_dir / "historically_coupled_files").exists():
        _append_file_content(cl_dir / "historically_coupled_files", contents, max_lines)
        
    # 4. Add Original Files modified in the PR
    # We find these by listing everything that isn't a known meta-file
    meta_files = {"commit_info", "project_tree", "historically_coupled_files", "diff.patch", "summary", "extra_context_files", "code_review.md", "full_context"}
    
    for root, _, files in os.walk(cl_dir):
        for file in files:
            file_path = Path(root) / file
            
            # Skip known meta-files
            if file in meta_files:
                continue
                
            _append_file_content(file_path, contents, max_lines)
            
    # 5. Add the Diff last (Recency bias)
    _append_file_content(cl_dir / "diff.patch", contents, max_lines)
    
    return "\n".join(contents)


def build_review_context(cl_dir: Path, max_lines: int = 10000) -> str:
    """
    Builds the context string specifically for the specialized Review Agents.
    Excludes noise like project_tree and historically_coupled_files.
    Includes commit info, extra context files, original files, summary, and the diff.
    """
    contents = []
    
    # 1. Add Commit Info
    _append_file_content(cl_dir / "commit_info", contents, max_lines)
    
    # 2. Add Extra Context Files first (Architectural context)
    extra_context_list_file = cl_dir / "extra_context_files"
    extra_files_added = set()
    
    if extra_context_list_file.exists():
        try:
            with open(extra_context_list_file, "r", encoding="utf-8") as f:
                for line in f:
                    extra_file_path = line.strip()
                    if extra_file_path:
                        full_path = cl_dir / extra_file_path
                        if full_path.exists():
                            _append_file_content(full_path, contents, max_lines)
                            extra_files_added.add(extra_file_path)
        except Exception as e:
            print(f"Warning: Could not read extra_context_files list: {e}")

    # 3. Add Original Modified Source Files
    # We exclude meta-files, noise, AND the extra files we just added
    meta_files = {"commit_info", "project_tree", "historically_coupled_files", "diff.patch", "summary", "extra_context_files", "code_review.md", "full_context"}
    
    for root, _, files in os.walk(cl_dir):
        for file in files:
            # We need the relative path from cl_dir to check against extra_files_added
            file_path = Path(root) / file
            rel_path = str(file_path.relative_to(cl_dir))
            
            # Skip known meta-files, noise, and already added extra files
            if file in meta_files or rel_path in extra_files_added:
                continue
                
            _append_file_content(file_path, contents, max_lines)
            
    # 4. Add Summary (Recency bias)
    if (cl_dir / "summary").exists():
        _append_file_content(cl_dir / "summary", contents, max_lines)
        
    # 5. Add the Diff absolutely last (Recency bias)
    _append_file_content(cl_dir / "diff.patch", contents, max_lines)
    
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
