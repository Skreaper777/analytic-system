import pandas as pd
from diary.models import Entry, EntryValue, Parameter
from slugify import slugify
from datetime import datetime
import os
from django.conf import settings

def run_excel_import():
    file_path = os.path.join(settings.BASE_DIR, 'diary', 'scripts', 'Короткая таблица.xlsx')

    df = pd.read_excel(file_path)
    columns = [col.strip() for col in df.columns]
    df.columns = columns

    print("\n>>> Начинаем импорт...")

    param_cache = {p.name_ru: p for p in Parameter.objects.all()}
    param_counter = len(param_cache)

    entries = {}
    entry_values_to_create = []
    entry_values_to_update = []
    existing_entry_values = {(ev.entry_id, ev.parameter_id): ev for ev in EntryValue.objects.all()}

    for index, row in df.iterrows():
        date_str = str(row[columns[0]]).strip()
        try:
            entry_date = pd.to_datetime(date_str).date()
        except Exception as e:
            print(f"[!] Невалидная дата '{date_str}': {e}")
            continue

        if entry_date not in entries:
            entries[entry_date], _ = Entry.objects.get_or_create(date=entry_date)

        entry = entries[entry_date]
        print(f"\n📅 Обработка даты: {entry_date}")

        for col in columns[1:]:
            value = row[col]
            if pd.isnull(value):
                continue

            name_ru = col.strip()
            param = param_cache.get(name_ru)
            if not param:
                key = slugify(name_ru)
                if not key:
                    param_counter += 1
                    key = f"param_{param_counter}"
                param = Parameter.objects.create(name_ru=name_ru, key=key)
                param_cache[name_ru] = param
                print(f"➕ Создан параметр: {name_ru} (key={key})")

            key_tuple = (entry.id, param.id)
            if key_tuple in existing_entry_values:
                ev = existing_entry_values[key_tuple]
                ev.value = float(value)
                entry_values_to_update.append(ev)
                print(f"  ✏️ {param.name_ru} = {value}")
            else:
                entry_values_to_create.append(EntryValue(entry=entry, parameter=param, value=float(value)))
                print(f"  🆕 {param.name_ru} = {value}")

    if entry_values_to_create:
        EntryValue.objects.bulk_create(entry_values_to_create)
    if entry_values_to_update:
        EntryValue.objects.bulk_update(entry_values_to_update, ["value"])

    created_count = len(entry_values_to_create)
    updated_count = len(entry_values_to_update)

    print(f"\n✅ Импорт завершён. Создано: {created_count}, обновлено: {updated_count}")
    return created_count, updated_count
