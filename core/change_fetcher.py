"""
Fetches the changelist from Gerrit and saves the initial files.
"""

import re
from pathlib import Path

from core.gerrit_client import GerritClient
from core.models import ChangeInfo
from core.utils import save_file

def parse_gerrit_url(url: str) -> tuple[str, str]:
    """Parses a Gerrit URL into (host, change_id)."""
    match = re.search(r'https://([^/]+)/.*/\+/(\d+)', url)
    if match:
        return match.group(1), match.group(2)
    elif url.isdigit():
        return "chromium-review.googlesource.com", url
    else:
        raise ValueError("Could not parse change ID from input.")

def fetch_change(url: str, output_dir: Path) -> ChangeInfo:
    """
    Fetches change metadata, the patch diff, and the original files 
    for a given Gerrit URL, saving them to output_dir.
    """
    host, change_id = parse_gerrit_url(url)
    client = GerritClient(host)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Fetching change info...")
    info_json = client.fetch_change_info(change_id)
    
    project = info_json.get("project", "")
    numeric_id = info_json.get("_number", change_id)
    current_rev = info_json.get("current_revision", "")
    commit_url = f"https://{host}/c/{project}/+/{numeric_id}"
    
    gitiles_link = ""
    patch_set_num = "UNKNOWN"
    subject = "UNKNOWN"
    message = "UNKNOWN"
    author_name = "UNKNOWN"
    author_email = "UNKNOWN"

    if current_rev:
        revision_data = info_json.get("revisions", {}).get(current_rev, {})
        patch_set_num = revision_data.get("_number", "UNKNOWN")
        commit_data = revision_data.get("commit", {})
        subject = commit_data.get("subject", "UNKNOWN")
        message = commit_data.get("message", "UNKNOWN")
        author_data = commit_data.get("author", {})
        author_name = author_data.get("name", "UNKNOWN")
        author_email = author_data.get("email", "UNKNOWN")

        for link in commit_data.get("web_links", []):
            if link.get("name") == "Gitiles":
                gitiles_link = link.get("url")
                break

    change_info = ChangeInfo(
        cl_id=str(numeric_id),
        host=host,
        project=project,
        branch=info_json.get("branch", "UNKNOWN"),
        status=info_json.get("status", "UNKNOWN"),
        patch_set=str(patch_set_num),
        author_name=author_name,
        author_email=author_email,
        created=info_json.get("created", "UNKNOWN"),
        updated=info_json.get("updated", "UNKNOWN"),
        subject=subject,
        message=message,
        commit_url=commit_url,
        gitiles_link=gitiles_link
    )
    
    # Save commit_info
    commit_info_content = (
        f"Commit URL: {change_info.commit_url}\n"
        f"Gitiles Link: {change_info.gitiles_link if change_info.gitiles_link else 'Not available'}\n"
        f"Project: {change_info.project}\n"
        f"Branch: {change_info.branch}\n"
        f"Status: {change_info.status}\n"
        f"Patch Set: {change_info.patch_set}\n"
        f"Author: {change_info.author_name} <{change_info.author_email}>\n"
        f"Created: {change_info.created}\n"
        f"Updated: {change_info.updated}\n"
        f"\nSubject: {change_info.subject}\n"
        f"\nCommit Message:\n{change_info.message}\n"
    )
    save_file(output_dir / "commit_info", commit_info_content)
    print(f"Saved commit info to: {output_dir / 'commit_info'}")

    # Fetch and save diff
    print("Fetching complete diff...")
    patch_bytes = client.fetch_patch_diff(change_id, context_lines=20)
    save_file(output_dir / "diff.patch", patch_bytes)
    print(f"Saved complete diff to: {output_dir / 'diff.patch'}")

    # Fetch changed files
    print("Fetching original file contents...")
    files_data = client.fetch_changed_files(change_id)
    modified_files = []
    
    for file_path in files_data.keys():
        if file_path == "/COMMIT_MSG":
            continue
        modified_files.append(file_path)
        try:
            original_bytes = client.fetch_original_file(change_id, file_path)
            save_file(output_dir / file_path, original_bytes)
            print(f"- Saved: {output_dir / file_path}")
        except Exception as e:
            print(f"- Failed to fetch original file '{file_path}' (may be a new file): {e}")

    # Discover and save project tree
    print("Discovering project tree context...")
    target_dirs = set([""]) # Always include root
    
    for file_path in modified_files:
        parts = file_path.split('/')
        # Add all parent directories up to root
        for i in range(len(parts)):
            dir_path = "/".join(parts[:i])
            target_dirs.add(dir_path)
            
    tree_files = set()
    commit_id = current_rev if current_rev else "HEAD"
    
    for dir_path in sorted(list(target_dirs)):
        try:
            dir_data = client.fetch_gitiles_directory(project, commit_id, dir_path, gitiles_commit_url=change_info.gitiles_link)
            entries = dir_data.get("entries", [])
            for entry in entries:
                if entry.get("type") == "blob":
                    file_name = entry.get("name")
                    full_path = f"{dir_path}/{file_name}" if dir_path else file_name
                    tree_files.add(full_path)
        except Exception as e:
            print(f"- Warning: Could not fetch directory listing for '{dir_path}': {e}")
            
    if tree_files:
        tree_content = "Project files near the changed files:\n\n" + "\n".join(sorted(list(tree_files))) + "\n"
        save_file(output_dir / "project_tree", tree_content)
        print(f"Saved project tree context with {len(tree_files)} files to: {output_dir / 'project_tree'}")

    return change_info
