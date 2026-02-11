"""Prerequisites checking for required tools and configurations."""

import subprocess
import sys
from typing import Optional
from .ui import print_error, print_info, print_section, print_success


def check_command(cmd: str, name: str, install_hint: str) -> bool:
    """
    Check if a command-line tool is available.
    
    Args:
        cmd: Command to check
        name: Human-readable name of the tool
        install_hint: Installation instructions
        
    Returns:
        True if command is available, False otherwise
    """
    try:
        version_args = [cmd, 'version'] if cmd == 'helm' else [cmd, 'version', '--client']
        subprocess.run(version_args, capture_output=True, check=True)
        print_success(f"{name} is installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error(f"{name} is not installed or not in PATH")
        print_info(install_hint)
        return False


def check_cloud_cli(cloud_provider: str) -> bool:
    """
    Check if the cloud CLI (aws or gsutil) is available.
    
    Args:
        cloud_provider: Either 'aws' or 'gcp'
        
    Returns:
        True if CLI is available, False otherwise
    """
    try:
        if cloud_provider == 'aws':
            subprocess.run(['aws', '--version'], capture_output=True, check=True)
        else:
            subprocess.run(['gsutil', 'version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_kubectl_context() -> Optional[str]:
    """
    Verify kubectl has a valid context configured.
    
    Returns:
        The current context name, or None if not configured
    """
    try:
        result = subprocess.run(
            ['kubectl', 'config', 'current-context'],
            capture_output=True, text=True, check=True
        )
        context = result.stdout.strip()
        print_success(f"kubectl context: {context}")
        return context
    except subprocess.CalledProcessError:
        print_error("No kubectl context configured")
        print_info("Run 'kubectl config use-context <context>' to set one")
        return None


def check_prerequisites() -> str:
    """
    Verify all required tools are installed.
    
    Returns:
        The kubectl context name
        
    Raises:
        SystemExit if prerequisites are not met
    """
    print_section("Checking Prerequisites")
    ok = True
    
    if not check_command('kubectl', 'kubectl', 'Install from https://kubernetes.io/docs/tasks/tools/'):
        ok = False
    if not check_command('helm', 'Helm', 'Install from https://helm.sh/docs/intro/install/'):
        ok = False
    
    context = None
    if ok:
        context = check_kubectl_context()
        if not context:
            ok = False
    
    if not ok:
        print()
        print_error("Prerequisites not met. Please install the missing tools and try again.")
        sys.exit(1)
    
    print()
    print_success("All prerequisites met!")
    return context
