"""Helm operations and LoadBalancer management."""

import subprocess
import sys
import time
from typing import Optional, List
from .constants import (
    RELEASE_NAME, CHART_DIR, VALUES_FILE, LB_SERVICE_NAME,
    LB_MAX_ATTEMPTS, LB_INITIAL_WAIT, LB_MAX_WAIT
)
from .ui import print_info, print_section


def build_helm_cmd(namespace: str) -> List[str]:
    """
    Build the helm upgrade --install command.
    
    Args:
        namespace: Kubernetes namespace
        
    Returns:
        Command as list of strings
    """
    return [
        'helm', 'upgrade', '--install',
        RELEASE_NAME,
        CHART_DIR,
        '--namespace', namespace,
        '--create-namespace',
        '-f', str(VALUES_FILE),
    ]


def run_helm(args: List[str]) -> int:
    """
    Execute the helm command.
    
    Args:
        args: Command arguments
        
    Returns:
        Return code from helm command
    """
    print(f"Command: {' '.join(args)}\n")
    result = subprocess.run(args)
    return result.returncode


def wait_for_pods_ready(namespace: str) -> bool:
    """
    Wait for all Laminar pods to be ready.
    
    Args:
        namespace: Kubernetes namespace
        
    Returns:
        True if pods are ready, False if timeout
    """
    print_section("Waiting for Pods to be Ready")
    print_info("Waiting for ClickHouse and Data Plane Proxy to start (up to 5 minutes)...")
    
    try:
        # Wait for ClickHouse StatefulSet
        subprocess.run(
            [
                'kubectl', 'wait', '--for=condition=ready',
                'pod', '-l', 'app.kubernetes.io/name=laminar-clickhouse',
                '-n', namespace,
                '--timeout=300s'
            ],
            check=True
        )
        
        # Wait for Data Plane Proxy Deployment
        subprocess.run(
            [
                'kubectl', 'wait', '--for=condition=ready',
                'pod', '-l', 'app.kubernetes.io/name=laminar-data-plane-proxy',
                '-n', namespace,
                '--timeout=300s'
            ],
            check=True
        )
        
        return True
    except subprocess.CalledProcessError:
        return False


def get_load_balancer_url(namespace: str) -> Optional[str]:
    """
    Attempt to retrieve the LoadBalancer external URL via kubectl.
    
    Polls the LoadBalancer service until an external IP/hostname is assigned,
    or until the maximum number of attempts is reached.
    
    Args:
        namespace: Kubernetes namespace
        
    Returns:
        LoadBalancer URL (hostname or IP) or None if not available
    """
    print_section("Retrieving LoadBalancer URL")
    print_info("Waiting for LoadBalancer to be provisioned (this can take 1-3 minutes)...")

    for attempt in range(1, LB_MAX_ATTEMPTS + 1):
        for field in ['hostname', 'ip']:
            try:
                result = subprocess.run(
                    [
                        'kubectl', 'get', 'svc', LB_SERVICE_NAME,
                        '-n', namespace,
                        '-o', f'jsonpath={{.status.loadBalancer.ingress[0].{field}}}'
                    ],
                    capture_output=True, text=True, check=True
                )
                value = result.stdout.strip()
                if value and value != '<none>' and value != 'null':
                    return value
            except subprocess.CalledProcessError:
                pass

        if attempt < LB_MAX_ATTEMPTS:
            wait = min(LB_MAX_WAIT, LB_INITIAL_WAIT + attempt)
            sys.stdout.write(f"\r  Attempt {attempt}/{LB_MAX_ATTEMPTS} - waiting {wait}s...")
            sys.stdout.flush()
            time.sleep(wait)

    print()
    return None
