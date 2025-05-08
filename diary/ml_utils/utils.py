# diary/ml_utils/utils.py
import logging
from typing import List, Dict

import pandas as pd

from diary.models import Entry, EntryValue, Parameter

logger = logging.getLogger("diary.ml_utils.utils")


def get_diary_dataframe() -> pd.DataFrame:
    """Загружает все записи дневника в виде **pandas DataFrame**.

    *Строки* — это даты,
    *столбцы* — **machine‑friendly** ключи параметров (``Parameter.key``),
    *значения* — числовые (``float``).

    Экспортирует *отладочную* копию в «debug_diary_dataframe.xlsx» 📊.
    """

    # Получаем все активные параметры и строим карту id → key
    parameters = Parameter.objects.filter(active=True)
    id_to_key: Dict[int, str] = {p.id: p.key for p in parameters}

    # Выгружаем записи дневника, отсортированные по дате
    entries = Entry.objects.all().order_by("date")

    data: List[Dict[str, float]] = []
    for entry in entries:
        row: Dict[str, float] = {"date": entry.date}

        # Собираем значения параметров за конкретную дату
        for ev in EntryValue.objects.filter(entry=entry):
            key = id_to_key.get(ev.parameter_id)
            if key:
                row[key] = ev.value
        data.append(row)

    # Преобразуем в DataFrame и заменяем пропуски на 0.0
    df = pd.DataFrame(data).fillna(0.0)

    # Логируем первые десять строк
    logger.debug("🧞 DataFrame head used for training:\n%s", df.head(10).to_string())

    # Сохраняем копию для ручной проверки
    df.to_excel("debug_diary_dataframe.xlsx", index=False)

    return df
