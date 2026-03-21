Based on the code change, the provided project tree, and the detailed summary you just created (provided in the context as CHANGE SUMMARY),
determine which other files in the repository would be useful to add to the context.

Your goal is to provide the code review agents with as much surrounding context as possible. **Adding dozens of files is perfectly fine and encouraged.**
Err heavily on the side of inclusion.

- **HEADER DISCOVERY:** Scan the provided diff and modified files for `#include` statements, type names, namespaces, and function calls.
  You MUST add every included local header to the `extra_context_files` list. (e.g., `#include "path/to/my_class.h"` adds `path/to/my_class.h` to the list)
- **BROAD SWEEP:** Use the provided `project_tree` file to find *anything* remotely relevant. Include:
  - All related interface declarations, base classes, and subclasses.
  - Sibling implementations, utility functions, or data structures in the same directory.
  - Files that share a similar naming prefix or suffix.
  - Files involved in the same architectural layer or pipeline.
  - Any test files (`*_unittest.cc`, `*_test.py`, etc.) related to the modified components, even if they weren't explicitly changed.
- **HISTORICALLY RELATED FILES:** Pay special attention to the "Historically Related Files" section at the bottom of the `project_tree`.
  These files have a proven track record of changing together in the past. You need to prioritize including these files in your `extra_context_files` list,
  as they are highly likely to contain relevant dependencies, tests, or coupled logic.
- **DOCUMENTATION (CRITICAL):** Vigorously search the `project_tree` for relevant documentation files (`.md`, `.txt`, design docs, architectural overviews). If a component is changed, include the directory's `README.md` or related system design docs.

IMPORTANT: You must return the output STRICTLY as a plain text list of file paths, with exactly one file path per line (e.g., docs/design/architecture.md). Do not include bullet points, prefixes, markdown formatting, or any explanations. Just the file paths.
