import pandas as pd
from diary.models import Entry, EntryValue, Parameter
from slugify import slugify
from datetime import datetime

# Заменить путь на свой
file_path = 'E:/My_Projects/Codding/Python/analytic-system/scripts/Короткая таблица.xlsx'

df = pd.read_excel(file_path)

# Преобразуем заголовки: убираем пробелы
columns = [col.strip() for col in df.columns]
df.columns = columns

print("\n>>> Начинаем импорт...")
for index, row in df.iterrows():
    date_str = str(row[columns[0]]).strip()
    try:
        entry_date = pd.to_datetime(date_str).date()
    except Exception as e:
        print(f"[!] Невалидная дата '{date_str}': {e}")
        continue

    entry, _ = Entry.objects.get_or_create(date=entry_date)
    print(f"\n📅 Обработка даты: {entry_date}")

    for col in columns[1:]:  # Пропускаем колонку с датой
        value = row[col]
        if pd.isnull(value):
            continue

        name_ru = col.strip()
        param = Parameter.objects.filter(name_ru=name_ru).first()
        if not param:
            key = slugify(name_ru)
            if not key:
                key = f"param_{Parameter.objects.count() + 1}"
            param = Parameter.objects.create(name_ru=name_ru, key=key)
            print(f"➕ Создан параметр: {name_ru} (key={key})")

        ev, created = EntryValue.objects.update_or_create(
            entry=entry,
            parameter=param,
            defaults={"value": float(value)}
        )
        print(f"  {'🆕' if created else '✏️'} {param.name_ru} = {value}")

print("\n✅ Импорт завершён")
