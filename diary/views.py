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

# Настройка логирования в файл с читаемым форматом времени
logger = logging.getLogger('diary.views')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('diary.log', encoding='utf-8')
formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(funcName)s] %(message)s', datefmt='%d/%b/%Y %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def add_entry(request):
    date_str = request.GET.get('date')
    try:
        entry_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug(f"Invalid date format '{date_str}', falling back to today")

    logger.debug(f"Entry date: {entry_date}")
    entry, created = Entry.objects.get_or_create(date=entry_date)
    logger.debug(f"Entry fetched: id={entry.id}, created={created}, comment='{entry.comment}'")

    initial_data = {'comment': entry.comment}
    for ev in EntryValue.objects.filter(entry=entry):
        initial_data[ev.parameter.key] = ev.value
        logger.debug(f"Pre-fill {ev.parameter.key} = {ev.value}")

    logger.debug(f"Complete initial_data: {initial_data}")

    if request.method == 'POST':
        logger.debug(f"POST data: {dict(request.POST)}")
        form = EntryForm(request.POST)
        if form.is_valid():
            entry.comment = form.cleaned_data['comment']
            entry.save()
            for param in Parameter.objects.filter(active=True):
                val = form.cleaned_data.get(param.key)
                if val is not None:
                    EntryValue.objects.update_or_create(
                        entry=entry,
                        parameter=param,
                        defaults={'value': val}
                    )
            return redirect(f"/add/?date={entry_date}")
        else:
            logger.debug(f"Form errors: {form.errors}")
    else:
        form = EntryForm(initial=initial_data)
        logger.debug("Rendering form with initial data.")

    context = {
        'form': form,
        'range_6': range(6),
        'today_str': entry_date.strftime('%Y-%m-%d'),
        'parameter_keys': [p.key for p in Parameter.objects.filter(active=True)]
    }
    logger.debug(f"Context prepared: date={context['today_str']}")
    return render(request, 'diary/add_entry.html', context)


@csrf_exempt
def predict_today(request):
    logger.debug('predict_today called')
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)

    try:
        body = request.body.decode('utf-8')
        user_input = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    logger.debug(f"Today input for prediction: {user_input}")
    try:
        df = get_diary_dataframe()
    except Exception as e:
        return JsonResponse({'error': f'Data error: {str(e)}'}, status=500)

    # Собираем только числовые параметры
    today_row = {}
    for k, v in user_input.items():
        if v != '':
            try:
                today_row[k] = float(v)
            except (TypeError, ValueError):
                logger.debug(f"Non-numeric value for {k}: {v}")

    logger.debug(f"Clean today_row: {today_row}")
    result = {}

    for target in df.columns:
        # всегда считаем прогноз, кроме колонки даты
        if target == 'date':
            continue
        try:
            model_info = train_model(df, target, exclude=list(today_row.keys()))
            model = model_info['model']
            feature_names = list(model.feature_names_in_)
            X_today = pd.DataFrame([today_row], columns=feature_names).fillna(0)
            pred = model.predict(X_today)[0]
            result[target] = round(float(pred), 2)
            logger.debug(f"Predicted {target} = {result[target]}")
        except Exception as e:
            logger.debug(f"Prediction error for {target}: {e}")
    return JsonResponse(result)


@csrf_exempt
def update_value(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    logger.debug('update_value called with method POST')
    try:
        data = json.loads(request.body.decode('utf-8'))
        key = data.get('key')
        value = data.get('value')
        logger.debug(f"update_value payload: key={key}, value={value}")
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    date_str = request.GET.get('date')
    try:
        entry_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()

    entry, _ = Entry.objects.get_or_create(date=entry_date)
    try:
        param = Parameter.objects.get(key=key)
    except Parameter.DoesNotExist:
        return JsonResponse({'error': 'Unknown parameter'}, status=400)

    if value is None:
        EntryValue.objects.filter(entry=entry, parameter=param).delete()
        logger.debug(f"Deleted value for {key}")
        return JsonResponse({'status': 'deleted'})
    else:
        ev, created = EntryValue.objects.update_or_create(
            entry=entry,
            parameter=param,
            defaults={'value': value}
        )
        logger.debug(f"Saved value for {key}: {value}")
        return JsonResponse({'status': 'saved', 'value': ev.value})


def entry_success(request):
    return render(request, 'diary/success.html')
