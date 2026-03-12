"""
Multi-threaded code review engine using Gemini Context Caching and Tool Calling.
"""

import os
import time
import threading
import concurrent.futures
from pathlib import Path
from typing import List, Callable, Optional, Dict, Any

from core.gemini_client import GeminiClient
from core.gerrit_client import GerritClient
from core.models import AgentReview, ChangeInfo
from core.utils import read_directory_context, save_file

COMMON_AGENT_INSTRUCTION = """
**CRITICAL INSTRUCTION:** You must analyze ONLY the code changes (the lines added or modified in the diff). Do NOT report issues, bugs, or improvements for existing code that was not modified in this changelist, even if it is provided in the context.

**TOOL USE:** You have access to the tool `get_function` to investigate the codebase. If the diff references a function or class you don't understand, or you need to see the logic of a function called in the diff, USE `get_function` to fetch it. Do not guess function signatures or implementations.
"""

# Tool definitions for the Gemini API
TOOLS = [{
    "function_declarations": [
        {
            "name": "get_function",
            "description": "Fetch the body of a specific function or class from a file.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "file_path": {
                        "type": "STRING",
                        "description": "The full path to the file."
                    },
                    "function_name": {
                        "type": "STRING",
                        "description": "The name of the function or class to extract."
                    }
                },
                "required": ["file_path", "function_name"]
            }
        }
    ]
}]

def _create_logger(cl_dir: Path) -> Callable[[str], None]:
    """Creates a thread-safe logger that writes to agent_activity.log"""
    log_file = cl_dir / "agent_activity.log"
    lock = threading.Lock()
    
    def log(message: str):
        with lock:
            with open(log_file, "a", encoding="utf-8") as f:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")
    return log

