"""
Gerrit API client.
"""

import json
import time
import base64
import random
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from core.exceptions import GerritAPIError, ParseError

class GerritClient:
    def __init__(self, host: str, min_delay_seconds: float = 0.2):
        """
        Initializes the client.
        :param host: e.g., 'chromium-review.googlesource.com'
        :param min_delay_seconds: Minimum time to wait between API requests.
        """
        self.host = host
        self.base_url = f"https://{self.host}/changes"
        self.min_delay_seconds = min_delay_seconds
        self._last_request_time = 0.0

    def _execute_request(self, url: str) -> bytes:
        """Helper to make a raw GET request with proactive throttling and retries."""
        req = urllib.request.Request(url)
        max_retries = 5
        
        for attempt in range(max_retries):
            # Proactive throttling
            now = time.time()
            time_since_last = now - self._last_request_time
            if time_since_last < self.min_delay_seconds:
                time.sleep(self.min_delay_seconds - time_since_last)
            
            self._last_request_time = time.time()

            try:
                with urllib.request.urlopen(req) as response:
                    return response.read()
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < max_retries - 1:
                    retry_after = e.headers.get('Retry-After')
                    if retry_after and retry_after.isdigit():
                        sleep_time = int(retry_after)
                    else:
                        sleep_time = (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(sleep_time)
                    continue
                # If it's not 429 or we ran out of retries, re-raise the HTTPError
                raise e
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep((2 ** attempt) + random.uniform(0, 0.5))
                    continue
                raise GerritAPIError(f"Failed to fetch {url}: {e}")

    def _make_request(self, endpoint: str) -> bytes:
        """Helper to make a raw GET request to the Gerrit API endpoints."""
        url = f"{self.base_url}/{endpoint}"
        try:
            return self._execute_request(url)
        except urllib.error.HTTPError as e:
            raise GerritAPIError(f"HTTP Error {e.code} fetching {url}: {e.reason}", status_code=e.code, details=e.reason)

    def _execute_json_request(self, url: str, default_on_404: Optional[Any] = None) -> Dict[str, Any]:
        """Executes a request and parses the JSON, handling 404s with an optional default value."""
        try:
            raw_bytes = self._execute_request(url)
        except urllib.error.HTTPError as e:
            if e.code == 404 and default_on_404 is not None:
                return default_on_404
            raise GerritAPIError(f"HTTP Error {e.code} fetching {url}: {e.reason}", status_code=e.code, details=e.reason)
            
        try:
            data_str = raw_bytes.decode('utf-8')
            if data_str.startswith(")]}'"):
                data_str = data_str[4:]
            return json.loads(data_str)
        except json.JSONDecodeError as e:
            raise ParseError(f"Failed to parse JSON from {url}: {e}")
        except Exception as e:
            raise ParseError(f"Failed to decode response from {url}: {e}")

    def get_json(self, endpoint: str) -> Dict[str, Any]:
        """
        Fetches data from Gerrit and parses the JSON.
        Automatically strips the XSSI magic string `)]}'`.
        """
        url = f"{self.base_url}/{endpoint}"
        return self._execute_json_request(url)

    def get_base64_file(self, endpoint: str) -> bytes:
        """
        Fetches a base64 encoded response from Gerrit and decodes it to raw bytes.
        Used for fetching patch diffs and file contents.
        """
        encoded_data = self._make_request(endpoint)
        try:
            return base64.b64decode(encoded_data)
        except Exception as e:
            raise ParseError(f"Failed to decode base64 data from Gerrit: {e}")

    def fetch_change_info(self, change_id: str) -> Dict[str, Any]:
        """Fetches metadata about a specific CL."""
        endpoint = f"{change_id}?o=CURRENT_REVISION&o=CURRENT_COMMIT&o=WEB_LINKS"
        return self.get_json(endpoint)

    def fetch_changed_files(self, change_id: str) -> Dict[str, Any]:
        """Returns the list of files modified in the current revision."""
        endpoint = f"{change_id}/revisions/current/files/"
        return self.get_json(endpoint)

    def fetch_patch_diff(self, change_id: str, context_lines: int = 20) -> bytes:
        """Downloads the full unified diff for the current revision."""
        endpoint = f"{change_id}/revisions/current/patch?context={context_lines}"
        return self.get_base64_file(endpoint)

    def fetch_original_file(self, change_id: str, file_path: str) -> bytes:
        """Downloads the original file content from the base commit (parent=1)."""
        encoded_path = urllib.parse.quote(file_path, safe='')
        endpoint = f"{change_id}/revisions/current/files/{encoded_path}/content?parent=1"
        return self.get_base64_file(endpoint)

    def fetch_gitiles_directory(self, project: str, commit_id: str, dir_path: str, gitiles_commit_url: str = "", recursive: bool = False) -> Dict[str, Any]:
        """
        Fetches the contents of a directory using the Gitiles REST API.
        dir_path should be empty string for root, or a path like 'src/main'.
        """
        encoded_dir = urllib.parse.quote(dir_path, safe='') if dir_path else ""
        # Important: Gitiles requires a trailing slash to return the directory entries 
        # instead of just returning the commit info for the root.
        path_suffix = f"/{encoded_dir}/" if encoded_dir else "/"
        
        if gitiles_commit_url:
            url = f"{gitiles_commit_url.rstrip('/')}{path_suffix}?format=JSON"
        else:
            # Fallback to Gerrit plugin path if no Gitiles link is provided
            encoded_project = urllib.parse.quote(project, safe='')
            url = f"https://{self.host}/plugins/gitiles/{encoded_project}/+/{commit_id}{path_suffix}?format=JSON"
            
        if recursive:
            url += "&recursive=1"
        
        return self._execute_json_request(url, default_on_404={"entries": []})

    def fetch_file_history(self, project: str, commit_id: str, file_path: str, gitiles_commit_url: str = "", limit: int = 5) -> Dict[str, Any]:
        """Fetches the commit history for a specific file via Gitiles."""
        encoded_path = urllib.parse.quote(file_path, safe='')
        
        if gitiles_commit_url:
            # gitiles_commit_url usually looks like: https://host/project/+/commit_id
            # We need to replace the /+/commit_id part with /+log/commit_id/path
            base_url = gitiles_commit_url.split('/+/')[0]
            url = f"{base_url}/+log/{commit_id}/{encoded_path}?format=JSON&n={limit}"
        else:
            encoded_project = urllib.parse.quote(project, safe='')
            url = f"https://{self.host}/plugins/gitiles/{encoded_project}/+log/{commit_id}/{encoded_path}?format=JSON&n={limit}"

        return self._execute_json_request(url, default_on_404={"log": []})

    def fetch_commit_details(self, project: str, commit_id: str, gitiles_commit_url: str = "") -> Dict[str, Any]:
        """Fetches details of a specific commit via Gitiles, including the tree_diff."""
        if gitiles_commit_url:
            base_url = gitiles_commit_url.split('/+/')[0]
            url = f"{base_url}/+/{commit_id}?format=JSON"
        else:
            encoded_project = urllib.parse.quote(project, safe='')
            url = f"https://{self.host}/plugins/gitiles/{encoded_project}/+/{commit_id}?format=JSON"

        return self._execute_json_request(url, default_on_404={})
