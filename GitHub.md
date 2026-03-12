# GitHub PR Support Integration Plan

DeepReview will be extended to support GitHub Pull Requests (PRs) alongside Gerrit. This document outlines the integration plan and technical specifications for the GitHub REST API.

## Integration Plan

1.  **Generalize Data Models**: Update `ChangeInfo` in `core/models.py` to be platform-agnostic.
2.  **Generic Client Interface**: Define `BaseClient` in `core/base_client.py` as an abstract base class.
3.  **GitHub Implementation**: Create `GitHubClient` in `core/github_client.py` implementing the `BaseClient` interface.
4.  **Refactor Gerrit Client**: Update `GerritClient` to implement the `BaseClient` interface.
5.  **Enhanced URL Parsing**: Update `core/change_fetcher.py` to recognize GitHub PR URLs and instantiate the correct client.
6.  **Orchestrator Updates**: Update `main.py` to handle `GITHUB_TOKEN` and coordinate the review flow for GitHub PRs.

## Technical Details: GitHub REST API

The `GitHubClient` will utilize the following GitHub REST API v3 endpoints.

### 1. Fetching Pull Request Metadata
- **Endpoint**: `GET /repos/{owner}/{repo}/pulls/{pull_number}`
- **Usage**: Retrieve the PR subject, body, author, base branch, and head commit SHA.

### 2. Fetching the Patch/Diff
- **Endpoint**: `GET /repos/{owner}/{repo}/pulls/{pull_number}`
- **Header**: `Accept: application/vnd.github.v3.diff`
- **Usage**: Downloads the unified diff for the entire PR.

### 3. Fetching Changed Files List
- **Endpoint**: `GET /repos/{owner}/{repo}/pulls/{pull_number}/files`
- **Usage**: Identify which files were added, modified, or deleted in the PR.

### 4. Fetching Original File Contents
- **Endpoint**: `GET /repos/{owner}/{repo}/contents/{path}?ref={base_sha}`
- **Usage**: Retrieve the base version of a file (prior to the PR changes) for context.
- **Decoding**: File content is returned as a base64-encoded string.

### 5. Fetching Directory Trees (Context Discovery)
- **Endpoint**: `GET /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1`
- **Usage**: Discover the project structure to identify relevant context files (headers, documentation).

### Authentication and Limits
- **Header**: `Authorization: Bearer <GITHUB_TOKEN>`
- **Rate Limit**: Authenticated requests allow up to 5,000 requests per hour.
- **Pagination**: Use the `per_page` and `page` parameters for endpoints returning lists (e.g., changed files) if necessary.

## Implementation Considerations
- **Environment Variable**: Use `GITHUB_TOKEN` for API authentication.
- **Error Handling**: Handle 404 (Not Found), 403 (Rate Limit), and 401 (Unauthorized) errors gracefully.
- **URL Formats**: Support standard formats like `https://github.com/owner/repo/pull/123`.
