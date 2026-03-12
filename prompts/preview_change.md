Please analyze this code change based on the provided files.

1. **Identify the Project:** First, determine which software project this change belongs to based on the file paths, commit info, or code content (e.g., Chromium, Android, V8).
2. **Create a Summary:** Provide a detailed summary of the change and its core logic.
3. **Identify Context Files:** Based on the identified project and the code changes, determine which other files in the repository would be highly useful to add to the context for a thorough code review by the agents listed above.
   - **CRITICAL - HEADER DISCOVERY:** Scan the provided diff and modified files for `#include` statements and type names. If a modified file includes a local header (e.g., `#include "path/to/my_class.h"`), you MUST add `"path/to/my_class.h"` to the `extra_context_files` list. Additionally, if the changes heavily rely on a specific class or utility, try to infer and include its corresponding `.h` and `.cc`/`.cpp` files, even if those paths do not explicitly appear in the `project_tree`.
   - You are provided with a file named `project_tree` in the context. This file lists the neighboring files in the repository structure. Use this list to find actual file paths that exist in the project.
   - Look for files in the `project_tree` that contain relevant interface declarations, base classes, and definitions of utility functions or data structures that are heavily utilized in the modified code.
   - **CRITICAL:** Strongly emphasize finding and including relevant documentation files (e.g., `.md` and `.txt` files, architectural docs, or design documents) that are referenced by or conceptually related to these changes.
   - It is better to err on the side of including files rather than excluding them. Add any files that might be helpful for the code review agents.

IMPORTANT: You must return the output STRICTLY as a valid JSON object with EXACTLY two keys:
- "summary": A string containing a detailed summary of the change.
- "extra_context_files": A list of strings, where each string is exactly the file path (e.g., "docs/design/architecture.md" or "path/to/code/file.cc").
Do not include any other text, markdown formatting (like ```json), or explanations outside the JSON object.

--- START CONTEXT ---