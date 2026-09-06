"""Pluggable graphic engines for F1 content production.

External engines are adapters only. The publishing pipeline consumes immutable
final assets and must not depend on a specific provider.
"""

from .engine_router import generate_final_visual

__all__ = ["generate_final_visual"]
