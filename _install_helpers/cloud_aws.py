"""AWS-specific operations for EKS and IAM configuration."""

import json
import subprocess
from typing import Optional, List
from .ui import print_error, print_info, print_section, print_success, print_warning
from .input_utils import get_input


def get_eks_nodegroup_role(cluster_name: str) -> Optional[str]:
    """
    Get the IAM role name for an EKS node group.
    
    Args:
        cluster_name: Name of the EKS cluster
        
    Returns:
        IAM role name or None if not found
    """
    try:
        result = subprocess.run(
            ['aws', 'eks', 'list-nodegroups', '--cluster-name', cluster_name],
            capture_output=True, text=True, check=True
        )
        nodegroups = json.loads(result.stdout).get('nodegroups', [])
        if not nodegroups:
            return None
        
        nodegroup_name = nodegroups[0]
        result = subprocess.run(
            [
                'aws', 'eks', 'describe-nodegroup',
                '--cluster-name', cluster_name,
                '--nodegroup-name', nodegroup_name,
                '--query', 'nodegroup.nodeRole',
                '--output', 'text'
            ],
            capture_output=True, text=True, check=True
        )
        role_arn = result.stdout.strip()
        
        if role_arn and '/' in role_arn:
            return role_arn.split('/')[-1]
        return None
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return None


def setup_aws_iam_policy(cluster_name: str, buckets: List[str], region: str) -> bool:
    """
    Attach S3 permissions to the EKS node group IAM role.
    
    Args:
        cluster_name: Name of the EKS cluster
        buckets: List of S3 bucket names to grant access to
        region: AWS region
        
    Returns:
        True if successful, False otherwise
    """
    print_section("Setting Up AWS IAM Permissions")
    
    print_info("Detecting EKS node group IAM role...")
    role_name = get_eks_nodegroup_role(cluster_name)
    
    if not role_name:
        print_warning("Could not automatically detect node group IAM role")
        role_name = get_input("Enter the node group IAM role name", required=True)
    else:
        print_success(f"Detected IAM role: {role_name}")
    
    resources = []
    for bucket in buckets:
        resources.extend([
            f"arn:aws:s3:::{bucket}/*",
            f"arn:aws:s3:::{bucket}"
        ])
    
    policy_doc = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": resources
        }]
    }
    
    print_info("Attaching S3 access policy to IAM role...")
    try:
        subprocess.run(
            [
                'aws', 'iam', 'put-role-policy',
                '--role-name', role_name,
                '--policy-name', 'LaminarDataPlaneS3Access',
                '--policy-document', json.dumps(policy_doc)
            ],
            capture_output=True, text=True, check=True
        )
        print_success("IAM policy attached successfully")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to attach IAM policy: {e.stderr}")
        return False
