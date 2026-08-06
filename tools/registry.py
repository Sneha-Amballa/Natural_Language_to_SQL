from typing import Dict, List, Any
from tools.base_tool import BaseTool
from tools.tool_models import ToolResponse, ValidationResult
from tools.tool_schema import generate_groq_tool_definition

class ToolRegistry:
    """Registry mapping and dynamic tool definitions database."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        
    def register(self, tool: BaseTool) -> None:
        """Binds a new tool representation to matching name identifiers."""
        self._tools[tool.name] = tool
        
    def get_tool(self, name: str) -> BaseTool:
        """Retrieves the registered tool definition."""
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered.")
        return self._tools[name]
        
    def list_tools(self) -> List[str]:
        """Lists names of all registered tools."""
        return list(self._tools.keys())
        
    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Returns JSON schema representations of registered tools."""
        schemas = []
        for name, tool in self._tools.items():
            schemas.append(generate_groq_tool_definition(tool.name, tool.description, tool.schema))
        return schemas
        
    def execute_tool(self, name: str, **kwargs) -> ToolResponse:
        """Validates arguments and executes a tool by name with performance metrics and structured logs."""
        import time
        import logging
        logger = logging.getLogger("agent.tools")
        
        start_time = time.perf_counter()
        
        try:
            tool = self.get_tool(name)
        except KeyError as ke:
            logger.error({
                "event": "tool_execution_failed",
                "tool_name": name,
                "arguments": kwargs,
                "duration_ms": 0.0,
                "is_success": False,
                "error": str(ke)
            })
            return ToolResponse(
                is_success=False,
                result_content=f"Error: {ke}",
                error_message=str(ke)
            )
            
        val_res = tool.validate(**kwargs)
        if not val_res.is_valid:
            errors_str = "; ".join(val_res.errors)
            logger.warning({
                "event": "tool_validation_failed",
                "tool_name": name,
                "arguments": kwargs,
                "duration_ms": 0.0,
                "is_success": False,
                "error": errors_str
            })
            return ToolResponse(
                is_success=False,
                result_content=f"Validation Error: {errors_str}",
                error_message=errors_str
            )
            
        try:
            res = tool.execute(**kwargs)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            
            logger.info({
                "event": "tool_executed",
                "tool_name": name,
                "arguments": kwargs,
                "duration_ms": duration_ms,
                "is_success": res.is_success,
                "error": res.error_message
            })
            return res
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error({
                "event": "tool_execution_crash",
                "tool_name": name,
                "arguments": kwargs,
                "duration_ms": duration_ms,
                "is_success": False,
                "error": str(e)
            })
            return ToolResponse(
                is_success=False,
                result_content=f"Tool Execution Error: {e}",
                error_message=str(e)
            )

