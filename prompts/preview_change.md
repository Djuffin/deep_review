Please analyze this code change based on the provided files.

1. **Identify the Project:** First, determine what software project this change belongs to based on the file paths, commit info, or code content (e.g., Chromium, Android, V8).
2. **Create a Summary:** Provide a detailed summary of the change and its core logic.
3. **Identify Context Files:** Based on the identified project and the code changes, figure out what other files in the repository would be highly useful to add to the context for a thorough code review.
   - Look for files containing relevant interface declarations, base classes, and the definitions of utility functions or data structures that are heavily utilized in the modified code.
   - Use your knowledge of the project's codebase to add most important and relevant files.
   - **CRITICAL:** Strongly emphasize finding and including relevant documentation files (e.g., `.md` and `.txt` files, architectural docs, or design documents) that are referenced or conceptually related to these changes.

IMPORTANT: You must return the output STRICTLY as a valid JSON object with EXACTLY two keys:
- "summary": A string containing the detailed summary of the change.
- "extra_context_files": A list of strings, where each string is just the file path (e.g., "docs/design/architecture.md" or "path/to/code/file.cc").
Do not include any other text, markdown formatting like ```json, or explanations outside the JSON object.

--- START CONTEXT ---

