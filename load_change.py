"""
load_change.py

This script interacts with the Gerrit REST API to download the complete context 
of a specified Gerrit Changelist (CL). Given a Gerrit CL URL or ID, it performs 
the following operations:

1. Creates a local directory named after the CL ID.
2. Fetches and saves commit metadata (author, branch, commit message, Gitiles link, etc.) 
   into a `commit_info` file.
3. Downloads the complete diff/patch file with 20 lines of context into `diff.patch`.
4. Retrieves the original (base/parent=1) contents of all modified files and saves 
   them inside the CL directory, preserving their directory structure.

Usage: python3 load_change.py <gerrit-cl-url-or-number>
"""

import sys
import json
import base64
import urllib.parse
import urllib.request
import re
import os

def get_gerrit_data(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        data = response.read().decode('utf-8')
        # Gerrit REST API responses start with a magic string to prevent XSSI
        if data.startswith(")]}'"):
            data = data[4:]
        return json.loads(data)

def get_gerrit_base64_bytes(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as response:
        encoded_data = response.read()
        return base64.b64decode(encoded_data)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 load_change.py <gerrit-cl-url-or-number>")
        print("Example: python3 load_change.py https://chromium-review.googlesource.com/c/chromium/src/+/7652046")
        sys.exit(1)

    url_or_id = sys.argv[1]

    # Parse the host and change ID
    host = "chromium-review.googlesource.com"
    change_id = url_or_id

    # Example URL: https://chromium-review.googlesource.com/c/chromium/src/+/7652046
    match = re.search(r'https://([^/]+)/.*/\+/(\d+)', url_or_id)
    if match:
        host = match.group(1)
        change_id = match.group(2)
    elif url_or_id.isdigit():
        change_id = url_or_id
    else:
        print("Could not parse change ID from input. Using input as change ID directly.")

    base_api_url = f"https://{host}/changes/{change_id}"

    # Create directory for the CL
    cl_dir = str(change_id)
    os.makedirs(cl_dir, exist_ok=True)
    print(f"Created directory: {cl_dir}")

    # Fetch change info for URLs
    info_url = f"{base_api_url}?o=CURRENT_REVISION&o=CURRENT_COMMIT&o=WEB_LINKS"
    print("Fetching change info...")
    try:
        change_info = get_gerrit_data(info_url)
        project = change_info.get("project", "")
        numeric_id = change_info.get("_number", change_id)
        current_rev = change_info.get("current_revision", "")
        status = change_info.get("status", "UNKNOWN")
        branch = change_info.get("branch", "UNKNOWN")
        created = change_info.get("created", "UNKNOWN")
        updated = change_info.get("updated", "UNKNOWN")
        
        # If the project contains slashes, they are often URL encoded in the change ID, but the UI URL wants them literal or encoded depending on host.
        # usually /c/project/+/number works
        commit_url = f"https://{host}/c/{project}/+/{numeric_id}"
        
        gitiles_link = ""
        patch_set_num = "UNKNOWN"
        subject = "UNKNOWN"
        message = "UNKNOWN"
        author_name = "UNKNOWN"
        author_email = "UNKNOWN"

        if current_rev:
            revision_data = change_info.get("revisions", {}).get(current_rev, {})
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

        # Write to commit_info
        commit_info_path = os.path.join(cl_dir, "commit_info")
        with open(commit_info_path, "w") as f:
            f.write(f"Commit URL: {commit_url}\n")
            f.write(f"Gitiles Link: {gitiles_link if gitiles_link else 'Not available'}\n")
            f.write(f"Project: {project}\n")
            f.write(f"Branch: {branch}\n")
            f.write(f"Status: {status}\n")
            f.write(f"Patch Set: {patch_set_num}\n")
            f.write(f"Author: {author_name} <{author_email}>\n")
            f.write(f"Created: {created}\n")
            f.write(f"Updated: {updated}\n")
            f.write(f"\nSubject: {subject}\n")
            f.write(f"\nCommit Message:\n{message}\n")
            
        print(f"Saved commit info to: {commit_info_path}")
    except Exception as e:
        print(f"Failed to fetch change info: {e}")

    # --- 1. Get list of changed files ---
    files_url = f"{base_api_url}/revisions/current/files/"
    print(f"Fetching files from: {files_url}")
    try:
        files_data = get_gerrit_data(files_url)
    except Exception as e:
        print(f"Failed to fetch files: {e}")
        sys.exit(1)

    changed_files = []
    for file_path, info in files_data.items():
        if file_path == "/COMMIT_MSG":
            continue
        changed_files.append(file_path)

    # --- 2. Complete diff ---
    patch_url = f"{base_api_url}/revisions/current/patch?context=20"
    print(f"Fetching complete diff from: {patch_url}")
    try:
        patch_bytes = get_gerrit_base64_bytes(patch_url)
        patch_path = os.path.join(cl_dir, "diff.patch")
        with open(patch_path, "wb") as f:
            f.write(patch_bytes)
        print(f"Saved complete diff to: {patch_path}")
    except Exception as e:
        print(f"Failed to fetch patch: {e}")

    # --- 3. URLs to download the original file content ---
    print("Fetching original file contents...")
    for file_path in changed_files:
        # File path must be URL encoded (e.g., / becomes %2F)
        encoded_path = urllib.parse.quote(file_path, safe='')
        content_url = f"{base_api_url}/revisions/current/files/{encoded_path}/content?parent=1"
        try:
            original_bytes = get_gerrit_base64_bytes(content_url)
            local_file_path = os.path.join(cl_dir, file_path)
            # Create subdirectories matching the file path structure
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            with open(local_file_path, "wb") as f:
                f.write(original_bytes)
            print(f"- Saved: {local_file_path}")
        except Exception as e:
            # If the file is newly added, getting it from parent=1 might fail (404 Not Found)
            print(f"- Failed to fetch original file '{file_path}' (may be a new file): {e}")

if __name__ == "__main__":
    main()
