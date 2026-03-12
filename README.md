# DeepReview

**DeepReview** is an automated, multi-agent AI code review system. It uses the Gemini Context Caching API and **Agentic Tool-Use** to perform deep, parallelized code analysis.

Unlike basic AI diff-checkers that only see the changed lines, DeepReview agents are equipped with tools (`search_files`, `get_function`, `read_lines`) to autonomously navigate and investigate the full codebase on-demand.

## Quick Start

1. Export your API key:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

2. Run against a Gerrit CL (Remote Mode):
   ```bash
   python3 main.py https://chromium-review.googlesource.com/c/chromium/src/+/7219003
   ```

3. **OR** Run against your local repository (Local Mode):
   ```bash
   python3 main.py /path/to/your/local/chromium/src
   ```

4. Read the generated `final_summary.md` and `code_review.md` inside the output directory. Check `agent_activity.log` to see exactly how the agents navigated the codebase!

## How It Works

1. **Fetch:** Generates a diff and builds a directory map (`project_tree`) from Gerrit or your local git checkout.
2. **Review:** Uploads the initial context to Gemini's Cache. Multiple specialized AI agents (e.g., Memory Safety, Concurrency) run in parallel, using their tools to fetch full functions, search for references, and read lines dynamically.
3. **Summarize:** Consolidates all agent findings into a final report.

## Custom Agents

Add `.md` files to the `agents/` directory to create new reviewers. The filename becomes the agent's name.

```markdown
# agents/security.md
Review the provided code strictly for security vulnerabilities (SQLi, XSS). Provide only negative feedback with file/line references.
```

## Usage

```text
usage: main.py [-h] [--out-dir OUT_DIR] [--model MODEL] [--mock] url

positional arguments:
  url                Gerrit CL URL, numeric ID, or path to a local Git repository.

options:
  -h, --help         show this help message and exit
  --out-dir OUT_DIR  Directory to save files (defaults to CL ID or 'local')
  --model MODEL      The Gemini model to use for analysis and review (default: gemini-3-flash-preview)
  --mock             Use mock agents and gemini-3.1-flash-lite-preview for faster testing
```