def create_tool_handlers(change_info: ChangeInfo, cl_dir: Path, gemini_client: GeminiClient, logger: Callable[[str], None]) -> Dict[str, Callable]:
    """Creates the implementation for the tools available to the agents."""
    gerrit_client = GerritClient(change_info.host, logger=logger)
    cl_id = change_info.cl_id
    
    # Memoization cache: (file_path, function_name) -> code string
    extraction_cache = {}
    cache_lock = threading.Lock()

    def get_file_content(file_path: str) -> str:
        """Helper to fetch a full file content (internal only)."""
        local_path = cl_dir / file_path
        if local_path.exists():
            try:
                with open(local_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
        
        try:
            logger(f"Fetching from Gerrit: {file_path}")
            raw_bytes = gerrit_client.fetch_original_file(cl_id, file_path)
            save_file(local_path, raw_bytes)
            return raw_bytes.decode('utf-8')
        except Exception as e:
            return f"Error fetching file: {e}"

    def local_extract(content: str, name: str) -> Optional[str]:
        """Attempt to extract a function/class body or declaration."""
        import re
        # Normalize name: if it contains ::, handle optional spaces
        parts = name.split("::")
        escaped_parts = [re.escape(p.strip()) for p in parts]
        escaped_name = r"\s*::\s*".join(escaped_parts)
        
        # Look for the name followed by anything that isn't a brace or semicolon, 
        # then finally a brace or semicolon.
        # This handles both definitions { and declarations ;
        pattern = rf"(?:^|[^a-zA-Z0-9_]){escaped_name}\s*[^{{;]*([{{;])"
        
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if not match:
            return None
            
        start_idx = match.start()
        # If the match started with a non-word char, skip it
        if not content[start_idx].isalnum() and content[start_idx] != '_':
            start_idx += 1
            
        terminator = match.group(1)
        
        if terminator == ';':
            # It's a declaration
            line_start = content.rfind('\n', 0, start_idx)
            return content[max(0, line_start + 1) : match.end()]
        else:
            # It's a definition with a body
            brace_start = match.start(1)
            count = 0
            for i in range(brace_start, len(content)):
                if content[i] == '{': count += 1
                elif content[i] == '}':
                    count -= 1
                    if count == 0:
                        line_start = content.rfind('\n', 0, start_idx)
                        return content[max(0, line_start + 1) : i + 1]
        return None

    def get_function(file_path: str, function_name: str) -> str:
        """Extracts a specific function body, first locally, then via LLM."""
        # Normalize name to avoid redundant extractions
        normalized_name = function_name.strip()
        
        cache_key = (file_path, normalized_name)
        with cache_lock:
            if cache_key in extraction_cache:
                logger(f"  [Cache Hit] Using cached extraction for '{normalized_name}'")
                return extraction_cache[cache_key]

        file_content = get_file_content(file_path)
        if file_content.startswith("Error"):
            return file_content
            
        # 1. Try local extraction first
        local_result = local_extract(file_content, normalized_name)
        if local_result:
            logger(f"  [Local Extraction Success] '{normalized_name}':\n{local_result}")
            with cache_lock:
                extraction_cache[cache_key] = local_result
            return local_result

        # 2. Fall back to LLM if local fails, but use a window to be fast
        logger(f"  [Local Extraction Failed] Falling back to LLM (windowed) for '{normalized_name}'")
        
        # Find the name in the file to create a window
        try:
            name_idx = file_content.find(normalized_name)
            if name_idx == -1:
                # If name not found at all, don't bother the LLM
                return f"Error: Could not find '{normalized_name}' in {file_path}"
                
            # Create a 2000-line window around the match (approx 100 chars per line)
            start_win = max(0, name_idx - 50000)
            end_win = min(len(file_content), name_idx + 50000)
            window_content = file_content[start_win:end_win]
            
            prompt = f"Extract the exact complete body of the function or class '{function_name}' from the following code snippet. Return ONLY the raw code for that function/class, nothing else.\n\nCode:\n...{window_content}..."
            
            extracted = gemini_client.generate_content("gemini-3-flash-preview", prompt, temperature=0.0, logger=logger)
            if extracted:
                if extracted.startswith("ERROR:"):
                    logger(f"  [Extraction Error] {extracted}")
                    return extracted
                
                res = extracted.strip()
                logger(f"  [LLM Extraction Success] '{normalized_name}':\n{res}")
                
                with cache_lock:
                    extraction_cache[cache_key] = res
                return res
        except Exception as e:
            logger(f"  [LLM Extraction Exception] {e}")
        
        logger(f"  [Extraction Failed] Could not find '{normalized_name}' in {file_path}")
        return f"Error: Could not extract '{function_name}'"

    return {
        "get_function": get_function
    }

def _run_single_agent(
    agent_name: str,
    prompt: str,
    document_text: str,
    cache_name: Optional[str],
    gemini_client: GeminiClient,
    model_name: str,
    status_callback: Callable[[str, str], None],
    change_info: ChangeInfo,
    cl_dir: Path,
    logger: Callable[[str], None]
) -> AgentReview:
    """Worker function to run a single review agent."""
    status_callback(agent_name, "Running")

    # Pass the logger to the tool handlers so they can log internally
    tool_handlers = create_tool_handlers(change_info, cl_dir, gemini_client, logger)
    
    # Prefix logs from this thread with the agent's name
    def agent_logger(msg: str):
        logger(f"[{agent_name}] {msg}")

    try:
        response_text = gemini_client.generate_content(
            model_name=model_name,
            prompt=prompt,
            document_text=document_text if not cache_name else None,
            cache_name=cache_name,
            timeout=300,
            tools=TOOLS,
            tool_handlers=tool_handlers,
            logger=agent_logger
        )

        if response_text and not response_text.startswith("ERROR:"):
            status_callback(agent_name, "Done")
            return AgentReview(agent_name=agent_name, response_text=response_text, status="Done")
        else:
            status_callback(agent_name, "Failed")
            error_msg = response_text if response_text else "Empty response"
            return AgentReview(agent_name=agent_name, response_text=None, status="Failed", error_message=error_msg)

    except Exception as e:
        status_callback(agent_name, "Failed")
        agent_logger(f"Exception during review: {e}")
        return AgentReview(agent_name=agent_name, response_text=None, status="Failed", error_message=str(e))


def run_review(cl_dir: Path, change_info: ChangeInfo, gemini_client: GeminiClient, model_name: str, status_callback: Callable[[str, str, float], None], agents_dir: Path) -> None:
    """
    Orchestrates the multi-agent code review process.
    Uses status_callback(agent_name, status, elapsed_time) to report progress to the UI.
    """
    # Initialize the centralized logger
    logger = _create_logger(cl_dir)
    logger("=== Starting Review Engine ===")

    # 1. Read the agents
    agents: List[tuple[str, str]] = []

    if agents_dir.is_dir():
        for file_path in agents_dir.glob("*.md"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    agent_prompt = f.read().strip()
                    agent_prompt += f"\n\n{COMMON_AGENT_INSTRUCTION}\n"
                    agents.append((file_path.stem, agent_prompt))
            except Exception as e:
                logger(f"Failed to read agent prompt {file_path.name}: {e}")

    if not agents:
        logger("Error: No agent prompts (.md files) found.")
        return

    # Run all agents
    logger(f"DEBUG: Running with all agents: {[a[0] for a in agents]}")

    # 2. Build the initial core context (prevents context stuffing)
    document_text = read_directory_context(cl_dir, core_only=True)
    if not document_text.strip():
        logger("Error: Context is empty.")
        return

    save_file(cl_dir / "full_context", document_text)

    # 3. Create cache
    logger(f"Creating Gemini context cache using {model_name}...")
    cache_name = gemini_client.create_cached_content(model_name, document_text, ttl_seconds=3600, tools=TOOLS, logger=logger)

    if not cache_name:
        logger("Caching failed or unsupported. Falling back to direct API requests...")
    else:
        logger(f"Cache created: {cache_name}")

    # 4. State tracking for UI callback
    start_times = {name: time.time() for name, _ in agents}

    def thread_safe_callback(name: str, status: str):
        elapsed = time.time() - start_times[name]
        status_callback(name, status, elapsed)

    # 5. Run agents in parallel
    results: List[AgentReview] = []
    max_workers = 2  # Reduced from 5 to stay within token quota during agentic loops

    # Initialize all as Pending for the UI
    for name, _ in agents:
        status_callback(name, "Pending", 0.0)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_agent = {
            executor.submit(
                _run_single_agent,
                agent_name,
                prompt,
                document_text,
                cache_name,
                gemini_client,
                model_name,
                thread_safe_callback,
                change_info,
                cl_dir,
                logger
            ): agent_name
            for agent_name, prompt in agents
        }

        for future in concurrent.futures.as_completed(future_to_agent):
            try:
                review = future.result()
                results.append(review)
            except Exception as exc:
                agent_name = future_to_agent[future]
                logger(f"[{agent_name}] Agent process threw an exception: {exc}")
                results.append(AgentReview(agent_name=agent_name, response_text=None, status="Failed", error_message=str(exc)))

    # 6. Cleanup cache
    if cache_name:
        logger(f"Cleaning up cache: {cache_name}")
        gemini_client.delete_cached_content(cache_name, logger=logger)

    logger("=== Review Engine Complete ===")

    # 7. Aggregate and save results
    md_output = []

    # Sort results to be deterministic
    results.sort(key=lambda x: x.agent_name)

    for review in results:
        md_output.append(f"## Review by '{review.agent_name}'")
        if review.status == "Done" and review.response_text:
            md_output.append(review.response_text)
        else:
            md_output.append(f"*(Agent failed to generate review: {review.error_message})*")

    final_output = "\n\n---\n\n".join(md_output)
    out_file = cl_dir / "code_review.md"
    save_file(out_file, final_output)
