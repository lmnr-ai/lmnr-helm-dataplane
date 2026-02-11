"""Interactive configuration collection and orchestration."""

import getpass
from typing import Dict, Any, Optional, Callable
from .constants import (
    DEFAULT_AWS_REGION, DEFAULT_GCP_REGION, DEFAULT_NAMESPACE,
    DEFAULT_PROXY_REPLICAS, DEFAULT_PROXY_CPU, DEFAULT_PROXY_MEMORY,
    DEFAULT_CH_CPU, DEFAULT_CH_MEMORY, DEFAULT_CH_STORAGE_SIZE,
    DEFAULT_LB_PORT, YELLOW, RESET
)
from .ui import print_section, print_info, print_success, print_warning
from .input_utils import (
    get_input, get_yes_no, get_choice, get_int_input,
    generate_secure_password, generate_bucket_suffix
)
from .prerequisites import check_cloud_cli
from .cloud_aws import setup_aws_iam_policy
from .cloud_gcp import get_gcp_project_from_context, create_gcs_hmac_keys
from .storage import parse_existing_buckets, configure_bucket, construct_s3_endpoint
from .kubernetes import get_recommended_storage_class


def _retry_on_interrupt(func: Callable, section_name: str, *args, **kwargs) -> Any:
    """
    Execute a function and allow retry on KeyboardInterrupt (Ctrl-C).
    
    Args:
        func: Function to execute
        section_name: Name of the section for display
        *args: Arguments to pass to func
        **kwargs: Keyword arguments to pass to func
        
    Returns:
        The result of the function
        
    Raises:
        KeyboardInterrupt: If user chooses to exit
    """
    while True:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Section interrupted{RESET}")
            try:
                retry = get_yes_no(f"Retry {section_name}? (n to exit)", default=True)
                if retry:
                    print()
                    continue
                else:
                    raise KeyboardInterrupt("User chose to exit")
            except KeyboardInterrupt:
                raise KeyboardInterrupt("User chose to exit")


def configure(context: Optional[str]) -> Dict[str, Any]:
    """
    Collect configuration from the user interactively.
    
    Args:
        context: kubectl context name
        
    Returns:
        Configuration dictionary
    """
    config = {}

    # Step 1: Namespace
    def _step_namespace():
        print_section("Step 1: Kubernetes Namespace")
        config['namespace'] = get_input("Namespace", default=DEFAULT_NAMESPACE)
    
    _retry_on_interrupt(_step_namespace, "Step 1: Kubernetes Namespace")

    # Step 2: Cloud Provider & Cluster Info
    def _step_cloud_provider():
        print_section("Step 2: Cloud Provider & Cluster Info")
        cloud_options = ["AWS", "GCP"]
        cloud_idx = get_choice("Select your cloud provider:", cloud_options)
        config['cloud_provider'] = cloud_options[cloud_idx].lower()

        if config['cloud_provider'] == 'aws':
            print_info("Common AWS regions: us-east-1, us-west-2, eu-west-1")
            if context and 'eks' in context.lower():
                cluster_name_parts = context.split('/')
                if len(cluster_name_parts) > 1:
                    config['cluster_name'] = cluster_name_parts[-1]
                else:
                    config['cluster_name'] = get_input("EKS cluster name", required=True)
            else:
                config['cluster_name'] = get_input("EKS cluster name", required=True)
            config['region'] = get_input("Region", default=DEFAULT_AWS_REGION)
        else:
            print_info("Common GCP regions: us-central1, us-east1, europe-west1")
            if context:
                project = get_gcp_project_from_context(context)
                if project:
                    print_success(f"Detected GCP project from context: {project}")
                    config['gcp_project_id'] = project
                else:
                    config['gcp_project_id'] = get_input("GCP Project ID", required=True)
            else:
                config['gcp_project_id'] = get_input("GCP Project ID", required=True)
            config['region'] = get_input("Region", default=DEFAULT_GCP_REGION)
    
    _retry_on_interrupt(_step_cloud_provider, "Step 2: Cloud Provider & Cluster Info")

    # Step 3: Required Configuration
    def _step_required_config():
        print_section("Step 3: Required Configuration")
        print_warning("REQUIRED: Data Plane Public Key must be provided by Laminar")
        config['data_plane_public_key'] = get_input("Data Plane Public Key", required=True)

        print()
        generate_password = get_yes_no("Generate a secure ClickHouse password automatically?", default=True)
        if generate_password:
            config['clickhouse_password'] = generate_secure_password()
            print_success("Generated secure password (128 hex characters):")
            print(f"  {YELLOW}{config['clickhouse_password']}{RESET}")
            print_warning("Please save this password securely!")
        else:
            while True:
                password = getpass.getpass("Enter ClickHouse password: ")
                if password:
                    config['clickhouse_password'] = password
                    break
                print_warning("Password cannot be empty")
    
    _retry_on_interrupt(_step_required_config, "Step 3: Required Configuration")

    # Step 4: Storage Configuration
    _retry_on_interrupt(_configure_storage, "Step 4: Storage Configuration", config, context)
    
    # Step 5: Advanced Configuration
    _retry_on_interrupt(_configure_advanced, "Step 5: Advanced Configuration", config)

    return config


