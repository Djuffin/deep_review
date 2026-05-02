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
usage: main.py [-h] [--out-dir OUT_DIR] [--model MODEL] [--persona] url

positional arguments:
  url                Gerrit CL URL or numeric ID

options:
  -h, --help         show this help message and exit
  --out-dir OUT_DIR  Directory to save files (defaults to CL ID)
  --model MODEL      The Gemini model to use for analysis and review.
                     Acceptable values: gemini-3.1-pro-preview, gemini-3-flash-preview,
                     gemini-3.1-flash-lite-preview (default: gemini-3-flash-preview)
  --persona          Use famous programmer personas for review (e.g., Linus Torvalds, James Gosling)
```

## License

MIT License

Copyright (c) 2026 Eugene Zemtsov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
