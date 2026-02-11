"""GCP-specific operations for GKE and HMAC key management."""

import subprocess
from typing import Optional, List, Tuple
from .ui import print_error, print_info, print_section, print_success, print_warning


SERVICE_ACCOUNT_NAME = 'laminar-workload'
K8S_SERVICE_ACCOUNT_NAME = 'laminar-workload-sa'


def get_gcp_project_from_context(context: str) -> Optional[str]:
    """
    Extract GCP project ID from GKE kubectl context name.
    
    GKE context format: gke_PROJECT-ID_REGION_CLUSTER-NAME
    
    Args:
        context: kubectl context name
        
    Returns:
        Project ID or None if not a GKE context
    """
    if context.startswith('gke_'):
        parts = context.split('_')
        if len(parts) >= 2:
            return parts[1]
    return None


def create_gcs_hmac_keys(
    project_id: str,
    buckets: List[str]
) -> Optional[Tuple[str, str]]:
    """
    Create HMAC keys for GCS S3-compatible API access.
    
    ClickHouse's S3 disk type doesn't support GCP Workload Identity natively,
    so we use HMAC keys (S3-compatible credentials) instead.
    
    Args:
        project_id: GCP project ID
        buckets: List of GCS bucket names to grant access to
        
    Returns:
        Tuple of (access_key_id, secret) or None if setup failed
    """
    print_section("Setting Up GCS HMAC Keys for ClickHouse")
    
    sa_email = f"{SERVICE_ACCOUNT_NAME}@{project_id}.iam.gserviceaccount.com"
    
    print_info(f"Creating GCP service account: {SERVICE_ACCOUNT_NAME}...")
    result = subprocess.run(
        [
            'gcloud', 'iam', 'service-accounts', 'create', SERVICE_ACCOUNT_NAME,
            '--project', project_id,
            '--display-name', 'Laminar Data Plane GCS Access'
        ],
        capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print_success(f"Service account created: {sa_email}")
    elif 'already exists' in result.stderr.lower():
        print_info(f"Service account already exists: {sa_email}")
    else:
        print_error(f"Failed to create service account: {result.stderr}")
        return None
    
    # Grant bucket-level permissions (scope to specific buckets, not project-wide)
    print_info(f"Granting Storage Object Admin role on {len(buckets)} bucket(s)...")
    all_success = True
    for bucket in buckets:
        result = subprocess.run(
            [
                'gcloud', 'storage', 'buckets', 'add-iam-policy-binding',
                f'gs://{bucket}',
                '--member', f'serviceAccount:{sa_email}',
                '--role', 'roles/storage.objectAdmin'
            ],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print_success(f"  ✓ Permissions granted for bucket: {bucket}")
        else:
            # Check if it's just a "binding already exists" case
            if 'already exists' in result.stderr.lower() or 'no change' in result.stderr.lower():
                print_info(f"  ✓ Permissions already exist for bucket: {bucket}")
            else:
                print_warning(f"  ✗ Failed to grant permissions for bucket {bucket}: {result.stderr[:100]}")
                all_success = False
    
    if not all_success:
        print_warning("Some bucket permissions may need manual configuration")
    
    print_info(f"Creating HMAC keys for service account: {sa_email}...")
    result = subprocess.run(
        ['gsutil', 'hmac', 'create', sa_email],
        capture_output=True, text=True
    )
    
    if result.returncode != 0:
        print_error(f"Failed to create HMAC keys: {result.stderr}")
        return None
    
    # Parse the output to extract Access ID and Secret
    # Output format:
    # Access ID:   GOOG1E...
    # Secret:      abc123...
    access_id = None
    secret = None
    
    for line in result.stdout.splitlines():
        if line.startswith('Access ID:'):
            access_id = line.split(':', 1)[1].strip()
        elif line.startswith('Secret:'):
            secret = line.split(':', 1)[1].strip()
    
    if not access_id or not secret:
        print_error("Failed to parse HMAC keys from gsutil output")
        return None
    
    print()
    print_success("HMAC keys created successfully!")
    print_info(f"Access Key ID: {access_id}")
    print_warning("Secret access key has been generated (will be stored in Kubernetes Secret)")
    print()
    print_info("Note: ClickHouse uses these HMAC keys to access GCS via the S3-compatible API.")
    print_info(f"Service account: {sa_email}")
    
    return (access_id, secret)
