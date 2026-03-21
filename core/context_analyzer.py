"""
Analyzes the codebase to find missing context using the LLM.
"""

import json
from pathlib import Path
from typing import Optional

from core.gemini_client import GeminiClient
from core.models import AnalysisResult
from core.utils import build_analysis_context, save_file
from core.exceptions import ParseError

def analyze_context(cl_dir: Path, gemini_client: GeminiClient, model_name: str, agents_dir: Path) -> Optional[AnalysisResult]:
    """
    Reads the downloaded files and asks the LLM to identify the project and recommend
    additional context files needed for a full review.
    """
    print(f"Reading files in '{cl_dir}' for analysis...")
    document_text = build_analysis_context(cl_dir)

    if not document_text.strip():
        print("No valid files found to analyze.")
        return None

    # Load prompts
    prompt_path = Path(__file__).parent.parent / "prompts" / "preview_change.md"
    extra_context_prompt_path = Path(__file__).parent.parent / "prompts" / "extra_context.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            summary_prompt = f.read()
        with open(extra_context_prompt_path, "r", encoding="utf-8") as f:
            extra_context_prompt = f.read()
    except Exception as e:
        print(f"Error reading prompt files: {e}")
        return None

    print(f"Sending summary request to Gemini API ({model_name})...")

    # We don't cache here because this is a one-off request
    summary_text = gemini_client.generate_content(
        model_name=model_name,
        prompt=summary_prompt,
        document_text=document_text
    )

    if not summary_text:
        print("Failed to get summary from Gemini API.")
        return None

    print(f"Sending extra context request to Gemini API ({model_name})...")
    
    # Append the summary to the document text for the second call
    extended_document_text = document_text + f"\n\n--- CHANGE SUMMARY ---\n{summary_text}\n"

    extra_context_response = gemini_client.generate_content(
        model_name=model_name,
        prompt=extra_context_prompt,
        document_text=extended_document_text
    )

    if not extra_context_response:
        print("Failed to get extra context from Gemini API.")
        return None

    # Parse plain text list of files
    clean_text = extra_context_response.strip()
    
    # Remove markdown code block markers if the model accidentally included them
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if len(lines) > 1:
            clean_text = "\n".join(lines[1:])
    if clean_text.endswith("```"):
        lines = clean_text.splitlines()
        if len(lines) > 1:
            clean_text = "\n".join(lines[:-1])

    extra_files = [line.strip() for line in clean_text.splitlines() if line.strip()]

    analysis = AnalysisResult(
        summary=summary_text.strip(),
        extra_context_files=extra_files
    )

    # Save output files
    save_file(cl_dir / "summary", analysis.summary)
    save_file(cl_dir / "extra_context_files", "\n".join(analysis.extra_context_files) + "\n")

    print("\nAnalysis complete!")
    print(f"Saved summary to {cl_dir / 'summary'}")
    print(f"Saved context files to {cl_dir / 'extra_context_files'}")

    return analysis
