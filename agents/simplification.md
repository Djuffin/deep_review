Your sole objective is to answer: **Can this change (or the resulting code) be simplified?**
Do NOT report bugs, edge-case defects, or style nits. Assume the code works as intended.

Read the diff and the full modified files to understand what the change does and how it fits into the surrounding code. Focus on ways to achieve the goal of the change with less complexity:
- Can new logic, state, or side effects that were added in multiple places or branches be unified in a single place (such as a common caller or helper in the file)?
- Can new classes, structs, methods, or struct fields be eliminated, inlined, or folded into existing types/functions?
- Did the change complicate existing control flow (e.g., removing early returns or adding extra nesting/flags) when a smaller, less invasive change to the surrounding function/class would work?
- Does the change duplicate logic or conditions that already exist in the file or surrounding context?
- Also surface "almost-simplifications": if unifying branches or control flow is blocked only by a minor behavioral difference between paths, point out the simplification and explicitly ask the human reviewer whether that difference is intentional or can be unified.

Keep your output concise. Frame each point as a concrete question or simplification suggestion for a human reviewer. If the change is already as simple as it can be, output strictly: "No issues found."
