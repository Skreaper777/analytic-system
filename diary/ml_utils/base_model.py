# diary/ml_utils/base_model.py
"""Базовая линейная регрессия (возвращает модель + порядок колонок).

• Всегда исключаем `date/Дата` + `exclude` + `target`.
• Заполняем NaN нулями.
• Логи пишем через стандартный `logging` → попадают в diary.log.
"""
from __future__ import annotations

import logging
from typing import List

import pandas as pd
from sklearn.linear_model import LinearRegression

logger = logging.getLogger("predict")  # было __name__ — заменено на predict

DROP_ALWAYS: List[str] = ["date", "Дата"]

def train_model(
    df: pd.DataFrame,
    target: str,
    *,
    exclude: list[str] | None = None,
):
    if exclude is None:
        exclude = []

    drop_cols = DROP_ALWAYS + exclude + [target]
    X = df.drop(columns=drop_cols, errors="ignore").fillna(0.0)
    y = df[target]

    logger.debug("train_model: target=%s, X_shape=%s, exclude=%s", target, X.shape, exclude)
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    if X.shape[1] == 0:
        logger.warning("train_model: Пропущено обучение для '%s' — нет признаков (X пуст)", target)
        for h in logger.handlers:
            try:
                h.flush()
            except Exception:
                pass
        return {"model": None, "features": []}

    model = LinearRegression()
    model.fit(X, y)

    logger.debug("trained %s: intercept=%.3f", target, model.intercept_)
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    return {"model": model, "features": X.columns.tolist()}