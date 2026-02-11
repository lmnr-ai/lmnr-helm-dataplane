"""User interface utilities for displaying formatted output."""

from typing import Optional
from .constants import BOLD, BLUE, CYAN, GREEN, RED, YELLOW, RESET


def print_header(text: str) -> None:
    """Print a prominent header with decorative borders."""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text.center(70)}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_section(text: str) -> None:
    """Print a section header with lighter decoration."""
    print(f"\n{CYAN}{'─'*70}{RESET}")
    print(f"{BOLD}{CYAN}{text}{RESET}")
    print(f"{CYAN}{'─'*70}{RESET}\n")


def print_success(text: str) -> None:
    """Print a success message with a checkmark."""
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str) -> None:
    """Print an error message with an X mark."""
    print(f"{RED}✗ {text}{RESET}")


def print_warning(text: str) -> None:
    """Print a warning message with a warning symbol."""
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str) -> None:
    """Print an informational message with an info symbol."""
    print(f"{CYAN}ℹ {text}{RESET}")


def print_final_url(url: str, port: str) -> None:
    """Display the final LoadBalancer URL to the user."""
    print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
    print(f"{BOLD}{GREEN}  Laminar Data Plane is ready!{RESET}")
    print(f"{BOLD}{GREEN}{'='*70}{RESET}")
    print()
    print(f"  {BOLD}Data Plane URL:{RESET}  {CYAN}http://{url}:{port}{RESET}")
    print()
    print("  Copy this URL and provide it to Laminar, or point a DNS record to it.")
    print(f"\n{BOLD}{GREEN}{'='*70}{RESET}")
