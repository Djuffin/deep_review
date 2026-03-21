1. **Review logic of the code:** Focus on:
        - **Algorithmic Correctness:** Does the implementation actually fulfill the requirements? Are there any logical leaps or flaws?
        - **Edge Cases & Boundaries:** What happens with zero-values, empty collections, extremely large inputs, or unexpected null states?
        - **State Management:** If the code manages state, are the transitions logical? Is it possible to get stuck in an invalid state?
2. **Review the implementation details and style:** Pay special attention to:
        - **Memory safety:** Watch for use-after-free, dangling pointers, and out-of-bounds access. Ensure raw pointers do not take ownership.
        - **Buffer Safety:** Enforce rules around `UNSAFE_BUFFERS` and `UNSAFE_TODO`. Flag C-style arrays or raw pointer arithmetic; suggest `base::span`.
        - **Undefined Behavior:** Flag signed integer overflow and uninitialized variables.
        - **Thread Safety:**  Watch for data races, deadlocks & lock ordering.
        - **Error Handling** Look for unhandled errors
        - **Performance:** Look for pass-by-reference efficiencies, correct move semantics (`std::move`), loop copies
        - **Typos:** Catch misleading comments or typos.
