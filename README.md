# Laminar Data Plane - Helm Chart

Deploy a self-hosted Laminar Data Plane on Kubernetes. This chart provisions a ClickHouse instance with authenticated access via the Laminar Data Plane Proxy.

## Architecture

```
Internet ──► LoadBalancer (:40080) ──► Data Plane Proxy (:8080) ──► ClickHouse (:8123)
```

**Components:**

| Component | Kind | Description |
|---|---|---|
| ClickHouse | StatefulSet | Column-oriented database for trace/log storage |
| Data Plane Proxy | Deployment | Authenticated proxy that fronts ClickHouse |
| Migration Runner | Init Container | Runs ClickHouse schema migrations on startup |

## Prerequisites

1. **Kubernetes cluster** — AWS EKS or GCP GKE (or any conformant cluster)
   
   **Minimum cluster requirements:**
   - **2 vCPUs** and **4GB RAM** available for workload pods (defaults: 0.5 CPU/1GB for proxy, 1 CPU/2GB for ClickHouse)
   - **1 node** minimum (2+ nodes recommended for high availability)
   - **100GB+ persistent storage** for ClickHouse data volume

   <details>
   <summary><b>Creating a cluster on AWS EKS</b></summary>

   ```bash
   # Install eksctl if not already installed
   # https://eksctl.io/installation/

   # Create a cluster with a managed node group
   eksctl create cluster \
     --name laminar-dataplane \
     --region us-east-1 \
     --nodegroup-name standard-workers \
     --node-type t3.xlarge \
     --nodes 2 \
     --nodes-min 1 \
     --nodes-max 3 \
     --managed

   # Configure kubectl
   aws eks update-kubeconfig --region us-east-1 --name laminar-dataplane
   ```

   **Node type recommendations:**
   - **Minimum:** `t3.large` (2 vCPU, 8GB RAM) - suitable for small workloads
   - **Production:** `t3.xlarge` (4 vCPU, 16GB RAM) or larger, with 2+ nodes for availability

   </details>

   <details>
   <summary><b>Creating a cluster on GCP GKE</b></summary>

   ```bash
   # Set your project and region
   export PROJECT_ID=your-project-id
   export REGION=us-central1

   # Create a GKE cluster
   gcloud container clusters create laminar-dataplane \
     --project=$PROJECT_ID \
     --region=$REGION \
     --node-locations=$REGION-a # limit to 1 AZ for cost efficiency (default 3)
     --machine-type=n1-standard-4 \
     --num-nodes=2 \
     --disk-size=100 \
     --enable-autoscaling \
     --min-nodes=1 \
     --max-nodes=3 \
     --enable-ip-alias \
     --workload-pool=$PROJECT_ID.svc.id.goog

   # Configure kubectl
   gcloud container clusters get-credentials laminar-dataplane \
     --region=$REGION \
     --project=$PROJECT_ID
   ```

   **Node type recommendations:**
   - **Minimum:** `e2-standard-2` (2 vCPU, 8GB RAM) - suitable for small workloads
   - **Production:** `n1-standard-4` (4 vCPU, 15GB RAM) or larger, with 2+ nodes per zone for availability

   </details>

2. **kubectl** — installed and configured to the correct cluster context
   ```bash
   # Verify your context
   kubectl config current-context
   ```

3. **Helm 3** — installed
   ```bash
   # Verify
   helm version
   ```

4. **Data Plane Public Key** — provided by Laminar

