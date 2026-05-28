"""Cost tracking stub for Narramancy.

Prints API call costs to console. Will be replaced with persistent
tracking in a future phase.
"""

from pathlib import Path


class CostTracker:
    def __init__(self, base_path: Path = None):
        self.base_path = base_path

    def log_api_call(self, provider: str, model: str, operation: str,
                     input_tokens: int, output_tokens: int):
        total = input_tokens + output_tokens
        import sys
        print(f"[cost] {provider}/{model} {operation}: {input_tokens}in + {output_tokens}out = {total} tokens", file=sys.stderr)
