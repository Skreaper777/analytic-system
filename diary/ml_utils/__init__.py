# diary/ml_utils/__init__.py
"""ML-модуль дневника.

Пока активна **только** базовая линейная регрессия (`base_model`).
При необходимости можно вернуть `flags_model` и `hybrid_model`,
но они исключены из публичного интерфейса, чтобы не усложнять код.
"""
from . import base_model  # noqa: F401

__all__ = ["base_model"]