def _configure_storage(config: Dict[str, Any], context: Optional[str]) -> None:
    """
    Configure storage buckets and credentials.
    
    Args:
        config: Configuration dictionary (modified in place)
        context: kubectl context name
    """
    print_section("Step 4: Storage Buckets")
    
    existing_buckets = parse_existing_buckets()
    use_existing = False
    
    # Check cloud CLI availability upfront (needed in multiple paths)
    has_cloud_cli = check_cloud_cli(config['cloud_provider'])
    
    if existing_buckets:
        print_success("Found existing bucket configuration in laminar.yaml:")
        if 'ch_bucket' in existing_buckets:
            print_info(f"  ClickHouse data bucket: {existing_buckets['ch_bucket']}")
        print()
        use_existing = get_yes_no("Keep existing bucket configuration?", default=True)
        
        if use_existing:
            if existing_buckets.get('s3_enabled'):
                config['s3_enabled'] = True
                config['ch_bucket'] = existing_buckets.get('ch_bucket', '')
                config['s3_endpoint'] = construct_s3_endpoint(
                    config['cloud_provider'],
                    config['ch_bucket'],
                    config['region'],
                )
                config['s3_region'] = config['region']
                
                print()
                config['s3_use_env_creds'] = get_yes_no(
                    "Use IAM / Workload Identity for bucket access (recommended)?",
                    default=True
                )
                if not config['s3_use_env_creds']:
                    config['s3_access_key'] = get_input("Access Key ID", required=True)
                    config['s3_secret_key'] = getpass.getpass("Secret Access Key: ")
    
    if not use_existing:
        print_info("Laminar Data Plane can use cloud object storage (S3 / GCS) for:")
        print_info("  ClickHouse data backend (recommended for production)")
        print()
        
        cli_desc = "AWS CLI" if config['cloud_provider'] == 'aws' else "gsutil"
        print_info(f"You can either let this script create the bucket (requires {cli_desc})")
        print_info("installed), or create it manually in advance.")

        if has_cloud_cli:
            print_success(f"{cli_desc} is available")
        else:
            print_warning(f"{cli_desc} not found - bucket creation will be skipped")

        config['s3_enabled'] = get_yes_no(
            "\nEnable S3/GCS backend for ClickHouse storage? (recommended for production)",
            default=existing_buckets.get('s3_enabled', True)
        )
        
        if config['s3_enabled']:
            print()
            config['s3_use_env_creds'] = get_yes_no(
                "Use IAM / Workload Identity for bucket access (recommended)?",
                default=True
            )
            if not config['s3_use_env_creds']:
                config['s3_access_key'] = get_input("Access Key ID", required=True)
                config['s3_secret_key'] = getpass.getpass("Secret Access Key: ")

            bucket_suffix = generate_bucket_suffix()
            ch_bucket_default = existing_buckets.get('ch_bucket', f"lmnr-clickhouse-data-{bucket_suffix}")

            config['ch_bucket'] = configure_bucket(
                config['cloud_provider'],
                config['region'],
                "ClickHouse data bucket",
                ch_bucket_default,
                has_cloud_cli,
            )
            config['s3_endpoint'] = construct_s3_endpoint(
                config['cloud_provider'],
                config['ch_bucket'],
                config['region'],
            )
            config['s3_region'] = config['region']
        
    if config.get('s3_enabled') and has_cloud_cli:
        _setup_cloud_permissions(config, has_cloud_cli)
    
    # Auto-detect and configure storage class (always do this)
    _configure_storage_class(config)


def _configure_storage_class(config: Dict[str, Any]) -> None:
    """
    Configure storage class for ClickHouse persistent volume.
    
    Args:
        config: Configuration dictionary (modified in place)
    """
    print()
    print_section("Step 4c: ClickHouse Persistent Storage")
    
    recommended_sc = get_recommended_storage_class(config['cloud_provider'])
    if recommended_sc:
        print_success(f"Detected storage class: {recommended_sc}")
        config['ch_storage_class'] = recommended_sc
        print_info(f"ClickHouse will use '{recommended_sc}' storage class for persistent volumes")
    else:
        print_warning("No storage class detected in the cluster!")
        print_info("You may need to create a storage class or the deployment may fail.")
        ch_storage_class = get_input(
            "ClickHouse storage class (leave empty to skip)",
            required=False
        )
        if ch_storage_class:
            config['ch_storage_class'] = ch_storage_class


