from abc import ABC, abstractmethod
from typing import Dict, Any
from tools.tool_models import ToolResponse, ValidationResult

class BaseTool(ABC):
    """Base representation of agent-callable operations."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name identifier of this tool."""
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        """Details outlining function execution patterns."""
        pass
        
    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """Pydantic schema parameters configuration for APIs."""
        pass

    @property
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema format input parameters configuration."""
        return self.schema
        
    @property
    def output_schema(self) -> Dict[str, Any]:
        """JSON Schema format output configurations."""
        return {
            "type": "object",
            "properties": {
                "is_success": {"type": "boolean"},
                "result_content": {"type": "string"},
                "error_message": {"type": "string"}
            }
        }
        
    @abstractmethod
    def execute(self, **kwargs) -> ToolResponse:
        """Main execution boundary logic call."""
        pass

    def validate(self, **kwargs) -> ValidationResult:
        """Validates incoming arguments against parameters required fields schema specifications."""
        required = self.schema.get("required", [])
        errors = []
        for field in required:
            if field not in kwargs:
                errors.append(f"Missing required field '{field}'")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

