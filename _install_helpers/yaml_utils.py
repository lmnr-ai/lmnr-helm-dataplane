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
        # Escape backslashes and double quotes for YAML double-quoted strings
        # Must escape backslashes first to avoid double-escaping
        escaped = value.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped}"'
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


def is_loadbalancer_disabled(yaml_content: str) -> bool:
    """
    Check if LoadBalancer is explicitly disabled in the YAML content.
    
    This function specifically checks for:
        dataPlaneProxy:
          loadBalancer:
            enabled: false
    
    Args:
        yaml_content: The YAML content as a string
        
    Returns:
        True if LoadBalancer is explicitly disabled, False otherwise
    """
    lines = yaml_content.splitlines()
    in_data_plane_proxy = False
    in_load_balancer = False
    data_plane_indent = -1
    
    for line in lines:
        # Skip comments and empty lines
        stripped = line.lstrip()
        if not stripped or stripped.startswith('#'):
            continue
        
        # Calculate indentation level
        indent = len(line) - len(stripped)
        
        # Reset sections if we're back at root level or parent level
        if in_load_balancer and indent <= data_plane_indent:
            in_load_balancer = False
        if in_data_plane_proxy and indent <= data_plane_indent:
            in_data_plane_proxy = False
            in_load_balancer = False
        
        # Check for dataPlaneProxy section
        if stripped.startswith('dataPlaneProxy:'):
            in_data_plane_proxy = True
            data_plane_indent = indent
            continue
        
        # Check for loadBalancer section within dataPlaneProxy
        if in_data_plane_proxy and stripped.startswith('loadBalancer:'):
            in_load_balancer = True
            continue
        
        # Check for enabled: false within loadBalancer section
        if in_load_balancer and stripped.startswith('enabled:'):
            value = stripped.split(':', 1)[1].strip().lower()
            # Remove quotes if present
            value = value.strip('"').strip("'")
            return value == 'false'
    
    # If loadBalancer section not found or enabled not specified, assume enabled
    return False
