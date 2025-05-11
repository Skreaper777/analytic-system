# diary/views.py
"""Вьюхи дневника — контроллеры ввода, предсказания и визуализации."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import date, datetime
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import EntryForm
from .models import Entry, EntryValue, Parameter
from .ml_utils import base_model
from .ml_utils.utils import get_diary_dataframe

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
        Полные исторические данные дневника.
    today_values
        Значения показателей за рассматриваемый день.
    mode
        «live» — обучить модель «на лету» на полном датасете,
        «base» — использовать предобученную базовую модель.
    """
    predictions: Dict[str, float] = {}
    model_dir = os.path.join(settings.BASE_DIR, "diary", "trained_models", "base")

    for target in today_values.keys():
        try:
            # ------------------------------------------------------------------
            # 1. Модель
            # ------------------------------------------------------------------
            if mode == "live":
                model_info = base_model.train_model(df.copy(), target=target, exclude=[target])
                model = model_info["model"]
                features = model_info.get("features", getattr(model, "feature_names_in_", []))
            else:
                model_path = os.path.join(model_dir, f"{target}.pkl")
                if not os.path.exists(model_path):
                    logger.warning("Базовая модель %s.pkl не найдена", target)
                    continue
                model: Any = joblib.load(model_path)
                features = getattr(model, "feature_names_in_", [])

            # ------------------------------------------------------------------
            # 2. features → list
            # ------------------------------------------------------------------
            if isinstance(features, (pd.Index, np.ndarray)):
                features = features.tolist()
            if not features:
                features = [c for c in df.columns if c not in ("date", target)]

            # ------------------------------------------------------------------
            # 3. Строка для предсказания
            # ------------------------------------------------------------------
            safe_today = {f: float(today_values.get(f) or 0.0) for f in features}
            X_today = pd.DataFrame([safe_today])

            # ------------------------------------------------------------------
            # 4. Предсказание
            # ------------------------------------------------------------------
            pred_val = float(model.predict(X_today)[0])
            predictions[target] = round(pred_val, 2)

        except Exception:
            logger.exception("Prediction failed for %s (%s mode)", target, mode)

    return predictions


def _build_pred_dict(
    raw_preds: Dict[str, float],
    today_values: Dict[str, float],
) -> Dict[str, Dict[str, Any]]:
    """Готовит структуру для шаблона add_entry.html."""
    out: Dict[str, Dict[str, Any]] = {}
    for key, val in raw_preds.items():
        diff = val - today_values.get(key, 0.0)
        out[key] = {
            "value": round(val, 1),
            "delta": round(diff, 1),
            "color": _color_hint(diff),
        }
    return out


# ---------------------------------------------------------------------------
# Страницы
# ---------------------------------------------------------------------------


def add_entry(request: HttpRequest) -> HttpResponse:
    """Создаёт или редактирует запись за заданную дату."""
    date_str = request.GET.get("date")
    try:
        entry_date = datetime.fromisoformat(date_str).date() if date_str else date.today()
    except (TypeError, ValueError):
        entry_date = date.today()
        logger.debug("Invalid date '%s' — fallback to today", date_str)

    entry, created = Entry.objects.get_or_create(date=entry_date)
    logger.debug("📌 Объект Entry: %s для %s", "создан" if created else "найден", entry.date)

    form = EntryForm(request.POST or None, instance=entry)

    if request.method == "POST" and form.is_valid():
        for key, val in form.cleaned_data.items():
            if key in ("csrfmiddlewaretoken",):
                continue

            if key == "comment":
                entry.comment = val
                entry.save(update_fields=["comment"])
                logger.debug("💬 Updated comment: %s", val)
                continue

            parameter = Parameter.objects.filter(key=key).first()
            if parameter is None:
                logger.error("❌ Parameter with key '%s' not found", key)
                continue

            if val in (None, ""):
                EntryValue.objects.filter(entry=entry, parameter=parameter).delete()
                logger.debug("🗑️ Удалено значение для параметра %s", key)
            else:
                ev, created_ev = EntryValue.objects.update_or_create(
                    entry=entry,
                    parameter=parameter,
                    defaults={"value": val},
                )
                logger.debug(
                    "✅ EntryValue %s: %s",
                    "создан" if created_ev else "обновлён",
                    ev,
                )

        return HttpResponseRedirect(reverse("diary:add_entry") + f"?date={entry_date.isoformat()}")

    # -----------------------------------------------------------------------
    # Подготовка данных для прогнозов
    # -----------------------------------------------------------------------
    df = get_diary_dataframe().copy()
    values_qs = EntryValue.objects.filter(entry=entry).select_related("parameter")
    today_values = {ev.parameter.key: float(ev.value or 0) for ev in values_qs}

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


def entry_success(request: HttpRequest) -> HttpResponse:
    """Редирект после успешного сохранения записи."""
    return HttpResponseRedirect(reverse("diary:add_entry"))


# ---------------------------------------------------------------------------
# AJAX endpoints
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def update_value(request: HttpRequest) -> JsonResponse:
    """Сохраняет, обновляет или удаляет одно значение параметра."""
    logger.debug("📥 Поступил update_value: %s", request.body)

    try:
        data: Dict[str, Any] = json.loads(request.body or "{}")
        param_key = data["parameter"]
        value = data.get("value")
        raw_date = data["date"]
    except (KeyError, json.JSONDecodeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    # -----------------------------------------------------------------------
    # Приведение даты
    # -----------------------------------------------------------------------
    try:
        date_obj = datetime.fromisoformat(str(raw_date).split("T")[0]).date()
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    logger.debug("📆 Обрабатываем дату: %s → %s", raw_date, date_obj)

    # -----------------------------------------------------------------------
    # Работа с БД
    # -----------------------------------------------------------------------
    entry, _ = Entry.objects.get_or_create(date=date_obj)
    parameter = Parameter.objects.filter(key=param_key).first()
    if not parameter:
        return JsonResponse({"error": "Unknown parameter"}, status=400)

    if value in (None, ""):
        EntryValue.objects.filter(entry=entry, parameter=parameter).delete()
        logger.info("Deleted %s for %s", param_key, date_obj.isoformat())
    else:
        ev, _ = EntryValue.objects.get_or_create(entry=entry, parameter=parameter)
        ev.value = value
        ev.save(update_fields=["value"])
        logger.info("Saved %s=%s for %s", param_key, value, date_obj.isoformat())

    return JsonResponse({
        "status": "ok",
        "date": str(date_obj),
        "parameter": param_key,
        "value": value,
    })


@csrf_exempt
@require_POST
def predict_today(request: HttpRequest) -> JsonResponse:
    """Строит прогноз на основе переданных значений за сегодняшний день."""
    try:
        user_input: Dict[str, float] = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    df = get_diary_dataframe().copy()

    if df.empty:
        return JsonResponse({})

    today_values = {**{k: 0.0 for k in df.columns if k != "date"}, **user_input}
    live_raw = _predict_for_row(df, today_values, mode="live")
    return JsonResponse({k: {"value": v} for k, v in live_raw.items()})


# ---------------------------------------------------------------------------
# Запуск обучения моделей
# ---------------------------------------------------------------------------


def train_models_view(request: HttpRequest) -> HttpResponse:
    """Запускает manage.py train_models и возвращает пользователя обратно на add_entry."""
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
        logger.exception("train_models завершился с ошибкой")
        return JsonResponse({"error": exc.stderr or str(exc)}, status=500)
