"""
Gemini API client.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple, List, Callable

from core.exceptions import GeminiAPIError, ParseError

class GeminiClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key must be provided")
        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _make_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None, method: str = 'POST', timeout: int = 120, logger: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        """Helper to make a raw JSON request to the Gemini API with exponential backoff for 429s."""
        import time # Ensure time is available for sleep
        import random # Add random for jitter
        
        url = f"{self.base_url}/{endpoint}?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        req_data = json.dumps(data).encode('utf-8') if data else None
        
        max_retries = 8
        base_delay = 2 # Start with 2 seconds
        retriable_codes = {429, 500, 502, 503, 504}
        
        for attempt in range(max_retries):
            req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
            try:
                if logger:
                    logger(f"  [API Request] {method} {endpoint} (Attempt {attempt+1}/{max_retries})")
                
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.getcode() == 204: # No content (e.g. for DELETE)
                        return {}
                    return json.loads(response.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                
                if e.code in retriable_codes and attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 4)
                    if logger:
                        logger(f"  [API {e.code} Error] Retrying in {delay:.1f}s: {e.reason}")
                    time.sleep(delay)
                    continue
                    
                error_msg = f"[Gemini API Error] {e.code} {e.reason}: {error_body}"
                if logger:
                    logger(error_msg)
                raise GeminiAPIError(
                    f"Gemini API HTTP {e.code}: {e.reason}", 
                    status_code=e.code, 
                    details=error_body
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 4)
                    if logger:
                        logger(f"  [Connection Error] {e}. Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                    
                error_msg = f"[Gemini Connection Error] {e}"
                if logger:
                    logger(error_msg)
                raise GeminiAPIError(f"Failed to communicate with Gemini API: {e}")

    def create_cached_content(self, model_name: str, document_text: str, ttl_seconds: int = 600, tools: Optional[List[Dict[str, Any]]] = None, logger: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """
        Uploads document text to create a cached context.
        Returns the cache name (e.g., 'cachedContents/xyz') or None if it fails.
        """
        data = {
            "model": f"models/{model_name}",
            "contents": [{
                "parts": [{"text": document_text}],
                "role": "user"
            }],
            "ttl": f"{ttl_seconds}s"
        }

        if tools:
            data["tools"] = tools
        
        try:
            result = self._make_request("cachedContents", data=data, logger=logger)
            return result.get('name')
        except GeminiAPIError as e:
            if logger:
                logger(f"[Warning] Failed to create cache: {e}")
            return None

    def delete_cached_content(self, cache_name: str, logger: Optional[Callable[[str], None]] = None) -> None:
        """Deletes a cached context by name."""
        try:
            self._make_request(cache_name, method='DELETE', logger=logger)
        except GeminiAPIError as e:
            if logger:
                logger(f"[Warning] Failed to delete cache {cache_name}: {e}")

    def generate_content(
        self, 
        model_name: str, 
        prompt: str, 
        document_text: Optional[str] = None, 
        cache_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: int = 600,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_handlers: Optional[Dict[str, Callable]] = None,
        logger: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Generates content from the model. Support multi-turn tool calling.
        Can use either a cached context or direct document text.
        Returns response_text.
        """
        contents = []
        if document_text:
            contents.append({"role": "user", "parts": [{"text": document_text + "\n\n" + prompt}]})
        else:
            contents.append({"role": "user", "parts": [{"text": prompt}]})

        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature
            }
        }
        
        if cache_name:
            data["cachedContent"] = cache_name
            # If using cached content, the base text is already in the cache. 
            # We just append the prompt in the contents array.
            contents[0]["parts"][0]["text"] = prompt
            # Note: Tools must be in the Cache, not here, when using cachedContent.
            
        elif tools:
            # Only send tools here if we are NOT using a cache
            data["tools"] = tools

        endpoint = f"models/{model_name}:generateContent"
        
        # Multi-turn conversation loop to handle function calls
        max_turns = 40
        for turn in range(max_turns):
            try:
                if logger:
                    logger(f"  [Gemini Turn {turn+1}/{max_turns}] Sending request...")
                
                result = self._make_request(endpoint, data=data, timeout=timeout, logger=logger)
                
                if logger:
                    logger(f"  [Gemini Turn {turn+1}/{max_turns}] Response received.")
                
                # Extract parts from the response
                try:
                    candidate = result['candidates'][0]
                    content = candidate['content']
                    parts = content.get('parts', [])
                except (KeyError, IndexError):
                    raise ParseError(f"Unexpected response structure: {json.dumps(result)}")

                function_call = None
                text_response = ""
                for part in parts:
                    if 'functionCall' in part:
                        function_call = part['functionCall']
                    elif 'text' in part:
                        text_response += part['text']

                if function_call and tool_handlers:
                    name = function_call.get('name')
                    args = function_call.get('args', {})
                    
                    if logger:
                        logger(f"[Agent Tool Call] {name}({json.dumps(args)})")
                    
                    if name in tool_handlers:
                        try:
                            func_res = tool_handlers[name](**args)
                            tool_result = {"result": str(func_res)}
                        except Exception as e:
                            tool_result = {"error": str(e)}
                            if logger:
                                logger(f"[Agent Tool Call Error] {e}")
                    else:
                        tool_result = {"error": f"Unknown tool: {name}"}

                    # Append model's response to history
                    if 'role' not in content:
                        content['role'] = 'model'
                    data["contents"].append(content)
                    
                    # Append function response to history
                    data["contents"].append({
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": name,
                                "response": tool_result
                            }
                        }]
                    })
                    continue
                else:
                    return text_response
                    
            except GeminiAPIError as e:
                # Store the error message in the return value so it can be reported by the agent
                error_ret = f"ERROR: Gemini API Error: {e.details if e.details else str(e)}"
                if logger:
                    logger(error_ret)
                return error_ret
            except ParseError as e:
                error_ret = f"ERROR: Parse Error: {str(e)}"
                if logger:
                    logger(error_ret)
                return error_ret
        
        error_ret = "ERROR: Max tool loop iterations reached (40)."
        if logger:
            logger(error_ret)
        return error_ret
