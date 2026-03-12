"""
Gerrit API client.
"""

import json
import base64
import urllib.parse
import urllib.request
import urllib.error
from typing import Dict, Any

from core.exceptions import GerritAPIError, ParseError

class GerritClient:
    def __init__(self, host: str):
        """
        Initializes the client.
        :param host: e.g., 'chromium-review.googlesource.com'
        """
        self.host = host
        self.base_url = f"https://{self.host}/changes"

    def _make_request(self, endpoint: str) -> bytes:
        """Helper to make a raw GET request to the Gerrit API."""
        url = f"{self.base_url}/{endpoint}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            raise GerritAPIError(f"HTTP Error fetching {url}", status_code=e.code, details=e.reason)
        except Exception as e:
            raise GerritAPIError(f"Failed to fetch {url}: {e}")

    def get_json(self, endpoint: str) -> Dict[str, Any]:
        """
        Fetches data from Gerrit and parses the JSON.
        Automatically strips the XSSI magic string `)]}'`.
        """
        raw_bytes = self._make_request(endpoint)
        try:
            data_str = raw_bytes.decode('utf-8')
            if data_str.startswith(")]}'"):
                data_str = data_str[4:]
            return json.loads(data_str)
        except json.JSONDecodeError as e:
            raise ParseError(f"Failed to parse JSON from Gerrit: {e}")
        except Exception as e:
            raise ParseError(f"Failed to decode Gerrit response: {e}")

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

    def fetch_gitiles_directory(self, project: str, commit_id: str, dir_path: str, gitiles_commit_url: str = "") -> Dict[str, Any]:
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
        
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as response:
                raw_bytes = response.read()
                data_str = raw_bytes.decode('utf-8')
                if data_str.startswith(")]}'"):
                    data_str = data_str[4:]
                return json.loads(data_str)
        except urllib.error.HTTPError as e:
            # It's normal for some directories to not exist in older commits or if we guessed a path incorrectly
            if e.code == 404:
                return {"entries": []}
            raise GerritAPIError(f"HTTP Error fetching {url}", status_code=e.code, details=e.reason)
        except Exception as e:
            raise GerritAPIError(f"Failed to fetch {url}: {e}")
