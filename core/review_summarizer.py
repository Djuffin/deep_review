"""
Module for summarizing and deduplicating the results of multi-agent reviews.
"""

from typing import Optional
from pathlib import Path
from core.gemini_client import GeminiClient
from core.utils import save_file

def summarize_reviews(cl_dir: Path, gemini_client: GeminiClient, model_name: str) -> Optional[str]:
    """
    Reads the diff.patch and code_review.md files, and uses the LLM to deduplicate
    and summarize the findings into a final, consolidated review.
    """
    diff_path = cl_dir / "diff.patch"
    review_path = cl_dir / "code_review.md"
    summary_path = cl_dir / "summary"
    commit_info_path = cl_dir / "commit_info"
    
    if not diff_path.exists() or not review_path.exists():
        print("Error: Missing diff.patch or code_review.md for summarization.")
        return None

    # Load the raw files
    try:
        with open(diff_path, "r", encoding="utf-8") as f:
            diff_text = f.read()
        with open(review_path, "r", encoding="utf-8") as f:
            review_text = f.read()
            
        summary_text = ""
        if summary_path.exists():
            with open(summary_path, "r", encoding="utf-8") as f:
                summary_text = f.read()
                
        commit_info_text = ""
        if commit_info_path.exists():
            with open(commit_info_path, "r", encoding="utf-8") as f:
                commit_info_text = f.read()
    except Exception as e:
        print(f"Error reading files for summarization: {e}")
        return None

    # Load prompt
    prompt_path = Path(__file__).parent.parent / "prompts" / "review_summary.md"
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt = f.read().strip()
    except Exception as e:
        print(f"Error reading prompt file from {prompt_path}: {e}")
        return None

    document_text = (
        f"--- commit_info ---\n{commit_info_text}\n\n"
        f"--- summary ---\n{summary_text}\n\n"
        f"--- code_review.md ---\n{review_text}\n\n"
        f"--- diff.patch ---\n{diff_text}\n"
    )

    print(f"Sending summary request to Gemini API ({model_name})...")
    
    response_text = gemini_client.generate_content(
        model_name=model_name,
        prompt=prompt,
        document_text=document_text
    )

    if not response_text:
        print("Failed to get review summary from Gemini API.")
        return None

    # Save output
    out_file = cl_dir / "final_summary.md"
    save_file(out_file, response_text)
    print(f"Consolidated summary saved to {out_file}")
    
    return response_text
