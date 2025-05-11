from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import EntryForm
from .models import Entry, EntryValue, Parameter
from .ml_utils import base_model
from .ml_utils.utils import get_diary_dataframe

logger = logging.getLogger(__name__)

def _color_hint(diff: float) -> str:
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
    predictions: Dict[str, float] = {}
    model_dir = os.path.join(settings.BASE_DIR, "diary", "trained_models", "base")

    for target in today_values.keys():
        try:
            if mode == "live":
                model_info = base_model.train_model(df.copy(), target=target, exclude=[target])
                model = model_info.get("model")
                features = model_info.get("features", getattr(model, "feature_names_in_", []))
            else:
                model_path = os.path.join(model_dir, f"{target}.pkl")
                if not os.path.exists(model_path):
                    logger.warning("Базовая модель %s.pkl не найдена", target)
                    continue
                model = joblib.load(model_path)
                features = getattr(model, "feature_names_in_", [])

            if isinstance(features, (pd.Index, np.ndarray)):
                features = features.tolist()
            if not features:
                features = [c for c in df.columns if c not in ("date", target)]

            safe_today = {
                f: float(today_values.get(f)) if today_values.get(f) not in [None, "", "None"] else 0.0
                for f in features
            }
            X_today = pd.DataFrame([safe_today])
            pred_val = float(model.predict(X_today)[0])
            predictions[target] = round(pred_val, 2)
        except Exception:
            logger.exception("Prediction failed for %s (%s mode)", target, mode)
    return predictions

def _build_pred_dict(
    raw_preds: Dict[str, float],
    today_values: Dict[str, float],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for key, val in raw_preds.items():
        diff = val - today_values.get(key, 0.0)
        out[key] = {
            "value": round(val, 1),
            "delta": round(diff, 1) if val is not None else None,
            "color": _color_hint(diff),
        }
    return out

def add_entry(request):
    logger.debug("\U0001f680 Вызов функции add_entry - старт обработки запроса")
    date_str = request.GET.get("date")
    try:
        entry_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug("Invalid date '%s' - fallback to today", date_str)

    entry, _ = Entry.objects.get_or_create(date=entry_date)
    form = EntryForm(request.POST or None, instance=entry)

    if request.method == "POST" and form.is_valid():
        for key, val in form.cleaned_data.items():
            if key in ("csrfmiddlewaretoken", "comment"):
                if key == "comment":
                    entry.comment = val
                    entry.save()
                    logger.debug("💬 Updated comment: %s", val)
                continue
            try:
                param = Parameter.objects.get(key=key)
                if val in (None, ""):
                    EntryValue.objects.filter(entry=entry, parameter=param).delete()
                    logger.debug("🗑️ Удалено значение для параметра %s", param)
                else:
                    ev, created = EntryValue.objects.update_or_create(
                        entry=entry,
                        parameter=param,
                        defaults={"value": val},
                    )
                    logger.debug("✅ EntryValue %s: %s", "создан" if created else "обновлён", ev)
            except Parameter.DoesNotExist:
                logger.error("❌ Parameter with key '%s' not found", key)
        return HttpResponseRedirect(reverse("diary:add_entry"))

    df = get_diary_dataframe().copy()
    logger.debug("📅 Получен запрос на отображение страницы за дату: %s", entry_date)
    values_qs = EntryValue.objects.filter(entry=entry).select_related("parameter")
    logger.debug("📥 Загружаем значения EntryValue для этой даты...")
    logger.debug("📦 Найдено параметров: %d", len(values_qs))
    for ev in values_qs:
        logger.debug("🔢 Параметр %s = %s", ev.parameter.key, ev.value)
    today_values = {ev.parameter.key: ev.value or 0 for ev in values_qs}
    logger.debug("📤 Значения, переданные в шаблон: %s", today_values)

    live_raw = _predict_for_row(df, today_values, mode="live")
    base_raw = _predict_for_row(df, today_values, mode="base")

    context = {
        "form": form,
        "entry": entry,
        "entry_date": entry_date.isoformat(),
        "today_str": date.today().isoformat(),
        "parameter_keys": list(live_raw.keys()),
        "range_6": range(6),
        "live_predictions": _build_pred_dict(live_raw, today_values),
        "base_predictions": _build_pred_dict(base_raw, today_values),
    }
    return render(request, "diary/add_entry.html", context)

def entry_success(request):
    return HttpResponseRedirect(reverse("diary:add_entry"))

@csrf_exempt
@require_POST
def update_value(request):
    logger.debug("\U0001f680 Вызов функции update_value — старт обработки запроса")
    try:
        data = json.loads(request.body)
        if "date" in data:
            raw_date = data["date"]
            logger.debug(f"📅 Получена дата из POST-запроса: {raw_date}")
        else:
            raw_date = datetime.now().isoformat()
            logger.warning(f"⚠️ Дата не передана, используется текущая: {raw_date}")

        date_obj = datetime.fromisoformat(raw_date.split("T")[0]).date()
        param_key = data.get("key")
        value = data.get("value")

        entry, _ = Entry.objects.get_or_create(date=date_obj)
        parameter = Parameter.objects.get(key=param_key)

        if value is None:
            EntryValue.objects.filter(entry=entry, parameter=parameter).delete()
            logger.debug("🖑 Удалено значение параметра %s за %s", param_key, date_obj)
        else:
            ev, _ = EntryValue.objects.update_or_create(
                entry=entry,
                parameter=parameter,
                defaults={"value": value}
            )
            logger.info("Параметр сохраняется в БД. %s=%s for %s", param_key, value, date_obj)
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("❌ Ошибка в запросе update_value: %s", exc)
        return JsonResponse({"status": "error", "message": str(exc)}, status=400)

    return JsonResponse({'status': 'ok'})

@csrf_exempt
@require_POST
def predict_today(request):
    logger.debug("🚀 Вызов функции predict_today - старт обработки запроса")
    try:
        user_input = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        df = get_diary_dataframe().copy()
        if df.empty:
            return JsonResponse({})
        today_values = {**{k: 0.0 for k in df.columns if k != "date"}, **user_input}
        live_raw = _predict_for_row(df, today_values, mode="live")
        logger.debug(f"📤 Итоговые предсказания: {live_raw}")
        return JsonResponse({k: {"value": v} for k, v in live_raw.items()})
    except Exception as exc:
        logger.exception("predict_today failed")
        return JsonResponse({"error": str(exc)}, status=500)

import subprocess

def train_models_view(request):
    logger.info("🟡 train_models_view вызван")
    try:
        result = subprocess.run(
            ["python", "manage.py", "train_models"],
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("🟢 train_models выполнена успешно")
        logger.debug("STDOUT:\n%s", result.stdout)
        logger.debug("STDERR:\n%s", result.stderr)
        return HttpResponseRedirect(reverse("diary:add_entry"))
    except subprocess.CalledProcessError as exc:
        logger.exception("train_models_view failed")
        return JsonResponse({"error": exc.stderr or str(exc)}, status=500)
