#!/usr/bin/env python3
"""
Laminar Data Plane - Helm Interactive Installer

Zero-dependency CLI that guides users through configuration and deployment.
"""

import sys
import argparse
import time
from _install_helpers.constants import (
    RELEASE_NAME, LB_SERVICE_NAME, VALUES_FILE, YELLOW, RESET,
    ESTIMATE_HELM_INSTALL, ESTIMATE_POD_READINESS,
    ESTIMATE_TOTAL_MIN, ESTIMATE_TOTAL_MAX
)
from _install_helpers.ui import (
    print_header, print_section, print_info, print_success,
    print_error, print_warning, print_final_url
)
from _install_helpers.input_utils import get_yes_no
from _install_helpers.prerequisites import check_prerequisites
from _install_helpers.config import configure
from _install_helpers.values import (
    build_values, write_values_file_with_namespace, read_namespace_from_values
)
from _install_helpers.helm import build_helm_cmd, run_helm, wait_for_pods_ready, get_load_balancer_url


def update_only() -> None:
    """Re-apply existing laminar.yaml without interactive prompts."""
    print_header("Laminar Data Plane - Update")

    if not VALUES_FILE.exists():
        print_error(f"{VALUES_FILE.name} not found!")
        print_info("Please run the full installation first: python3 install.py")
        sys.exit(1)

    print("Updating existing installation...")
    print("This will re-apply laminar.yaml and pull latest container images.\n")

    namespace = read_namespace_from_values()
    print_success(f"Using configuration from {VALUES_FILE.name}")
    print_info(f"Namespace: {namespace}\n")
    
    print_info("Estimated time: 2-4 minutes")

    start_time = time.time()
    args = build_helm_cmd(namespace)

    print_section("Running Helm Upgrade")
    returncode = run_helm(args)

    if returncode != 0:
        print_error("Helm upgrade failed")
        sys.exit(1)

    print_success("Helm upgrade completed successfully!\n")

    # Wait for pods to be ready
    print_section("Waiting for Pods to be Ready")
    if not wait_for_pods_ready(namespace):
        print_warning("Pods did not become ready within the timeout period.")
        print_info("Check pod status: kubectl get pods -n " + namespace)

    content = VALUES_FILE.read_text()
    lb_disabled = 'enabled: false' in content and 'loadBalancer:' in content
    
    total_elapsed = int(time.time() - start_time)
    mins = total_elapsed // 60
    secs = total_elapsed % 60
    
    if not lb_disabled:
        url = get_load_balancer_url(namespace)
        port = '40080'
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith('port:') and 'loadBalancer' not in stripped:
                port = stripped.split(':')[1].strip().strip('"')
                break
        
        if url:
            print_final_url(url, port)
            print_info(f"\nTotal update time: {mins}m {secs}s")
        else:
            print_warning("Could not retrieve LoadBalancer URL yet.")
            print_info(f"Check manually: kubectl get svc {LB_SERVICE_NAME} -n {namespace}")
            print_info(f"\nTotal update time: {mins}m {secs}s")


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Laminar Data Plane - Helm Interactive Installer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 install.py              Run full interactive installation
  python3 install.py -u           Update existing installation (re-apply laminar.yaml)
  python3 install.py --help       Show this help message

The installer is fully interactive and requires only Python 3 (no dependencies).
It will guide you through:
  1. Prerequisites check (kubectl, helm)
  2. Configuration (namespace, cloud provider, credentials)
  3. Automatic cloud storage setup (optional)
  4. Helm deployment
  5. Pod readiness verification

For more information, see README.md
        """
    )
    parser.add_argument(
        '-u', '--update-only',
        action='store_true',
        help='Update existing installation using laminar.yaml (skip interactive setup)'
    )
    return parser.parse_args()


def main() -> None:
    """Main installation flow."""
    args = parse_arguments()
    
    if args.update_only:
        try:
            update_only()
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Update cancelled by user{RESET}")
            sys.exit(0)
        return

    print_header("Laminar Data Plane - Helm Installer")

    print("Welcome to the Laminar Data Plane installer!")
    print("This wizard will guide you through configuring and deploying")
    print("the Laminar Data Plane on your Kubernetes cluster.\n")
    
    print_info(f"Estimated time: {ESTIMATE_TOTAL_MIN}-{ESTIMATE_TOTAL_MAX} minutes")
    print_info("TIP: Use Ctrl-C at any prompt to retry that section or exit")
    print_info("TIP: Use arrow keys to navigate input history\n")

    try:
        start_time = time.time()
        
        print_section("Prerequisites Check (~5 seconds)")
        context = check_prerequisites()
        elapsed = int(time.time() - start_time)
        print_success(f"Prerequisites check complete ({elapsed}s)\n")
        
        config = configure(context)
        namespace = config['namespace']

        values = build_values(config)
        write_values_file_with_namespace(values, namespace)

        print_section("Ready to Deploy")
        print_info(f"Release name:         {RELEASE_NAME}")
        print_info(f"Namespace:            {namespace}")
        print_info(f"Values file:          {VALUES_FILE}")
        if config.get('s3_enabled'):
            print_info(f"ClickHouse bucket:    {config['ch_bucket']}")
        print()

        confirm = get_yes_no("Proceed with installation?", default=True)
        if not confirm:
            print()
            print_info("Installation cancelled. Your configuration is saved in laminar.yaml.")
            print_info("You can edit it and run: python3 install.py update-only")
            sys.exit(0)

        args = build_helm_cmd(namespace)

        print_section(f"Running Helm Install (~{ESTIMATE_HELM_INSTALL} seconds)")
        helm_start = time.time()
        returncode = run_helm(args)

        if returncode != 0:
            print_error("Helm install failed")
            sys.exit(1)

        helm_elapsed = int(time.time() - helm_start)
        print_success(f"Helm install completed successfully! ({helm_elapsed}s)\n")

        # Wait for pods to be ready
        print_section(f"Waiting for Pods to be Ready (~{ESTIMATE_POD_READINESS} seconds)")
        pods_start = time.time()
        if not wait_for_pods_ready(namespace):
            print_warning("Pods did not become ready within the timeout period.")
            print_info("Check pod status: kubectl get pods -n " + namespace)
            print_info("Check pod logs: kubectl logs -l app.kubernetes.io/name=laminar-clickhouse -n " + namespace)
            sys.exit(1)

        pods_elapsed = int(time.time() - pods_start)
        print_success(f"All pods are ready! ({pods_elapsed}s)\n")

        lb_enabled = config.get('lb_enabled', True)
        lb_port = config.get('lb_port', '40080')
        
        total_elapsed = int(time.time() - start_time)
        mins = total_elapsed // 60
        secs = total_elapsed % 60
        
        if lb_enabled:
            url = get_load_balancer_url(namespace)
            if url:
                print_final_url(url, lb_port)
                print_info(f"\nTotal installation time: {mins}m {secs}s")
            else:
                print()
                print_warning("LoadBalancer URL is not available yet.")
                print_info("It may take a few more minutes for your cloud provider to provision it.")
                print_info(f"Check with: kubectl get svc {LB_SERVICE_NAME} -n {namespace}")
        else:
            print()
            print_header("Installation Complete!")
            print_success("Laminar Data Plane is deployed (no external LoadBalancer).")
            print_info(f"\nTotal installation time: {mins}m {secs}s")

    except KeyboardInterrupt:
        print(f"\n{YELLOW}Installation cancelled by user{RESET}")
        sys.exit(0)
    except Exception as e:
        print()
        print_error(f"An error occurred: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