5. **Cloud storage bucket and IAM setup** — Optional for production deployments using S3/GCS backend:

   **The interactive installer automates this setup** if you have the cloud CLI installed (`aws` for AWS, `gsutil` for GCP). It will:
   - Create bucket with globally unique name
   - Configure IAM roles (AWS) or HMAC keys (GCP)
   - Grant storage permissions automatically

   <details>
   <summary><b>Manual AWS EKS Setup (if not using install.py)</b></summary>

   1. **Create S3 bucket:**
      ```bash
      aws s3 mb s3://lmnr-clickhouse-data-XXXXXX --region us-east-1
      ```

   2. **Attach S3 permissions to the node group IAM role:**
      ```bash
      # Get your node group role name
      ROLE_NAME=$(aws eks describe-nodegroup \
        --cluster-name your-cluster-name \
        --nodegroup-name your-nodegroup-name \
        --query 'nodegroup.nodeRole' --output text | cut -d'/' -f2)
      
      # Attach policy
      aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name LaminarDataPlaneS3Access \
        --policy-document '{
          "Version": "2012-10-17",
          "Statement": [{
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
            "Resource": [
              "arn:aws:s3:::lmnr-clickhouse-data-XXXXXX/*",
              "arn:aws:s3:::lmnr-clickhouse-data-XXXXXX"
            ]
          }]
        }'
      ```

   </details>

   <details>
   <summary><b>Manual GCP GKE Setup (if not using install.py)</b></summary>

   1. **Create GCS bucket:**
      ```bash
      gsutil mb -l us-central1 gs://lmnr-clickhouse-data-XXXXXX
      ```

   2. **Create GCP service account and HMAC keys:**
      ```bash
      export PROJECT_ID=your-project-id
      
      # Create GCP service account
      gcloud iam service-accounts create laminar-workload \
        --project=$PROJECT_ID \
        --display-name="Laminar Data Plane GCS Access"
      
      # Grant storage permissions
      gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:laminar-workload@$PROJECT_ID.iam.gserviceaccount.com" \
        --role="roles/storage.objectAdmin"
      
      # Create HMAC keys for S3-compatible access
      gsutil hmac create laminar-workload@$PROJECT_ID.iam.gserviceaccount.com
      ```

      Save the Access ID and Secret — you'll need to provide them in `values.yaml`.

   **Note:** ClickHouse uses HMAC keys (not Workload Identity) because its S3 disk type doesn't support GCP Workload Identity natively. HMAC keys provide S3-compatible authentication for GCS.

   </details>

## Quick Start (Interactive Installer)

The interactive installer requires only Python 3 (no pip dependencies).

```bash
git clone https://github.com/lmnr-ai/lmnr-helm-dataplane.git
cd lmnr-helm-dataplane
python3 install.py
```

The installer will:
1. Check that `kubectl` and `helm` are available
2. Walk you through configuration (namespace, cloud provider, credentials, buckets, resources)
3. **Automatically configure cloud storage authentication** (AWS IAM or GCP HMAC keys)
4. Generate a `laminar.yaml` values override file with your settings
5. Run `helm upgrade --install` with `laminar.yaml`
6. Wait for the LoadBalancer and print the external URL

**Estimated time:** 5-10 minutes

**Interactive features:**
- Use **arrow keys** to navigate input history
- Press **Ctrl-C** at any prompt to retry that section or exit
- Use `--help` to see all available options

### CLI Options

```bash
# Show help and usage information
python3 install.py --help

# Update existing installation (shorthand: -u)
python3 install.py --update-only
python3 install.py -u
```

### Updating an Existing Installation

Your configuration is persisted in `laminar.yaml`. You can edit this file directly, then re-apply:

```bash
python3 install.py -u
```

This re-runs `helm upgrade --install` using the existing `laminar.yaml`, which also pulls latest container images.

## Manual Installation

If you prefer to run Helm directly:

```bash
helm upgrade --install laminar-dataplane . \
  --namespace laminar \
  --create-namespace \
  --set cloudProvider=aws \
  --set dataPlaneProxy.dataPlanePublicKey="YOUR_PUBLIC_KEY" \
  --set clickhouse.password="YOUR_CLICKHOUSE_PASSWORD"
```

Or create a `laminar.yaml` file and use `-f`:

```bash
helm upgrade --install laminar-dataplane . \
  --namespace laminar \
  --create-namespace \
  -f laminar.yaml
```

After installation, get the LoadBalancer URL:

