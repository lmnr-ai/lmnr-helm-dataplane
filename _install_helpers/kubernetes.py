"""Kubernetes cluster utilities."""

import json
import subprocess
from typing import Optional, List, Tuple


def get_storage_classes() -> List[Tuple[str, bool]]:
    """
    Get available storage classes from the cluster.
    
    Returns:
        List of tuples (storage_class_name, is_default)
    """
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'storageclass', '-o', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        
        data = json.loads(result.stdout)
        
        storage_classes = []
        for item in data.get('items', []):
            name = item['metadata']['name']
            # Check if it's marked as default
            annotations = item['metadata'].get('annotations', {})
            is_default = (
                annotations.get('storageclass.kubernetes.io/is-default-class') == 'true' or
                annotations.get('storageclass.beta.kubernetes.io/is-default-class') == 'true'
            )
            storage_classes.append((name, is_default))
        
        return storage_classes
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        return []


def get_default_storage_class() -> Optional[str]:
    """
    Get the default storage class name from the cluster.
    
    Returns:
        Default storage class name or None if not found
    """
    storage_classes = get_storage_classes()
    for name, is_default in storage_classes:
        if is_default:
            return name
    return None


def get_recommended_storage_class(cloud_provider: str) -> Optional[str]:
    """
    Get a recommended storage class based on cloud provider.
    
    Args:
        cloud_provider: 'aws' or 'gcp'
        
    Returns:
        Recommended storage class name or None
    """
    storage_classes = get_storage_classes()
    
    if not storage_classes:
        return None
    
    # First, check if there's a default
    for name, is_default in storage_classes:
        if is_default:
            return name
    
    # No default, try cloud-specific recommendations
    if cloud_provider == 'aws':
        # Prefer gp3 > gp2 > first available
        for name, _ in storage_classes:
            if 'gp3' in name.lower():
                return name
        for name, _ in storage_classes:
            if 'gp2' in name.lower():
                return name
    elif cloud_provider == 'gcp':
        # Prefer pd-ssd > standard-rwo > first available
        for name, _ in storage_classes:
            if 'ssd' in name.lower():
                return name
        for name, _ in storage_classes:
            if 'standard' in name.lower():
                return name
    
    # Return first available if no match
    if storage_classes:
        return storage_classes[0][0]
    
    return None
