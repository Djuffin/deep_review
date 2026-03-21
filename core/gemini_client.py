"""
Gemini API client.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

from core.exceptions import GeminiAPIError, ParseError

class GeminiClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key must be provided")
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, method: str = 'POST', timeout: int = 600) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint}?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        req_data = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.getcode() == 204: # No content (e.g. for DELETE)
                    return {}
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            raise GeminiAPIError(
                f"Gemini API HTTP {e.code}: {e.reason}", 
                status_code=e.code, 
                details=error_body
            )
        except Exception as e:
            raise GeminiAPIError(f"Failed to communicate with Gemini API: {e}")

    def create_cached_content(self, model_name: str, document_text: str, ttl_seconds: int = 600) -> Optional[str]:
        """
        Uploads document text to create a cached context.
        Returns the cache name (e.g., 'cachedContents/xyz') or None if it fails.
        """
        data = {
            "model": f"models/{model_name}",
            "contents": [
                {
                    "parts": [{"text": document_text}],
                    "role": "user"
                },
                {
                    "parts": [{"text": "Context received. I am ready to review the changes based on this context."}],
                    "role": "model"
                }
            ],
            "ttl": f"{ttl_seconds}s"
        }
        
        try:
            result = self._make_request("cachedContents", data=data)
            return result.get('name')
        except GeminiAPIError as e:
            # We don't want to crash the whole app if caching fails (e.g., context too small)
            # We will log the error and allow the app to fallback to a direct request.
            # In a full app, we might use a proper logger here.
            print(f"[Warning] Failed to create cache: {e}")
            return None

    def delete_cached_content(self, cache_name: str) -> None:
        """Deletes a cached context by name."""
        try:
            self._make_request(cache_name, method='DELETE')
        except GeminiAPIError as e:
            print(f"[Warning] Failed to delete cache {cache_name}: {e}")

    def generate_content(
        self, 
        model_name: str, 
        prompt: str, 
        document_text: Optional[str] = None, 
        cache_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: int = 600
    ) -> Optional[str]:
        """
        Generates content from the model. Can use either a cached context or direct document text.
        Returns response_text.
        """
        data = {
            "contents": [{
                "parts": [{"text": prompt}],
                "role": "user"
            }],
            "generationConfig": {
                "temperature": temperature
            }
        }
        
        if cache_name:
            data["cachedContent"] = cache_name
        elif document_text:
            data["contents"][0]["parts"].insert(0, {"text": document_text + "\n\n"})
            
        endpoint = f"models/{model_name}:generateContent"
        
        try:
            result = self._make_request(endpoint, data=data, timeout=timeout)
            
            # Extract text
            try:
                text = result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                raise ParseError(f"Unexpected response structure: {json.dumps(result)}")
            
            return text
            
        except GeminiAPIError as e:
            print(f"Error calling Gemini API: {e}")
            if e.details:
                print(f"Details: {e.details}")
            return None
        except ParseError as e:
            print(f"Error parsing Gemini response: {e}")
            return None
