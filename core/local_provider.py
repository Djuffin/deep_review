"""
Provides change information and file access for local git repositories.
"""

import subprocess
import os
from pathlib import Path
from core.models import ChangeInfo

def is_local_repo(path_str: str) -> bool:
    """Checks if the string is a path to a local git repository."""
    path = Path(path_str).expanduser().resolve()
    return path.is_dir() and (path / ".git").exists()

def fetch_local_change(repo_path: Path) -> tuple[ChangeInfo, str]:
    """
    Gather 'CL' info from the local git repo.
    Returns (ChangeInfo, diff_text).
    """
    diff_command = ""
    # 1. Get the diff against the upstream/tracking branch
    try:
        # Find the merge base with the upstream branch (e.g. origin/main)
        merge_base = subprocess.check_output(
            ["git", "merge-base", "HEAD", "@{u}"], 
            cwd=repo_path, text=True, stderr=subprocess.DEVNULL
        ).strip()
        
        diff_command = f"git diff {merge_base}"
        diff_text = subprocess.check_output(
            ["git", "diff", merge_base], 
            cwd=repo_path, text=True
        )
    except subprocess.CalledProcessError:
        # Fallback to just diffing against HEAD if no upstream is found
        diff_command = "git diff HEAD"
        diff_text = subprocess.check_output(
            ["git", "diff", "HEAD"], 
            cwd=repo_path, text=True
        )

    # 2. Get commit info (subject, message)
    try:
        subject = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"], cwd=repo_path, text=True
        ).strip()
        message = subprocess.check_output(
            ["git", "log", "-1", "--format=%B"], cwd=repo_path, text=True
        ).strip()
        author = subprocess.check_output(
            ["git", "log", "-1", "--format=%an <%ae>"], cwd=repo_path, text=True
        ).strip()
    except Exception:
        subject = "Local Changes"
        message = "Uncommitted local changes"
        author = "Local User"

    # Append the diff command to the message so it's logged
    message = f"Diff generated using: {diff_command}\n\n" + message

    # 3. Get file tree
    tree_files = subprocess.check_output(
        ["git", "ls-files"], cwd=repo_path, text=True
    ).splitlines()
    
    project_tree = "Project files in local repository:\n\n" + "\n".join(tree_files)

    change_info = ChangeInfo(
        cl_id="local",
        host="local",
        project=repo_path.name,
        subject=subject,
        message=message,
        author_name=author,
        # We'll use this to store the actual path for the tools to use
        gitiles_link=str(repo_path) 
    )

    return change_info, diff_text, project_tree
