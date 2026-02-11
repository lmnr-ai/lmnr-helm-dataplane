"""Constants and configuration values for the installer."""

from pathlib import Path

# ANSI color codes for terminal output
BOLD = '\033[1m'
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
CYAN = '\033[96m'

# Installation configuration
RELEASE_NAME = 'laminar-dataplane'
LB_SERVICE_NAME = 'laminar-data-plane-proxy-lb'
CHART_DIR = str(Path(__file__).resolve().parent.parent)
VALUES_FILE = Path(CHART_DIR) / 'laminar.yaml'

# Default values
DEFAULT_AWS_REGION = 'us-east-1'
DEFAULT_GCP_REGION = 'us-central1'
DEFAULT_NAMESPACE = 'default'
DEFAULT_PROXY_REPLICAS = 1
DEFAULT_PROXY_CPU = '1'
DEFAULT_PROXY_MEMORY = '2Gi'
DEFAULT_CH_CPU = '2'
DEFAULT_CH_MEMORY = '4Gi'
DEFAULT_CH_STORAGE_SIZE = '100Gi'
DEFAULT_LB_PORT = '40080'

# Timeouts and retries
LB_MAX_ATTEMPTS = 30
LB_INITIAL_WAIT = 2
LB_MAX_WAIT = 10

# Security
PASSWORD_LENGTH = 64  # hex characters for ClickHouse password
BUCKET_SUFFIX_LENGTH = 8  # hex characters for bucket uniqueness

# Timing estimates (in seconds)
ESTIMATE_PREREQUISITES = 5
ESTIMATE_CONFIGURATION = 180  # 2-5 minutes (user dependent, use lower bound)
ESTIMATE_HELM_INSTALL = 45  # 30-60 seconds
ESTIMATE_POD_READINESS = 150  # 2-3 minutes
ESTIMATE_TOTAL_MIN = 5  # Total time in minutes (lower bound)
ESTIMATE_TOTAL_MAX = 10  # Total time in minutes (upper bound)
