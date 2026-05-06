from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path(r"C:\Users\Inaki Senar\Documents\GitHub\AI-Factory-v2")
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from openai_key_manager import get_openai_api_key


def generate_env() -> int:
    api_key = get_openai_api_key()
    if not api_key:
        print("No OpenAI API key available.")
        return 1

    Path(".env").write_text(f'OPENAI_API_KEY="{api_key}"\n', encoding="utf-8")
    print("Generated .env with OPENAI_API_KEY")
    return 0


if __name__ == "__main__":
    raise SystemExit(generate_env())
