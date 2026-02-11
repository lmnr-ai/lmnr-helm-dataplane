"""Storage bucket operations for S3 and GCS."""

import subprocess
import sys
from typing import Dict
from .ui import print_error, print_info, print_success, print_warning
from .input_utils import get_input, get_yes_no
from .constants import VALUES_FILE


def create_bucket(cloud_provider: str, bucket_name: str, region: str) -> bool:
    """
    Create a cloud storage bucket.
    
    Args:
        cloud_provider: Either 'aws' or 'gcp'
        bucket_name: Name of the bucket to create
        region: Cloud region
        
    Returns:
        True on success, False otherwise
    """
    if cloud_provider == 'aws':
        cmd = ['aws', 's3', 'mb', f's3://{bucket_name}', '--region', region]
    else:
        cmd = ['gsutil', 'mb', '-l', region, f'gs://{bucket_name}']

    print_info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print_success(f"Bucket '{bucket_name}' created successfully")
        return True
    else:
        print_error(f"Failed to create bucket '{bucket_name}' (exit code {result.returncode})")
        print_info("The bucket may already exist, or you may lack permissions.")
        print_info("You can create it manually and re-run the installer.")
        return False


def construct_s3_endpoint(cloud_provider: str, bucket_name: str, region: str) -> str:
    """
    Construct the S3-compatible endpoint URL for a bucket.
    
    Args:
        cloud_provider: Either 'aws' or 'gcp'
        bucket_name: Name of the bucket
        region: Cloud region
        
    Returns:
        S3-compatible endpoint URL
    """
    if cloud_provider == 'aws':
        return f"https://s3.{region}.amazonaws.com/{bucket_name}/data/"
    else:
        return f"https://storage.googleapis.com/{bucket_name}/data/"


def parse_existing_buckets() -> Dict[str, any]:
    """
    Parse existing laminar.yaml to extract bucket names.
    
    Returns:
        Dictionary with 'ch_bucket' and 's3_enabled' keys
    """
    if not VALUES_FILE.exists():
        return {}
    
    existing = {}
    content = VALUES_FILE.read_text()
    lines = content.splitlines()
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if stripped.startswith('enabled:') and i > 0:
            context_lines = lines[max(0, i-5):i]
            if any('s3:' in context_line for context_line in context_lines):
                if 'true' in stripped:
                    existing['s3_enabled'] = True
        
        elif stripped.startswith('endpoint:') and i > 0:
            value = stripped.split(':', 1)[1].strip().strip('"\'')
            if value and ('s3.' in value or 'storage.googleapis.com' in value):
                parts = value.split('/')
                if len(parts) >= 4:
                    existing['ch_bucket'] = parts[3]
    
    return existing


def configure_bucket(
    cloud_provider: str,
    region: str,
    label: str,
    default_name: str,
    has_cloud_cli: bool
) -> str:
    """
    Interactive flow for configuring a single bucket.
    
    Args:
        cloud_provider: Either 'aws' or 'gcp'
        region: Cloud region
        label: Description of the bucket's purpose
        default_name: Default bucket name to suggest
        has_cloud_cli: Whether cloud CLI is available
        
    Returns:
        The bucket name
    """
    print()
    print_info(f"{label}:")
    bucket_name = get_input("  Bucket name", default=default_name)

    if has_cloud_cli:
        create = get_yes_no(
            f"  Create bucket '{bucket_name}' now? (recommended)",
            default=True
        )
        if create:
            success = create_bucket(cloud_provider, bucket_name, region)
            if not success:
                proceed = get_yes_no("  Continue anyway (bucket may already exist)?", default=True)
                if not proceed:
                    print_error("Aborting. Please create the bucket manually and re-run.")
                    sys.exit(1)
    else:
        cli_name = 'aws' if cloud_provider == 'aws' else 'gsutil'
        print_warning(
            f"  '{cli_name}' CLI not found. Make sure bucket '{bucket_name}' exists before proceeding."
        )
        print_info("  To create it manually:")
        if cloud_provider == 'aws':
            print_info(f"    aws s3 mb s3://{bucket_name} --region {region}")
        else:
            print_info(f"    gsutil mb -l {region} gs://{bucket_name}")

    return bucket_name
