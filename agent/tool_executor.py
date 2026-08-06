from typing import Dict, Any, List
from agent.registry import ToolRegistry
from tools.tool_models import ToolResponse

class ToolExecutor:
    """Helper module executing tools and formatting outputs."""
    
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        
    def execute_single(self, name: str, arguments: Dict[str, Any]) -> ToolResponse:
        """Executes a single tool and handles failures."""
        try:
            return self.registry.execute_tool(name, **arguments)
        except Exception as e:
            return ToolResponse(
                is_success=False,
                result_content=f"Error executing tool '{name}': {e}",
                error_message=str(e)
            )
            
    def execute_multiple(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Executes multiple tool calls in sequence and formats outputs."""
        results = []
        for call in tool_calls:
            name = call.get("name")
            args = call.get("arguments") or {}
            call_id = call.get("id")
            
            res = self.execute_single(name, args)
            results.append({
                "tool_call_id": call_id,
                "name": name,
                "is_success": res.is_success,
                "result": res.result_content
            })
        return results
