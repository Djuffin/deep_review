"""
review.py

This script takes a Changelist (CL) directory and reads all the files within it 
(skipping files over 5000 lines). It uses the Gemini REST API to prepare a cached 
context of the codebase, and then prompts the Gemini model to perform a thorough 
code review.

The review focuses on logic, memory safety, buffer safety, and other implementation details,
outputting strictly negative feedback with file and line references.

The output is saved to a `code_review.md` file inside the CL directory.

Usage: python3 review.py <cl-dir-number>
"""

import os
import sys
import json
import urllib.request
import urllib.error
import concurrent.futures

def get_file_contents(cl_dir):
    contents = []
    delayed_files = []
    
    # Walk through the directory to find all downloaded files
    for root, dirs, files in os.walk(cl_dir):
        for file in files:
            file_path = os.path.join(root, file)
            
            # Skip output files to avoid recursive prompting
            if file in ("pre_review", "extra_context_files", "code_review.md"):
                continue
            
            # Save diff.patch and summary to process them last
            if file in ("diff.patch", "summary"):
                delayed_files.append(file_path)
                continue
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    if len(lines) > 5000:
                        print(f"Skipping {file_path} (more than 5000 lines)")
                        continue
                    
                    file_content = "".join(lines)
                    contents.append(f"--- File: {file_path} ---\n{file_content}\n")
            except UnicodeDecodeError:
                print(f"Skipping {file_path} (binary or non-UTF-8 content)")
            except Exception as e:
                print(f"Skipping {file_path} due to error: {e}")
                
    # Process the delayed files (diff.patch and summary) last
    # Try to order them specifically if both exist (e.g., summary then diff.patch)
    delayed_files.sort(key=lambda x: 1 if "diff.patch" in x else 0)
    
    for file_path in delayed_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if len(lines) > 5000:
                    print(f"Skipping {file_path} (more than 5000 lines)")
                    continue
                
                file_content = "".join(lines)
                contents.append(f"--- File: {file_path} ---\n{file_content}\n")
        except Exception as e:
            print(f"Skipping {file_path} due to error: {e}")
            
    return contents

def create_cached_content(api_key, model_name, document_text):
    # caching requires the model path like "models/gemini-1.5-pro-001"
    url = f"https://generativelanguage.googleapis.com/v1beta/cachedContents?key={api_key}"
    headers = {"Content-Type": "application/json"}
    data = {
        "model": f"models/{model_name}",
        "contents": [{
            "parts": [{"text": document_text}],
            "role": "user"
        }],
        "ttl": "3600s"
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('name')
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Failed to create cache: HTTP {e.code}")
        print(f"Details: {error_body}")
        return None
    except Exception as e:
        print(f"Failed to create cache: {e}")
        return None

def delete_cached_content(api_key, cache_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/{cache_name}?key={api_key}"
    req = urllib.request.Request(url, method='DELETE')
    try:
        urllib.request.urlopen(req)
        print("Cached content deleted.")
    except Exception as e:
        print(f"Failed to delete cache: {e}")

def call_gemini_api(api_key, model_name, prompt, document_text=None, cache_name=None):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    data = {
        "contents": [{
            "parts": [{"text": prompt}],
            "role": "user"
        }],
        "generationConfig": {
            "temperature": 0.2
        }
    }
    
    if cache_name:
        data["cachedContent"] = cache_name
    elif document_text:
        # Fallback to including the document directly
        data["contents"][0]["parts"].insert(0, {"text": document_text + "\n\n"})
        
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            try:
                return result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                print("Unexpected response structure from Gemini API:")
                print(json.dumps(result, indent=2))
                return None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {e.reason}")
        print(f"Details: {error_body}")
        return None
    except Exception as e:
        print(f"Failed to communicate with Gemini API: {e}")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 review.py <cl-dir>")
        sys.exit(1)

    cl_dir = sys.argv[1]
    if not os.path.isdir(cl_dir):
        print(f"Error: Directory '{cl_dir}' does not exist.")
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    # Read agent prompts from the 'agents' directory
    agents_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")
    if not os.path.isdir(agents_dir):
        print(f"Error: Agents directory '{agents_dir}' does not exist.")
        sys.exit(1)

    agents = []
    for filename in os.listdir(agents_dir):
        if filename.endswith(".md"):
            agent_name = filename[:-3]
            with open(os.path.join(agents_dir, filename), "r", encoding="utf-8") as f:
                agent_prompt = f.read()
            agents.append((agent_name, agent_prompt))
            
    if not agents:
        print(f"Error: No agent prompts (.md files) found in '{agents_dir}'.")
        sys.exit(1)

    print(f"Reading files in '{cl_dir}'...")
    file_contents = get_file_contents(cl_dir)
    if not file_contents:
        print("No valid files found to analyze.")
        sys.exit(1)

    document_text = "\n".join(file_contents)
    
    # The user specifically requested this model
    model_name = 'gemini-3.1-pro-preview'
    
    print("Attempting to create cached context...")
    cache_name = create_cached_content(api_key, model_name, document_text)
    
    if cache_name:
        print(f"Context cached successfully ({cache_name}).")
    else:
        print("Caching failed or is unsupported for this context size. Falling back to direct API requests...")

    def run_agent(agent_data):
        agent_name, prompt = agent_data
        print(f"Generating review from agent: {agent_name}...")
        if cache_name:
            response_text = call_gemini_api(api_key, model_name, prompt, cache_name=cache_name)
        else:
            response_text = call_gemini_api(api_key, model_name, prompt, document_text=document_text)

        if response_text:
            return f"## Review by {agent_name}\n\n{response_text}"
        else:
            return f"## Review by {agent_name}\n\n(Failed to get review from this agent)"

    all_reviews = []
    
    # Run agents in parallel using a thread pool
    max_workers = min(10, len(agents))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_agent = {executor.submit(run_agent, agent): agent for agent in agents}
        
        # Collect results as they complete, but we want to keep them in some order or just append
        for future in concurrent.futures.as_completed(future_to_agent):
            try:
                result = future.result()
                all_reviews.append(result)
            except Exception as exc:
                agent_name = future_to_agent[future][0]
                all_reviews.append(f"## Review by {agent_name}\n\n(Exception occurred: {exc})")

    if cache_name:
        delete_cached_content(api_key, cache_name)

    # Save the output to the code_review.md file
    out_file = os.path.join(cl_dir, "code_review.md")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(all_reviews))
    
    print(f"\nReview complete! Saved to {out_file}")

if __name__ == "__main__":
    main()
