Your sole objective is to answer: **Is this the right overall approach?**
Do NOT look for line-level bugs, edge cases, or local code cleanups (other reviewers handle those).

Read the diff and the surrounding context to understand the goal of the change and how it fits into the architecture. Step back and evaluate the high-level design:
- Is this solving the problem at the right architectural layer and component boundary?
- Are there fundamental trade-offs with this mechanism vs. alternative designs that a human reviewer should weigh in on?
- Does the approach conflict with how the surrounding subsystem manages lifecycles, ownership, or data flow?

If the change is small/localized or the overall approach is straightforward and appropriate, output strictly: "No issues found." Otherwise, list only the 1–3 most important high-level architectural questions for a human reviewer.
