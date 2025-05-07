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

# Настройка логгера для отладки
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

def add_entry(request):
    # Определяем дату: из GET-параметра или текущая
    date_str = request.GET.get('date')
    try:
        entry_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug(f"[add_entry] Invalid date format '{date_str}', fallback to today")

    logger.debug(f"[add_entry] Entry date: {entry_date}")
    entry, created = Entry.objects.get_or_create(date=entry_date)
    logger.debug(f"[add_entry] Entry fetched: id={entry.id}, created={created}, comment='{entry.comment}'")

    # Предзаполнение
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
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        df = get_diary_dataframe()
    except Exception as e:
        return JsonResponse({"error": f"Data error: {str(e)}"}, status=500)

    today_row = {k: float(v) for k, v in user_input.items() if v != ''}
    result = {}

    for target in df.columns:
        if target in ['date'] or target in today_row:
            continue
        try:
            model_info = train_model(df, target, exclude=list(today_row.keys()))
            model = model_info['model']
            X_today = pd.DataFrame([today_row], columns=model_info['coefficients']['parameter'])
            pred = model.predict(X_today)[0]
            result[target] = round(pred, 2)
        except Exception:
            continue

    return JsonResponse(result)