def _setup_cloud_permissions(config: Dict[str, Any], has_cloud_cli: bool) -> None:
    """
    Setup cloud provider permissions (IAM/Workload Identity).
    
    Args:
        config: Configuration dictionary (modified in place)
        has_cloud_cli: Whether cloud CLI is available
    """
    print()
    print_section("Step 4b: Cloud Storage Authentication Setup")
    
    buckets_to_grant = [config['ch_bucket']]
    
    if config['cloud_provider'] == 'aws':
        print_info("Setting up AWS IAM permissions for S3 access...")
        print_info(f"Buckets: {', '.join(buckets_to_grant)}")
        print()
        auto_setup = get_yes_no(
            "Automatically attach S3 policy to node group IAM role?",
            default=True
        )
        if auto_setup:
            success = setup_aws_iam_policy(
                config['cluster_name'],
                buckets_to_grant,
                config['region']
            )
            if not success:
                print_warning("IAM policy attachment failed. You may need to configure manually.")
                print_info("See README.md for manual setup instructions.")
        else:
            print_info("Skipping automatic IAM setup.")
            print_info("Make sure to grant S3 permissions manually before deployment.")
    
    else:  # GCP
        print_info("Setting up GCS HMAC keys for S3-compatible access...")
        print_info(f"Buckets: {', '.join(buckets_to_grant)}")
        print_info(f"Project: {config['gcp_project_id']}")
        print()
        print_info("Note: ClickHouse uses HMAC keys (not Workload Identity) for GCS access.")
        print()
        auto_setup = get_yes_no(
            "Automatically create GCP service account and generate HMAC keys?",
            default=True
        )
        if auto_setup:
            hmac_keys = create_gcs_hmac_keys(
                config['gcp_project_id'],
                buckets_to_grant
            )
            if hmac_keys:
                config['gcs_access_key_id'], config['gcs_secret_key'] = hmac_keys
                # Override the s3_use_env_creds for GCP since we have explicit keys
                config['s3_use_env_creds'] = False
            else:
                print_warning("HMAC key creation failed. You may need to configure manually.")
                print_info("See README.md for manual setup instructions.")
                # Fall back to manual credential entry
                if not config.get('s3_access_key') or not config.get('s3_secret_key'):
                    print()
                    print_info("Please provide existing HMAC credentials:")
                    config['gcs_access_key_id'] = get_input("HMAC Access Key ID", required=True)
                    config['gcs_secret_key'] = getpass.getpass("HMAC Secret: ")
                    config['s3_use_env_creds'] = False
        else:
            print_info("Skipping automatic HMAC key creation.")
            print_info("You'll need to create a GCP service account and HMAC keys manually.")
            print()
            use_existing = get_yes_no("Do you have existing HMAC keys to provide now?", default=False)
            if use_existing:
                config['gcs_access_key_id'] = get_input("HMAC Access Key ID", required=True)
                config['gcs_secret_key'] = getpass.getpass("HMAC Secret: ")
                config['s3_use_env_creds'] = False
            else:
                print_warning("You'll need to provide HMAC keys before ClickHouse can start.")
                print_info("See README.md for manual setup instructions.")


def _configure_advanced(config: Dict[str, Any]) -> None:
    """
    Configure advanced optional settings.
    
    Args:
        config: Configuration dictionary (modified in place)
    """
    print_section("Step 5: Advanced Configuration (Optional)")
    configure_advanced = get_yes_no("Configure advanced options?", default=False)

    if not configure_advanced:
        return

    print()
    print_info("Data Plane Proxy configuration:")
    config['proxy_replicas'] = get_int_input(
        "Number of proxy replicas",
        default=DEFAULT_PROXY_REPLICAS,
        min_value=1
    )

    configure_proxy_resources = get_yes_no("Configure proxy resource limits?", default=False)
    if configure_proxy_resources:
        config['proxy_cpu'] = get_input("Proxy CPU limit", default=DEFAULT_PROXY_CPU)
        config['proxy_memory'] = get_input("Proxy memory limit", default=DEFAULT_PROXY_MEMORY)

    print()
    print_info("ClickHouse configuration:")
    configure_ch_resources = get_yes_no("Configure ClickHouse resource limits?", default=False)
    if configure_ch_resources:
        config['ch_cpu'] = get_input("ClickHouse CPU limit", default=DEFAULT_CH_CPU)
        config['ch_memory'] = get_input("ClickHouse memory limit", default=DEFAULT_CH_MEMORY)

    config['ch_storage_size'] = get_input(
        "ClickHouse persistent volume size",
        default=DEFAULT_CH_STORAGE_SIZE
    )

    print()
    print_info("Load Balancer configuration:")
    config['lb_enabled'] = get_yes_no("Enable external LoadBalancer?", default=True)
    
    if config['lb_enabled']:
        config['lb_port'] = get_int_input(
            "External port",
            default=int(DEFAULT_LB_PORT),
            min_value=1,
            max_value=65535
        )

        print()
        print_info("Default LoadBalancer annotations are applied automatically")
        print_info(f"  based on your cloud provider ({config['cloud_provider'].upper()}).")
        add_annotations = get_yes_no("Add extra or override LoadBalancer annotations?", default=False)
        
        if add_annotations:
            config['lb_annotations'] = {}
            print_info("Enter annotations one per line. Empty key to finish.")
            while True:
                key = get_input("  Annotation key (empty to finish)")
                if not key:
                    break
                value = get_input(f"  Value for '{key}'", required=True)
                config['lb_annotations'][key] = value
