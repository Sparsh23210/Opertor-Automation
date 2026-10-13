from typing import Any, Callable, Type
from pydantic import BaseModel, Field

class ToolResult(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    evidence_summary: str = ""
    source_references: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)

class ToolDefinition:
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Type[BaseModel],
        output_schema: Type[BaseModel],
        handler: Callable[..., ToolResult],
        requires_approval: bool = False,
        permission_scope: str = "read"  # read, write, execute, network
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.handler = handler
        self.requires_approval = requires_approval
        self.permission_scope = permission_scope

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' is already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "schema": t.input_schema.model_json_schema(),
                "requires_approval": t.requires_approval,
                "permission_scope": t.permission_scope
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Unknown tool '{name}'. Tool is not registered in the system.",
                evidence_summary=f"Attempted execution of unknown tool '{name}'."
            )
        try:
            validated_args = tool.input_schema(**args)
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Invalid arguments for tool '{name}': {str(e)}",
                evidence_summary=f"Argument validation failed for tool '{name}'."
            )

        try:
            result = tool.handler(validated_args)
            return result
        except PermissionError as pe:
            return ToolResult(
                success=False,
                error=f"Permission Denied: {str(pe)}",
                evidence_summary=f"Tool '{name}' failed permission check."
            )
        except Exception as ex:
            return ToolResult(
                success=False,
                error=f"Tool execution failed: {str(ex)}",
                evidence_summary=f"Tool '{name}' threw unexpected exception: {str(ex)}"
            )

registry = ToolRegistry()
