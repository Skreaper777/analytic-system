# diary/ml_utils/utils.py
"""Utility helpers for ML data preparation.

* Экспортирует «сырые» данные в Excel с человеческими названиями столбцов
  (на русском) **без** автозаполнения нулями,
* а для обучения/предсказаний возвращает DataFrame с **machine‑friendly**
  `Parameter.key`‑колонками, где пропуски заменены на `0.0`.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd

from diary.models import Entry, EntryValue, Parameter

logger = logging.getLogger("diary.ml_utils.utils")


def get_diary_dataframe() -> pd.DataFrame:
    """Собирает все записи дневника в два представления.

    1. **df_excel** — колонки = `Parameter.name_ru`, пропуски *оставлены пустыми*;
       сохраняется в *debug_diary_dataframe.xlsx* для анализа.
    2. **df_keys**  — колонки = `Parameter.key`, пропуски -> `0.0`;
       именно его функция *возвращает* для ML‑моделей.
    """

    # --- Справочники ---
    parameters: List[Parameter] = list(Parameter.objects.filter(active=True))
    id_to_key: Dict[int, str] = {p.id: p.key for p in parameters}
    id_to_name: Dict[int, str] = {p.id: p.name_ru for p in parameters}

    # --- Сбор строк как «key»‑ и «name_ru»‑словарей параллельно ---
    rows_keys: List[Dict[str, object]] = []
    rows_names: List[Dict[str, object]] = []

    for entry in Entry.objects.all().order_by("date"):
        row_k: Dict[str, object] = {"date": entry.date}
        row_n: Dict[str, object] = {"date": entry.date}

        for ev in EntryValue.objects.filter(entry=entry):
            key = id_to_key.get(ev.parameter_id)
            name = id_to_name.get(ev.parameter_id)
            if key:
                row_k[key] = ev.value
            if name:
                row_n[name] = ev.value

        rows_keys.append(row_k)
        rows_names.append(row_n)

    # --- DataFrames ---
    df_keys: pd.DataFrame = pd.DataFrame(rows_keys)
    df_names: pd.DataFrame = pd.DataFrame(rows_names)

    # --- Удаляем полностью пустые строки (все параметры NaN, кроме даты) ---
    param_cols = [col for col in df_keys.columns if col != "date"]
    df_keys = df_keys.dropna(how="all", subset=param_cols)

    # --- Экспорт «человеческого» варианта ---
    df_names.to_excel("debug_diary_dataframe.xlsx", index=False)

    # --- Лог и возврат «machine»‑варианта ---
    logger.debug("🧞 DataFrame head used for training:\n%s", df_keys.head(10).to_string())
    for h in logger.handlers:
        try:
            h.flush()
        except Exception:
            pass

    return df_keys.fillna(0.0)