from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(r"C:\Users\Inaki Senar\Documents\GitHub\AI-Factory-v2")
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from openai_key_manager import (
    OpenAIMasterKeyManager,
    get_openai_api_key,
    get_openai_manager,
    setup_openai_env,
)

__all__ = [
    "OpenAIMasterKeyManager",
    "get_openai_api_key",
    "get_openai_manager",
    "setup_openai_env",
]
