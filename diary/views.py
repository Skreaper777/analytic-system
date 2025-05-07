import logging
import json
from datetime import date, datetime

import pandas as pd
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .forms import EntryForm
from .models import Entry, EntryValue, Parameter
from .ml_utils import get_diary_dataframe, train_model

# Настройка логгера для отладки: вывод в консоль и файл diary.log с форматированием времени
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%d/%b/%Y %H:%M:%S')

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

file_handler = logging.FileHandler('diary.log', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Добавляем обработчики к логгеру
logger.addHandler(console_handler)
logger.addHandler(file_handler)

def add_entry(request):
    date_str = request.GET.get('date')
    try:
        entry_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug(f"[add_entry] Invalid date format '{date_str}', fallback to today")

    logger.debug(f"[add_entry] Entry date: {entry_date}")
    entry, created = Entry.objects.get_or_create(date=entry_date)
    logger.debug(f"[add_entry] Entry fetched: id={entry.id}, created={created}, comment='{entry.comment}'")

    initial_data = {"comment": entry.comment}
    for ev in EntryValue.objects.filter(entry=entry):
        initial_data[ev.parameter.key] = ev.value
        logger.debug(f"[add_entry] Pre-fill {ev.parameter.key} = {ev.value}")

    logger.debug(f"[add_entry] Complete initial_data: {initial_data}")

    if request.method == "POST":
        logger.debug(f"[add_entry] POST data: {dict(request.POST)}")
        form = EntryForm(request.POST)
        if form.is_valid():
            logger.debug("[add_entry] Form is valid. Cleaned data: %s", form.cleaned_data)
            entry.comment = form.cleaned_data["comment"]
            entry.save()
            logger.debug(f"[add_entry] Saved entry.comment = '{entry.comment}'")

            for param in Parameter.objects.filter(active=True):
                val = form.cleaned_data.get(param.key)
                logger.debug(f"[add_entry] Parameter '{param.key}', form value = {val}")
                if val is not None:
                    ev_obj, ev_created = EntryValue.objects.update_or_create(
                        entry=entry,
                        parameter=param,
                        defaults={"value": val}
                    )
                    logger.debug(f"[add_entry] EntryValue for '{param.key}': value={ev_obj.value}, created={ev_created}")
            return redirect(f"/add/?date={entry_date}")
        else:
            logger.debug(f"[add_entry] Form errors: {form.errors}")
    else:
        form = EntryForm(initial=initial_data)
        logger.debug("[add_entry] Rendering form with initial data.")

    context = {
        "form": form,
        "range_6": range(6),
        "today_str": entry_date.strftime('%Y-%m-%d'),
        "parameter_keys": [p.key for p in Parameter.objects.filter(active=True)]
    }
    logger.debug(f"[add_entry] Context prepared: date={context['today_str']}")
    return render(request, "diary/add_entry.html", context)


def entry_success(request):
    return render(request, "diary/success.html")

@csrf_exempt
def predict_today(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        user_input = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError as e:
        logger.error("[predict_today] Invalid JSON: %s", e)
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        df = get_diary_dataframe()
    except Exception as e:
        logger.error("[predict_today] Data error: %s", e)
        return JsonResponse({"error": f"Data error: {str(e)}"}, status=500)

    # Формирование строки с текущими значениями
    today_row = {}
    for k, v in user_input.items():
        if v != '':
            try:
                today_row[k] = float(v)
            except ValueError:
                logger.warning("[predict_today] Non-numeric value for %s: %s", k, v)

    result = {}
    # Прогноз для каждого параметра (включая уже заданные пользователем)
    for target in df.columns:
        if target == 'date':
            continue
        try:
            model_info = train_model(df, target, exclude=[])
            model = model_info['model']
            if hasattr(model, 'feature_names_in_'):
                features = list(model.feature_names_in_)
            else:
                features = model_info['coefficients']['parameter']
            full_row = {}
            for feat in features:
                full_row[feat] = today_row.get(feat, df[feat].mean())
            X_today = pd.DataFrame([full_row], columns=features)
            pred = model.predict(X_today)[0]
            result[target] = round(float(pred), 2)
        except Exception as e:
            logger.error("[predict_today] Prediction error for %s: %s", target, e, exc_info=True)

    return JsonResponse(result)
