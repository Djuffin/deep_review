Please analyze this code change based on the provided files.

1. **Identify the Project & Broad Context:** First, determine which software project this change belongs to based on the file paths, commit info, or code content (e.g., Chromium, Android, V8).
2. **Create a Summary:** Provide a detailed summary of the change. Your summary MUST begin with a high-level description of the project itself and the specific subsystem being modified, followed by a detailed explanation of the change and its core logic.
3. **Identify Context Files (BE GENEROUS):** Based on the identified project and the code changes, determine which other files in the repository would be useful to add to the context. Your goal is to provide the code review agents with as much surrounding context as possible. **Adding dozens of files is perfectly fine and encouraged.** Err heavily on the side of inclusion.
   - **CRITICAL - HEADER DISCOVERY:** Scan the provided diff and modified files for `#include` statements, type names, namespaces, and function calls. You MUST add every local header included (e.g., `"path/to/my_class.h"`) to the `extra_context_files` list.
   - **BROAD SWEEP:** Use the provided `project_tree` file to find *anything* remotely relevant. Include:
     - All related interface declarations, base classes, and subclasses.
     - Sibling implementations, utility functions, or data structures in the same directory.
     - Files that share a similar naming prefix or suffix.
     - Files involved in the same architectural layer or pipeline.
     - Any test files (`*_unittest.cc`, `*_test.py`, etc.) related to the modified components, even if they weren't explicitly changed.
   - **DOCUMENTATION (CRITICAL):** Vigorously search the `project_tree` for relevant documentation files (`.md`, `.txt`, design docs, architectural overviews). If a component is changed, include the directory's `README.md` or related system design docs.

IMPORTANT: You must return the output STRICTLY as a valid JSON object with EXACTLY two keys:
- "summary": A string containing a detailed description of the project, subsystem, and the change itself.
- "extra_context_files": A list of strings, where each string is exactly the file path (e.g., "docs/design/architecture.md" or "path/to/code/file.cc").
Do not include any other text, markdown formatting (like ```json), or explanations outside the JSON object.

--- START CONTEXT ---
