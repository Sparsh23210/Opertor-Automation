import csv
import json
from typing import Any
from pathlib import Path
from pydantic import BaseModel, Field
from backend.config import settings, resolve_safe_path
from backend.tools.registry import ToolResult, ToolDefinition, registry

# 1. List Workspace Files
class ListFilesInput(BaseModel):
    subdirectory: str = Field(default="", description="Optional relative subfolder within workspace data directory")

class ListFilesOutput(BaseModel):
    files: list[dict[str, str]]

def handle_list_files(args: ListFilesInput) -> ToolResult:
    target_dir = settings.DATA_DIR
    if args.subdirectory:
        target_dir = (settings.DATA_DIR / args.subdirectory).resolve()
    
    # Verify path is within DATA_DIR
    safe_path = resolve_safe_path(target_dir, [settings.DATA_DIR])
    if not safe_path.exists() or not safe_path.is_dir():
        return ToolResult(
            success=False,
            error=f"Directory '{args.subdirectory}' does not exist or is not a directory.",
            evidence_summary="Directory discovery failed: target path not found."
        )

    file_list = []
    for item in safe_path.rglob("*"):
        if item.is_file():
            rel_path = item.relative_to(settings.DATA_DIR).as_posix()
            file_list.append({
                "path": rel_path,
                "name": item.name,
                "size_bytes": item.stat().st_size
            })

    return ToolResult(
        success=True,
        data={"files": file_list},
        evidence_summary=f"Discovered {len(file_list)} files in workspace directory '{args.subdirectory or 'data'}'."
    )

# 2. Read Workspace File
class ReadFileInput(BaseModel):
    relative_path: str = Field(description="Relative path to file inside data/ directory")

class ReadFileOutput(BaseModel):
    content: str
    format: str

def handle_read_file(args: ReadFileInput) -> ToolResult:
    target_path = (settings.DATA_DIR / args.relative_path).resolve()
    safe_path = resolve_safe_path(target_path, [settings.DATA_DIR])

    if not safe_path.exists() or not safe_path.is_file():
        return ToolResult(
            success=False,
            error=f"File not found: '{args.relative_path}'",
            evidence_summary=f"Read failed: file '{args.relative_path}' does not exist."
        )

    if safe_path.stat().st_size > settings.MAX_FILE_SIZE_BYTES:
        return ToolResult(
            success=False,
            error=f"File size exceeds maximum permitted limit ({settings.MAX_FILE_SIZE_BYTES} bytes).",
            evidence_summary="Read blocked: file exceeds safety size threshold."
        )

    try:
        content = safe_path.read_text(encoding="utf-8")
        ext = safe_path.suffix.lower()
        return ToolResult(
            success=True,
            data={"content": content, "format": ext, "path": str(safe_path.relative_to(settings.DATA_DIR))},
            evidence_summary=f"Read {len(content)} characters from file '{args.relative_path}'.",
            source_references=[f"file:{safe_path.relative_to(settings.DATA_DIR).as_posix()}"]
        )
    except Exception as e:
        return ToolResult(
            success=False,
            error=f"Failed to read file '{args.relative_path}': {str(e)}",
            evidence_summary=f"Read failure for '{args.relative_path}'."
        )

# 3. Search Company Policies
class SearchPoliciesInput(BaseModel):
    query: str = Field(description="Keyword or topic query to find in company SOPs and policies")

class SearchPoliciesOutput(BaseModel):
    matches: list[dict[str, Any]]

def handle_search_policies(args: SearchPoliciesInput) -> ToolResult:
    query_terms = [t.lower().strip() for t in args.query.split() if len(t.strip()) > 2]
    if not query_terms:
        query_terms = [args.query.lower().strip()]

    matches = []
    policies_dir = settings.POLICIES_DIR
    if not policies_dir.exists():
        return ToolResult(
            success=True,
            data={"matches": []},
            evidence_summary="No policies directory found."
        )

    for policy_file in policies_dir.glob("*.md"):
        try:
            content = policy_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            matching_sections = []
            current_section = "General"
            
            for line in lines:
                if line.startswith("#"):
                    current_section = line.strip("#").strip()
                if any(term in line.lower() for term in query_terms):
                    matching_sections.append({
                        "section": current_section,
                        "text": line.strip()
                    })

            if matching_sections:
                matches.append({
                    "document": policy_file.name,
                    "file_path": policy_file.relative_to(settings.DATA_DIR).as_posix(),
                    "excerpt_count": len(matching_sections),
                    "excerpts": matching_sections[:5] # Limit to top 5 excerpts per doc
                })
        except Exception:
            continue

    return ToolResult(
        success=True,
        data={"matches": matches},
        evidence_summary=f"Searched policies for '{args.query}', found {len(matches)} matching documents.",
        source_references=[f"policy:{m['document']}" for m in matches]
    )

def register_file_tools():
    registry.register(ToolDefinition(
        name="list_workspace_files",
        description="List discoverable files within the approved workspace data directory.",
        input_schema=ListFilesInput,
        output_schema=ListFilesOutput,
        handler=handle_list_files,
        permission_scope="read"
    ))
    registry.register(ToolDefinition(
        name="read_workspace_file",
        description="Read contents of an approved file within the workspace.",
        input_schema=ReadFileInput,
        output_schema=ReadFileOutput,
        handler=handle_read_file,
        permission_scope="read"
    ))
    registry.register(ToolDefinition(
        name="search_company_policies",
        description="Search company standard operating procedures (SOPs) and credit/operations policies.",
        input_schema=SearchPoliciesInput,
        output_schema=SearchPoliciesOutput,
        handler=handle_search_policies,
        permission_scope="read"
    ))

register_file_tools()
