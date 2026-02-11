"""YAML generation utilities without external dependencies."""

from typing import Any, List, Dict, Union


def _yaml_scalar(value: Any) -> str:
    """
    Format a scalar value for YAML output.
    
    Args:
        value: The value to format
        
    Returns:
        YAML-formatted string representation
    """
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        if value == '':
            return '""'
        return f'"{value}"'
    return str(value)


def _yaml_lines(obj: Union[Dict, List], indent: int = 0) -> List[str]:
    """
    Recursively render a dict/list to YAML lines.
    
    Args:
        obj: Dictionary or list to convert
        indent: Current indentation level
        
    Returns:
        List of YAML-formatted strings
    """
    lines = []
    prefix = '  ' * indent
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(_yaml_lines(value, indent + 1))
            else:
                lines.append(f"{prefix}{key}: {_yaml_scalar(value)}")
    
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_yaml_lines(item, indent + 1))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
    
    return lines


def dict_to_yaml(obj: Dict) -> str:
    """
    Convert a Python dict to a YAML string.
    
    Args:
        obj: Dictionary to convert
        
    Returns:
        YAML-formatted string
    """
    return '\n'.join(_yaml_lines(obj)) + '\n'
