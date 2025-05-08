# diary/views.py
import logging
import json
from datetime import date, datetime

import pandas as pd
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt

from .forms import EntryForm
from .models import Entry, EntryValue, Parameter
from .ml_utils.utils import get_diary_dataframe
from .ml_utils import base_model, flags_model, hybrid_model

logger = logging.getLogger('diary.views')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler('diary.log', encoding='utf-8')
formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(funcName)s] %(message)s', datefmt='%d/%b/%Y %H:%M:%S')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def add_entry(request):
    """Страница ввода/просмотра дневника за выбранную дату.

    * ВАЖНО*: не создавать *EntryValue* с нулевыми значениями автоматически.
    Значения параметров рождаются **только** когда пользователь явно кликает кнопку
    оценки *или* нажимает «Сохранить» после реального ввода.
    """
    date_str = request.GET.get('date')
    try:
        entry_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug(f"Invalid date format '{date_str}', falling back to today")

    logger.debug(f"Entry date: {entry_date}")
    # создаём/получаем саму запись без параметров
    entry, created = Entry.objects.get_or_create(date=entry_date)
    logger.debug(f"Entry fetched: id={entry.id}, created={created}, comment='{entry.comment}'")

    # --- Подготавливаем форму ---
    initial_data = {'comment': entry.comment}
    for ev in EntryValue.objects.filter(entry=entry):
        initial_data[ev.parameter.key] = ev.value
        logger.debug(f"Pre‑fill {ev.parameter.key} = {ev.value}")
    logger.debug(f"Complete initial_data: {initial_data}")

    if request.method == 'POST':
        logger.debug(f"POST data: {dict(request.POST)}")
        form = EntryForm(request.POST)
        if form.is_valid():
            entry.comment = form.cleaned_data['comment']
            entry.save()

            # 👇 сохраняем ТОЛЬКО реально введённые числовые значения
            active_params = Parameter.objects.filter(active=True)
            for param in active_params:
                val = form.cleaned_data.get(param.key)
                # игнорируем пустые поля – ничего не сохраняем и ничего не затираем нулями
                if val in (None, ''):
                    # если раньше значение было сохранено, удалить его
                    EntryValue.objects.filter(entry=entry, parameter=param).delete()
                    continue
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

    result = {}
    numeric_columns = [col for col in df.columns if col not in ('date',)]
    today_row = {}

    for col in numeric_columns:
        val = user_input.get(col)
        try:
            today_row[col] = float(val) if val != '' and val is not None else 0.0
        except (TypeError, ValueError):
            today_row[col] = 0.0

    logger.debug(f"Final today_row with zero fill: {today_row}")

    model_map = {
        "base_model": base_model.train_model,
        "flags_model": flags_model.train_model,
        "hybrid_model": hybrid_model.train_model
    }

    all_results = {}

    for model_name, model_func in model_map.items():
        predictions = {}
        for target in numeric_columns:
            try:
                exclude = [col for col in df.columns if col not in today_row or col == 'date' or col == target]
                model_info = model_func(df, target, exclude=exclude)
                model = model_info['model']
                feature_names = list(model.feature_names_in_)

                # Добавляем флаги *_есть в today_row для нужных моделей
                row_copy = today_row.copy()
                if model_name in ('flags_model', 'hybrid_model'):
                    for key in numeric_columns:
                        flag_name = f"{key}_есть"
                        if flag_name in feature_names:
                            row_copy[flag_name] = 1 if row_copy.get(key, 0) > 0 else 0
                X_today = pd.DataFrame([{k: row_copy.get(k, 0) for k in feature_names}])
                logger.debug(f"[{model_name}] X_today for target={target}: {X_today.to_dict(orient='records')}")
                pred = model.predict(X_today)[0]
                predictions[target] = round(float(pred), 2)
                logger.debug(f"[{model_name}] Predicted {target} = {predictions[target]}")
            except Exception as e:
                logger.debug(f"Prediction error for {target} in {model_name}: {e}")
        all_results[model_name] = predictions

    return JsonResponse(all_results)


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