"""
Command Line Interface and Orchestrator for the Code Review System.
"""

import sys
import os
import time
import threading
import argparse
from pathlib import Path

from core.gemini_client import GeminiClient
from core.change_fetcher import fetch_change, parse_gerrit_url
from core.context_analyzer import analyze_context
from core.extra_context_fetcher import fetch_extra_context
from core.review_engine import run_review

def print_header(title: str):
    print(f"\n{'='*50}")
    print(f"--- {title} ---")
    print(f"{'='*50}")

class ReviewDashboard:
    """Manages the live CLI dashboard for the parallel review agents."""
    def __init__(self):
        self.agent_states = {}
        self.active = False
        self.lock = threading.Lock()
        self.thread = None

    def update_status(self, agent_name: str, status: str, elapsed: float):
        with self.lock:
            # If transitioning to Running, record the start time to calculate elapsed dynamically
            if status == 'Running' and self.agent_states.get(agent_name, {}).get('status') != 'Running':
                self.agent_states[agent_name] = {'status': status, 'start_time': time.time(), 'elapsed': 0.0}
            else:
                # Keep the start time if it's already running, just update the status/final elapsed
                start_time = self.agent_states.get(agent_name, {}).get('start_time', time.time())
                self.agent_states[agent_name] = {'status': status, 'start_time': start_time, 'elapsed': elapsed}

    def _render_loop(self):
        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        
        while self.active:
            with self.lock:
                if not self.agent_states:
                    continue
                    
                # Move cursor up to the top of the dashboard
                num_agents = len(self.agent_states)
                sys.stdout.write(f"\033[{num_agents + 2}A")
                
                print("-" * 40 + "\033[K")
                for name in sorted(self.agent_states.keys()):
                    state = self.agent_states[name]
                    status = state['status']
                    
                    if status == 'Running':
                        # Calculate elapsed time dynamically for Running state
                        current_elapsed = time.time() - state.get('start_time', time.time())
                        print(f"[\033[93m~\033[0m] {name:<20} | Running ({current_elapsed:.1f}s)\033[K")
                    elif status == 'Done':
                        print(f"[\033[92m✓\033[0m] {name:<20} | Done ({state['elapsed']:.1f}s)\033[K")
                    elif status == 'Failed':
                        print(f"[\033[91mx\033[0m] {name:<20} | Failed ({state['elapsed']:.1f}s)\033[K")
                    else:
                        print(f"[ ] {name:<20} | {status}\033[K")
                print("-" * 40 + "\033[K")
            time.sleep(0.2)
            
        # Restore cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    def start(self, num_agents: int):
        self.active = True
        # Allocate empty lines for the dashboard to overwrite
        print("\n" * (num_agents + 2))
        self.thread = threading.Thread(target=self._render_loop)
        self.thread.start()

    def stop(self):
        self.active = False
        if self.thread:
            self.thread.join()

def main():
    parser = argparse.ArgumentParser(description="Automated LLM-based Code Review System")
    parser.add_argument("url", help="Gerrit CL URL or numeric ID")
    parser.add_argument("--out-dir", type=str, help="Directory to save files (defaults to CL ID)")
    parser.add_argument("--model", type=str, default="gemini-3-flash-preview", 
                        help="The Gemini model to use for analysis and review (default: gemini-3-flash-preview)")
    
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    try:
        _, cl_id = parse_gerrit_url(args.url)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    output_dir = Path(args.out_dir) if args.out_dir else Path(cl_id)
    gemini_client = GeminiClient(api_key=api_key)
    model_name = args.model

    try:
        # Step 1: Fetch Change
        print_header(f"Fetching Change {cl_id}")
        change_info = fetch_change(args.url, output_dir)

        # Step 2: Analyze Context
        print_header(f"Analyzing Context ({model_name})")
        analysis = analyze_context(output_dir, gemini_client, model_name)
        
        if not analysis:
            print("Failed to analyze context. Aborting.")
            sys.exit(1)

        # Step 3: Fetch Extra Context
        print_header("Loading Extra Context")
        fetch_extra_context(output_dir, change_info, analysis)

        # Step 4: Perform Review
        print_header(f"Performing Multi-Agent Code Review ({model_name})")
        
        # Count agents to allocate dashboard space
        agents_dir = Path(__file__).parent / "agents"
        num_agents = len(list(agents_dir.glob("*.md"))) if agents_dir.is_dir() else 0
        
        if num_agents == 0:
            print("No agents found. Skipping review.")
            sys.exit(0)

        dashboard = ReviewDashboard()
        dashboard.start(num_agents)

        run_review(
            cl_dir=output_dir, 
            gemini_client=gemini_client, 
            model_name=model_name,
            status_callback=dashboard.update_status
        )

        dashboard.stop()

        print(f"\n{'+'*50}")
        print(f"SUCCESS: Pipeline complete!")
        print(f"Check the '{output_dir / 'code_review.md'}' file for the final results.")
        print(f"{'+'*50}")

    except Exception as e:
        print(f"\n[!] Pipeline failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
