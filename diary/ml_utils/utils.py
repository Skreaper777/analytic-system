# diary/ml_utils/utils.py
import pandas as pd
import logging
from diary.models import Entry, EntryValue, Parameter

def get_diary_dataframe():
    """
    Загружает все записи дневника в виде pandas DataFrame, где строки — это даты,
    а столбцы — ключи параметров. Значения — числовые.
    """
    entries = Entry.objects.all().order_by('date')
    parameters = {p.id: p.key for p in Parameter.objects.filter(active=True)}

    data = []
    for entry in entries:
        row = {'date': entry.date}
        values = EntryValue.objects.filter(entry=entry)
        for ev in values:
            key = parameters.get(ev.parameter_id)
            if key:
                row[key] = ev.value
        data.append(row)

    df = pd.DataFrame(data)
    df = df.fillna(0.0)

    logger = logging.getLogger('diary.ml_utils.utils')
    logger.debug(f"🧞 DataFrame head used for training:\n{df.head(10).to_string()}")

    return df
