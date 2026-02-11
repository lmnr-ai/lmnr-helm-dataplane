"""Utilities for collecting user input."""

from typing import Optional, List
import secrets
from .ui import print_error
from .constants import PASSWORD_LENGTH, BUCKET_SUFFIX_LENGTH

# Import readline for better input handling (arrow keys, history)
# This is optional - if not available, input() will still work
try:
    import readline
    # Enable tab completion and history
    readline.parse_and_bind('tab: complete')
    # Set history file size
    readline.set_history_length(1000)
    READLINE_AVAILABLE = True
except ImportError:
    # readline not available on some platforms (e.g., Windows without pyreadline)
    READLINE_AVAILABLE = False


def get_input(prompt: str, default: Optional[str] = None, required: bool = False) -> str:
    """
    Get user input with optional default value.
    
    Args:
        prompt: The prompt to display to the user
        default: Default value if user provides no input
        required: Whether input is required
        
    Returns:
        The user's input or default value
    """
    display_prompt = f"{prompt} [{default}]: " if default else f"{prompt}: "
    
    while True:
        value = input(display_prompt).strip()
        if not value and default:
            return default
        if not value and required:
            print_error("This field is required. Please provide a value.")
            continue
        if value or not required:
            return value


def get_yes_no(prompt: str, default: bool = True) -> bool:
    """
    Get a yes/no response from the user.
    
    Args:
        prompt: The question to ask
        default: Default value if user provides no input
        
    Returns:
        True for yes, False for no
    """
    default_str = "Y/n" if default else "y/N"
    while True:
        response = input(f"{prompt} ({default_str}): ").strip().lower()
        if not response:
            return default
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no']:
            return False
        print_error("Please enter 'y' or 'n'")


def get_choice(prompt: str, options: List[str]) -> int:
    """
    Present a numbered list of options and get user's choice.
    
    Args:
        prompt: The question to ask
        options: List of option strings
        
    Returns:
        Zero-based index of the chosen option
    """
    print(f"\n{prompt}")
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    
    while True:
        choice = input(f"\nEnter 1-{len(options)}: ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return idx
        except ValueError:
            pass
        print_error(f"Please enter a number between 1 and {len(options)}")


def generate_secure_password(length: int = PASSWORD_LENGTH) -> str:
    """Generate a cryptographically secure random password."""
    return secrets.token_hex(length)


def get_int_input(prompt: str, default: Optional[int] = None, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    """
    Get integer input from user with validation and retry.
    
    Args:
        prompt: The prompt to display to the user
        default: Default value if user provides no input
        min_value: Minimum acceptable value (inclusive)
        max_value: Maximum acceptable value (inclusive)
        
    Returns:
        The validated integer input
    """
    default_str = str(default) if default is not None else None
    
    while True:
        value = get_input(prompt, default=default_str, required=(default is None))
        if not value and default is not None:
            return default
        
        try:
            int_value = int(value)
            
            # Validate range
            if min_value is not None and int_value < min_value:
                print_error(f"Value must be at least {min_value}")
                continue
            if max_value is not None and int_value > max_value:
                print_error(f"Value must be at most {max_value}")
                continue
            
            return int_value
        except ValueError:
            print_error(f"Please enter a valid integer (got: '{value}')")


def generate_bucket_suffix(length: int = BUCKET_SUFFIX_LENGTH) -> str:
    """Generate a random suffix for bucket names to ensure global uniqueness."""
    return secrets.token_hex(length)
