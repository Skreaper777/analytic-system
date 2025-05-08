# diary/ml_utils/base_model.py
"""
Базовая линейная регрессия для дневника.

• Удаляем системные колонки даты (`date`, `Дата`) + сам `target`.
• Исключаем все признаки, которые пользователь уже ввёл сегодня (`exclude`),
  чтобы не допустить утечки «будущей» информации в обучение.
• Заполняем пропуски нулями: отсутствие симптома трактуем как 0.0.

Функция возвращает словарь:
    {
        "model": sklearn.linear_model.LinearRegression,
    }
Дополнительные ключи добавлять не нужно — вьюхи берут `feature_names_in_`
непосредственно из `model`.
"""
from __future__ import annotations

from typing import List

import pandas as pd
from sklearn.linear_model import LinearRegression

# Колонки, которые *всегда* выкидываем из признаков
DROP_ALWAYS: List[str] = ["date", "Дата"]


def train_model(df: pd.DataFrame, target: str, *, exclude: list[str] | None = None):
    """Обучает линейную регрессию.

    Parameters
    ----------
    df : pd.DataFrame
        Исторические данные (широкий формат).
    target : str
        Имя целевого столбца, который нужно предсказать.
    exclude : list[str] | None
        Признаки, уже заполненные пользователем сегодня.
    """
    if exclude is None:
        exclude = []

    # 1️⃣ Формируем матрицу признаков
    drop_cols = DROP_ALWAYS + exclude + [target]
    X = df.drop(columns=drop_cols, errors="ignore").fillna(0.0)
    y = df[target]

    # 2️⃣ Обучаем модель
    model = LinearRegression()
    model.fit(X, y)

    return {"model": model}
