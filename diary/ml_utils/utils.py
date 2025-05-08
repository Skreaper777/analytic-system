# ---------- diary/ml_utils/utils.py ----------
import logging
from typing import Dict, List

import pandas as pd

from diary.models import Entry, EntryValue, Parameter

logger = logging.getLogger('diary.ml_utils.utils')


def get_diary_dataframe() -> pd.DataFrame:
    """Загружает все записи дневника в виде **pandas.DataFrame**.

    * Строки* — даты (`Entry.date`).
    * Столбцы* — machine‑friendly ключи параметров (`Parameter.key`).
    * Значения* — числовые оценки пользователя.

    💡 **Отладка**: отдельно сохраняем копию DataFrame c *русскими названиями*
    параметров (`Parameter.name_ru`) в `debug_diary_dataframe.xlsx`. Это не
    влияет на работу ML‑части и остальных функций.
    """

    entries = Entry.objects.all().order_by('date')
    parameters = Parameter.objects.filter(active=True)

    id_to_key: Dict[int, str] = {p.id: p.key for p in parameters}

    data: List[dict] = []
    for entry in entries:
        row = {'date': entry.date}
        values = EntryValue.objects.filter(entry=entry)
        for ev in values:
            key = id_to_key.get(ev.parameter_id)
            if key:
                row[key] = ev.value
        data.append(row)

    # DataFrame с ключами — используется повсеместно
    df = pd.DataFrame(data).fillna(0.0)

    logger.debug('🧞 DataFrame head (keys):\n%s', df.head(10).to_string())

    # ---- Excel‑вариант ----
    key_to_name = {p.key: p.name_ru for p in parameters}
    df_excel = df.rename(columns=key_to_name)
    try:
        df_excel.to_excel('debug_diary_dataframe.xlsx', index=False)
        logger.debug('📝 debug_diary_dataframe.xlsx обновлён (%d строк)', len(df_excel))
    except Exception as exc:
        logger.warning('Не удалось сохранить debug_diary_dataframe.xlsx: %s', exc)

    return df