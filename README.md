# DeepReview

**DeepReview** is an automated, multi-agent AI code review system for Gerrit. It uses the Gemini Context Caching API to perform deep, parallelized code analysis.

Unlike basic AI diff-checkers, DeepReview automatically discovers and fetches missing architectural context (interfaces, base classes, docs) directly from your repository *before* reviewing.

## Quick Start

1. Export your API key:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

2. Run against a Gerrit CL:
   ```bash
   python3 main.py https://chromium-review.googlesource.com/c/chromium/src/+/7219003
   ```

3. Read the generated `final_summary.md` and `code_review.md` inside the output directory.

## How It Works

1. **Fetch:** Downloads the diff and modified files from Gerrit.
2. **Contextualize:** Uses Gemini to identify and download necessary missing files (headers, docs).
3. **Review:** Uploads the entire context to Gemini's Cache and runs multiple specialized AI agents (e.g., Memory Safety, Concurrency) in parallel to review the code.

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
  url                Gerrit CL URL or numeric ID

options:
  -h, --help         show this help message and exit
  --out-dir OUT_DIR  Directory to save files (defaults to CL ID)
  --model MODEL      The Gemini model to use for analysis and review (default: gemini-3-flash-preview)
  --mock             Use mock agents and gemini-3.1-flash-lite-preview for faster testing
```
