
# diary/views.py
"""Вьюхи дневника – добавлена поддержка двух типов прогнозов:
• «На лету» — обучение моделей каждый раз без использования .pkl‑файлов;
• «База»   — использование предварительно обученных моделей из diary/trained_models/base/*.pkl.

Шаблон add_entry.html теперь получает словари `live_predictions` и `base_predictions`,
а endpoint /predict/ возвращает объект вида `{parameter_key: {"value": 1.2}}`
для корректной работы JS‑логики.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict

import joblib
import pandas as pd
import numpy as np
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .forms import EntryForm
from .models import Entry, EntryValue, Parameter
from .ml_utils.utils import get_diary_dataframe
from .ml_utils import base_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _color_hint(diff: float) -> str:
    """Определяет цвет подсказки по модулю дельты."""
    diff_abs = abs(diff)
    if diff_abs < 1:
        return "green"
    if diff_abs <= 2:
        return "yellow"
    return "red"

def _predict_for_row(
    df: pd.DataFrame,
    today_values: Dict[str, float],
    mode: str = "live",
) -> Dict[str, float]:
    """Возвращает прогнозы для строки ``today_values`` в двух режимах.

    Parameters
    ----------
    df
        Полный датафрейм с историческими данными (ключи = Parameter.key).
    today_values
        Словарь {parameter_key: value} для текущего дня.
    mode
        "live" — переобучать модель на лету;
        "base" — загружать готовые .pkl‑файлы.

    Returns
    -------
    Dict[str, float]
        {parameter_key: predicted_value}
    """
    predictions: Dict[str, float] = {}
    model_dir = os.path.join(settings.BASE_DIR, "diary", "trained_models", "base")

    for target in today_values.keys():
        try:
            # --- 1. Получаем модель и список фичей
            if mode == "live":
                model_info = base_model.train_model(df.copy(), target=target, exclude=[target])
                model = model_info.get("model")
                features = model_info.get("features", getattr(model, "feature_names_in_", []))
            else:  # base
                model_path = os.path.join(model_dir, f"{target}.pkl")
                if not os.path.exists(model_path):
                    logger.warning("Базовая модель %s.pkl не найдена", target)
                    continue
                model = joblib.load(model_path)
                features = getattr(model, "feature_names_in_", [])

            # --- 2. Приводим features к списку
            if isinstance(features, (pd.Index, np.ndarray)):
                features = features.tolist()
            if not features:
                # fallback – все колонки без date/target
                features = [c for c in df.columns if c not in ("date", target)]

            # --- 3. Формируем строку для предсказания
            safe_today = {
        f: float(today_values.get(f)) if today_values.get(f) not in [None, '', 'None'] else 0.0
        for f in features
    }
            X_today = pd.DataFrame([safe_today])

            # --- 4. Предсказываем
            pred_val = float(model.predict(X_today)[0])
            predictions[target] = round(pred_val, 2)
        except Exception:
            logger.exception("Prediction failed for %s (%s mode)", target, mode)
            continue

    return predictions
def _build_pred_dict(
    raw_preds: Dict[str, float],
    today_values: Dict[str, float],
) -> Dict[str, Dict[str, Any]]:
    """Формирует структуру для шаблона add_entry.html."""
    out: Dict[str, Dict[str, Any]] = {}
    for key, val in raw_preds.items():
        diff = val - today_values.get(key, 0.0)
        out[key] = {
            "value": round(val, 1),
            "delta": round(val - today_values.get(key, 0.0), 1) if val is not None and today_values.get(key) is not None else None,
            "color": _color_hint(diff),
        }
    return out

# ---------------------------------------------------------------------------
# Страницы
# ---------------------------------------------------------------------------

def add_entry(request):
    date_str = request.GET.get("date")
    try:
        entry_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug("Invalid date '%s' — fallback to today", date_str)

    entry, _ = Entry.objects.get_or_create(date=entry_date)
    form = EntryForm(instance=entry)

    # ---- Текущие значения поля -> словарь {key: value}
    parameter_qs = Parameter.objects.filter(active=True)
    parameter_keys = list(parameter_qs.values_list("key", flat=True))
    today_values = {ev.parameter.key: ev.value for ev in EntryValue.objects.filter(entry=entry)}
    for k in parameter_keys:
        today_values.setdefault(k, 0.0)

    # ---- Прогнозы
    df = get_diary_dataframe().copy()

    live_raw  = _predict_for_row(df, today_values, mode="live")
    base_raw  = _predict_for_row(df, today_values, mode="base")

    live_predictions = _build_pred_dict(live_raw, today_values)
    base_predictions = _build_pred_dict(base_raw, today_values)

    context = {
        "form": form,
        "entry": entry,
        "entry_date": entry_date.isoformat(),
        "today_str": date.today().isoformat(),
        "parameter_keys": parameter_keys,
        "range_6": range(6),
        "live_predictions": live_predictions,
        "base_predictions": base_predictions,
    }
    return render(request, "diary/add_entry.html", context)

def entry_success(request):
    return HttpResponseRedirect(reverse("diary:add_entry"))

# ---------------------------------------------------------------------------
# AJAX endpoints
# ---------------------------------------------------------------------------

@csrf_exempt
def update_value(request):
    """Сохраняет значение одного параметра."""
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        param_key: str = data["parameter"]
        value: float | None = data["value"]
        day = datetime.strptime(data["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.exception("update_value bad payload")
        return JsonResponse({"error": str(exc)}, status=400)

    entry, _ = Entry.objects.get_or_create(date=day)
    parameter = Parameter.objects.filter(key=param_key).first()
    if not parameter:
        return JsonResponse({"error": "Unknown parameter"}, status=400)

    entry_value, _ = EntryValue.objects.get_or_create(entry=entry, parameter=parameter)
    entry_value.value = value
    entry_value.save()

    logger.info("Saved %s = %s for %s", param_key, value, day.isoformat())
    return JsonResponse({"ok": True})

# ---------------------------------------------------------------------------
# prediction endpoint для JS
# ---------------------------------------------------------------------------

@csrf_exempt
def predict_today(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        user_input = json.loads(request.body.decode("utf-8"))  # {key: value}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        # ---- Загружаем данные
        df = get_diary_dataframe().copy()
        if df.empty:
            return JsonResponse({})
        today_values = {**{k: 0.0 for k in df.columns if k not in ("date",)}, **user_input}

        # Используем «на лету» модели
        live_raw = _predict_for_row(df, today_values, mode="live")
        response_payload = {k: {"value": v} for k, v in live_raw.items()}

        logger.debug("predict_today → %s", response_payload)
        return JsonResponse(response_payload)

    except Exception as exc:
        logger.exception("predict_today failed")
        return JsonResponse({"error": str(exc)}, status=500)

# ---------------------------------------------------------------------------
# Доп. вью для запуска обучения (без изменений)
# ---------------------------------------------------------------------------

import subprocess

def train_models_view(request):
    logger.info("🟡 train_models_view вызван")
    try:
        result = subprocess.run(["python", "manage.py", "train_models"], check=True, capture_output=True, text=True)
        logger.info("🟢 train_models выполнена успешно")
        logger.info("STDOUT:\n%s", result.stdout)
        logger.info("STDERR:\n%s", result.stderr)
        return HttpResponseRedirect(reverse("diary:add_entry"))
    except subprocess.CalledProcessError as exc:
        logger.exception("train_models_view failed")
        return JsonResponse({"error": exc.stderr}, status=500)