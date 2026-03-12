"""
Multi-threaded code review engine using Gemini Context Caching.
"""

import os
import time
import threading
import concurrent.futures
from pathlib import Path
from typing import List, Callable, Optional

from core.gemini_client import GeminiClient
from core.models import AgentReview
from core.utils import read_directory_context, save_file

def _run_single_agent(
    agent_name: str, 
    prompt: str, 
    document_text: str, 
    cache_name: Optional[str], 
    gemini_client: GeminiClient, 
    model_name: str,
    status_callback: Callable[[str, str], None]
) -> AgentReview:
    """Worker function to run a single review agent."""
    status_callback(agent_name, "Running")
    
    try:
        response_text = gemini_client.generate_content(
            model_name=model_name,
            prompt=prompt,
            document_text=document_text if not cache_name else None,
            cache_name=cache_name
        )
        
        if response_text:
            status_callback(agent_name, "Done")
            return AgentReview(agent_name=agent_name, response_text=response_text, status="Done")
        else:
            status_callback(agent_name, "Failed")
            return AgentReview(agent_name=agent_name, response_text=None, status="Failed", error_message="Empty response")
            
    except Exception as e:
        status_callback(agent_name, "Failed")
        return AgentReview(agent_name=agent_name, response_text=None, status="Failed", error_message=str(e))


def run_review(cl_dir: Path, gemini_client: GeminiClient, model_name: str, status_callback: Callable[[str, str, float], None], agents_dir: Path) -> None:
    """
    Orchestrates the multi-agent code review process.
    Uses status_callback(agent_name, status, elapsed_time) to report progress to the UI.
    """
    # 1. Read the agents
    agents: List[tuple[str, str]] = []
    
    if agents_dir.is_dir():
        for file_path in agents_dir.glob("*.md"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    agents.append((file_path.stem, f.read()))
            except Exception as e:
                print(f"Failed to read agent prompt {file_path.name}: {e}")
                
    if not agents:
        print("Error: No agent prompts (.md files) found.")
        return

    # 2. Build the context
    document_text = read_directory_context(cl_dir)
    if not document_text.strip():
        print("Error: Context is empty.")
        return
        
    save_file(cl_dir / "full_context", document_text)
    
    # 3. Create cache
    cache_name = gemini_client.create_cached_content(model_name, document_text, ttl_seconds=600)
    
    if not cache_name:
        print("Caching failed or unsupported. Falling back to direct API requests...")

    # 4. State tracking for UI callback
    start_times = {name: time.time() for name, _ in agents}
    
    def thread_safe_callback(name: str, status: str):
        elapsed = time.time() - start_times[name]
        status_callback(name, status, elapsed)

    # 5. Run agents in parallel
    results: List[AgentReview] = []
    max_workers = min(10, len(agents))
    
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
                thread_safe_callback
            ): agent_name
            for agent_name, prompt in agents
        }
        
        for future in concurrent.futures.as_completed(future_to_agent):
            try:
                review = future.result()
                results.append(review)
            except Exception as exc:
                agent_name = future_to_agent[future]
                results.append(AgentReview(agent_name=agent_name, response_text=None, status="Failed", error_message=str(exc)))

    # 6. Cleanup cache
    if cache_name:
        gemini_client.delete_cached_content(cache_name)

    # 7. Aggregate and save results
    md_output = []
    
    # Sort results to be deterministic
    results.sort(key=lambda x: x.agent_name)
    
    for review in results:
        md_output.append(f"## Review by {review.agent_name}")
        if review.status == "Done" and review.response_text:
            md_output.append(review.response_text)
        else:
            md_output.append(f"*(Agent failed to generate review: {review.error_message})*")
            
    final_output = "\n\n---\n\n".join(md_output)
    out_file = cl_dir / "code_review.md"
    save_file(out_file, final_output)
