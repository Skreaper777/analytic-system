# diary/ml_utils/utils.py
import pandas as pd
import logging
from diary.models import Entry, EntryValue, Parameter

def get_diary_dataframe():
    """
    Загружает все записи дневника в виде pandas DataFrame, где строки — это даты,
    а столбцы — имена параметров (на русском). Значения — числовые.
    """
    entries = Entry.objects.all().order_by('date')
    parameters = Parameter.objects.filter(active=True)
    id_to_name = {p.id: p.name_ru for p in parameters}

    data = []
    for entry in entries:
        row = {'date': entry.date}
        values = EntryValue.objects.filter(entry=entry)
        for ev in values:
            name = id_to_name.get(ev.parameter_id)
            if name:
                row[name] = ev.value
        data.append(row)

    df = pd.DataFrame(data)
    df = df.fillna(0.0)

    logger = logging.getLogger('diary.ml_utils.utils')
    logger.debug(f"🧞 DataFrame head used for training:\n{df.head(10).to_string()}")

    # Сохраняем отладочную таблицу
    df.to_excel("debug_diary_dataframe.xlsx", index=False)

    return df