```bash
# AWS EKS (hostname)
kubectl get svc laminar-data-plane-proxy-lb -n laminar \
  -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'

# GCP GKE (IP)
kubectl get svc laminar-data-plane-proxy-lb -n laminar \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

## Configuration Reference

### Global

| Parameter | Description | Default |
|---|---|---|
| `cloudProvider` | Cloud provider (`aws` or `gcp`). Sets default LB annotations. | `""` |

### Data Plane Proxy

| Parameter | Description | Default |
|---|---|---|
| `dataPlaneProxy.dataPlanePublicKey` | **Required.** Public key from Laminar | `""` |
| `dataPlaneProxy.image.repository` | Proxy image | `ghcr.io/lmnr-ai/lmnr-data-plane-proxy` |
| `dataPlaneProxy.image.tag` | Proxy image tag | `latest` |
| `dataPlaneProxy.initImage.repository` | Migration runner image | `ghcr.io/lmnr-ai/lmnr-data-plane-proxy-init-migration-runner` |
| `dataPlaneProxy.initImage.tag` | Migration runner image tag | `latest` |
| `dataPlaneProxy.replicaCount` | Number of proxy replicas | `1` |
| `dataPlaneProxy.resources.requests.cpu` | CPU request | `"1"` |
| `dataPlaneProxy.resources.requests.memory` | Memory request | `"2Gi"` |
| `dataPlaneProxy.resources.limits.cpu` | CPU limit | `"1"` |
| `dataPlaneProxy.resources.limits.memory` | Memory limit | `"2Gi"` |
| `dataPlaneProxy.loadBalancer.enabled` | Create a LoadBalancer service | `true` |
| `dataPlaneProxy.loadBalancer.port` | External port | `40080` |
| `dataPlaneProxy.loadBalancer.annotations` | Service annotations (cloud-specific) | `{}` |
| `dataPlaneProxy.nodeSelector` | Node selector | `{}` |
| `dataPlaneProxy.tolerations` | Tolerations | `[]` |
| `dataPlaneProxy.affinity` | Affinity rules | `{}` |

### ClickHouse

| Parameter | Description | Default |
|---|---|---|
| `clickhouse.password` | **Required.** ClickHouse password | `""` |
| `clickhouse.user` | ClickHouse username | `default` |
| `clickhouse.database` | ClickHouse database name | `default` |
| `clickhouse.image.repository` | ClickHouse image | `clickhouse/clickhouse-server` |
| `clickhouse.image.tag` | ClickHouse image tag | `latest` |
| `clickhouse.persistence.enabled` | Enable persistent storage | `true` |
| `clickhouse.persistence.size` | PVC size | `100Gi` |
| `clickhouse.persistence.storageClass` | Storage class (empty = cluster default) | `""` |
| `clickhouse.resources.requests.cpu` | CPU request | `"2"` |
| `clickhouse.resources.requests.memory` | Memory request | `"4Gi"` |
| `clickhouse.resources.limits.cpu` | CPU limit | `"2"` |
| `clickhouse.resources.limits.memory` | Memory limit | `"4Gi"` |
| `clickhouse.s3.enabled` | Enable S3/GCS object storage | `false` |
| `clickhouse.s3.endpoint` | S3 endpoint URL | `""` |
| `clickhouse.s3.region` | S3 region | `""` |
| `clickhouse.s3.accessKeyId` | Explicit access key (optional) | `""` |
| `clickhouse.s3.secretAccessKey` | Explicit secret key (optional) | `""` |
| `clickhouse.s3.useEnvironmentCredentials` | Use IAM/workload identity | `false` |
| `clickhouse.s3.cache.enabled` | Enable local S3 cache | `true` |
| `clickhouse.s3.cache.maxSize` | Max cache size | `"10Gi"` |
| `clickhouse.nodeSelector` | Node selector | `{}` |
| `clickhouse.tolerations` | Tolerations | `[]` |
| `clickhouse.affinity` | Affinity rules | `{}` |

## Cloud-Specific Notes

### LoadBalancer Annotations

When `cloudProvider` is set, default LoadBalancer annotations are applied automatically:

**AWS EKS** (`cloudProvider: aws`):
```yaml
service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "tcp"
```

**GCP GKE** (`cloudProvider: gcp`):
```yaml
networking.gke.io/load-balancer-type: "External"
```

To override any default annotation, set it in `dataPlaneProxy.loadBalancer.annotations`. Your values take precedence over the defaults.

### S3/GCS Object Storage

> **⚠️ IMPORTANT:** S3/GCS storage requires proper authentication setup (see [Prerequisites](#prerequisites)).

For S3 (AWS) with node group IAM role:
```yaml
clickhouse:
  s3:
    enabled: true
    endpoint: "https://s3.us-east-1.amazonaws.com/your-bucket/data/"
    region: us-east-1
    useEnvironmentCredentials: true
```

For GCS (S3-compatible API) with HMAC keys:
```yaml
cloudProvider: gcp
clickhouse:
  s3:
    enabled: true
    endpoint: "https://storage.googleapis.com/your-bucket/data/"
    region: us-east1
    accessKeyId: "GOOG1E..."
    secretAccessKey: "your-hmac-secret"
    useEnvironmentCredentials: false
```

**Note:** ClickHouse uses HMAC keys for GCS because its S3 disk type doesn't support GCP Workload Identity. The installer can create these automatically with `gsutil hmac create`.

**First-time setup recommendation:** Start with S3 disabled (`enabled: false`) to verify the cluster works, then enable S3 after configuring authentication.

## Upgrading

```bash
helm upgrade laminar-dataplane . --namespace laminar --reuse-values
```

Or with the installer:

```bash
python3 install.py -u
```

## Uninstalling

```bash
helm uninstall laminar-dataplane --namespace laminar
```

> **Note:** The ClickHouse PersistentVolumeClaim is not deleted automatically.
> To fully remove data: `kubectl delete pvc -l app.kubernetes.io/name=laminar-clickhouse -n laminar`
