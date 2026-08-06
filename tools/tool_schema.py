from typing import Dict, Any

def generate_groq_tool_definition(name: str, description: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generates Groq Tool Calling compatible JSON Schema definition.
    
    Args:
        name: The name of the tool function.
        description: Detail text describing tool utilization patterns.
        parameters: Dictionary holding parameters schema details.
        
    Returns:
        Structured API tool calling definition dictionary.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters.get("properties", {}),
                "required": parameters.get("required", [])
            }
        }
    }
