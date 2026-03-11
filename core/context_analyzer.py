"""
Analyzes the codebase to find missing context using the LLM.
"""

import json
from pathlib import Path
from typing import Optional

from core.gemini_client import GeminiClient
from core.models import AnalysisResult
from core.utils import read_directory_context, save_file
from core.exceptions import ParseError

def analyze_context(cl_dir: Path, gemini_client: GeminiClient, model_name: str) -> Optional[AnalysisResult]:
    """
    Reads the downloaded files and asks the LLM to identify the project and recommend
    additional context files needed for a full review.
    """
    print(f"Reading files in '{cl_dir}' for analysis...")
    document_text = read_directory_context(cl_dir)
    
    if not document_text.strip():
        print("No valid files found to analyze.")
        return None

    # Load prompt
    prompt_path = Path(__file__).parent.parent / "prompts" / "preview_change.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read()
    except Exception as e:
        print(f"Error reading prompt file from {prompt_path}: {e}")
        return None

    print(f"Sending request to Gemini API ({model_name})...")
    
    # We don't cache here because this is a one-off request
    response_text = gemini_client.generate_content(
        model_name=model_name,
        prompt=prompt,
        document_text=document_text
    )

    if not response_text:
        print("Failed to get analysis from Gemini API.")
        return None

    # Parse JSON
    try:
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]

        result_data = json.loads(clean_text)

        analysis = AnalysisResult(
            summary=result_data.get("summary", "Summary not provided."),
            extra_context_files=result_data.get("extra_context_files", [])
        )
        
        # Save output files
        save_file(cl_dir / "summary", analysis.summary)
        save_file(cl_dir / "extra_context_files", "\n".join(analysis.extra_context_files) + "\n")
        
        print("\nAnalysis complete!")
        print(f"Saved summary to {cl_dir / 'summary'}")
        print(f"Saved context files to {cl_dir / 'extra_context_files'}")
        
        return analysis

    except json.JSONDecodeError as e:
        print(f"Error: The model did not return a valid JSON response. ({e})")
        print(f"Raw output:\n{response_text}")
        return None
