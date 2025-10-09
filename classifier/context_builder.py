"""
Context builder for PR classification.

Formats PR data into a structured string for LLM consumption.
This is a shared component that can be imported by both the classifier
and the explorer GUI to show "what the LLM sees".
"""

from typing import Dict, Any, Optional


def build_pr_context(pr_data: Dict[str, Any]) -> str:
    """
    Build formatted context string from PR data for LLM classification.
    
    This is a pure function with no dependencies on LLM or database.
    Takes PR data and returns a formatted string with clear sections.
    
    Args:
        pr_data: Dict containing PR information:
            - repo: str (e.g., "facebook/react")
            - pr_number: int
            - title: str
            - body: Optional[str]
            - merged_at: str (ISO timestamp)
            - files: Optional[List[Dict]] (changed files with diffs)
            - linked_issue: Optional[Dict] (issue metadata)
            - issue_comments: Optional[List[Dict]] (issue comments)
    
    Returns:
        Formatted string with sections for PR metadata, files, issue, and comments.
        
    Note:
        We already truncated diffs in Milestone 6 (100 lines per file, max 10 files),
        so no additional truncation is needed here.
    """
    sections = []
    
    # Section 1: PR Metadata
    sections.append("=" * 80)
    sections.append("PULL REQUEST METADATA")
    sections.append("=" * 80)
    sections.append(f"Repository: {pr_data.get('repo', 'Unknown')}")
    sections.append(f"PR Number: #{pr_data.get('pr_number', 'Unknown')}")
    sections.append(f"Title: {pr_data.get('title', 'Unknown')}")
    sections.append(f"Merged At: {pr_data.get('merged_at', 'Unknown')}")
    sections.append("")
    
    # Section 2: PR Description/Body
    sections.append("=" * 80)
    sections.append("PR DESCRIPTION")
    sections.append("=" * 80)
    body = pr_data.get("body")
    if body:
        sections.append(body)
    else:
        sections.append("(No description provided)")
    sections.append("")
    
    # Section 3: Changed Files with Diffs
    sections.append("=" * 80)
    sections.append("CHANGED FILES AND DIFFS")
    sections.append("=" * 80)
    files = pr_data.get("files")
    
    # Handle nested structure: files might be {'files': [...], 'summary': {...}}
    if files and isinstance(files, dict) and 'files' in files:
        files = files['files']
    
    if files and isinstance(files, list):
        sections.append(f"Total files changed: {len(files)}")
        sections.append("")
        
        for i, file in enumerate(files, 1):
            filename = file.get("filename", "Unknown")
            status = file.get("status", "Unknown")
            additions = file.get("additions", 0)
            deletions = file.get("deletions", 0)
            patch = file.get("patch")
            
            sections.append(f"File {i}: {filename}")
            sections.append(f"Status: {status} (+{additions} -{deletions})")
            
            if patch:
                sections.append("```diff")
                sections.append(patch)
                sections.append("```")
            else:
                sections.append("(No diff available - likely binary or too large)")
            
            sections.append("")
    else:
        sections.append("(No files information available)")
        sections.append("")
    
    # Section 4: Linked Issue (if present)
    linked_issue = pr_data.get("linked_issue")
    if linked_issue and isinstance(linked_issue, dict):
        sections.append("=" * 80)
        sections.append("LINKED ISSUE")
        sections.append("=" * 80)
        sections.append(f"Issue Number: #{linked_issue.get('number', 'Unknown')}")
        sections.append(f"Title: {linked_issue.get('title', 'Unknown')}")
        sections.append(f"State: {linked_issue.get('state', 'Unknown')}")
        sections.append("")
        sections.append("Issue Body:")
        issue_body = linked_issue.get("body")
        if issue_body:
            sections.append(issue_body)
        else:
            sections.append("(No issue description)")
        sections.append("")
    
    # Section 5: Issue Comments (if present)
    issue_comments = pr_data.get("issue_comments")
    if issue_comments and isinstance(issue_comments, list) and len(issue_comments) > 0:
        sections.append("=" * 80)
        sections.append("ISSUE DISCUSSION")
        sections.append("=" * 80)
        sections.append(f"Total comments: {len(issue_comments)}")
        sections.append("")
        
        for i, comment in enumerate(issue_comments, 1):
            author = comment.get("user", {}).get("login", "Unknown")
            created_at = comment.get("created_at", "Unknown")
            body = comment.get("body", "")
            
            sections.append(f"Comment {i} by {author} at {created_at}:")
            sections.append(body)
            sections.append("")
            sections.append("-" * 80)
    
    # Join all sections with newlines
    return "\n".join(sections)

