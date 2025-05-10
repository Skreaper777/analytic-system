# diary/views.py
"""Вьюхи дневника – исправлена логика exclude, чтобы /predict/ не падал."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

import pandas as pd
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .forms import EntryForm
from .models import Entry, EntryValue, Parameter
from .ml_utils.utils import get_diary_dataframe
from .ml_utils import base_model

logger = logging.getLogger("predict")
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        return float(value) if value not in ("", None) else 0.0
    except (TypeError, ValueError):
        return 0.0

# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def add_entry(request):
    """Главная форма дневника на дату.
    Возвращает также selected_values: {param_key: value} для предварительной отрисовки.
    """
    date_str = request.GET.get("date")
    try:
        entry_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug("Invalid date '%s' — fallback to today", date_str)

    entry, _ = Entry.objects.get_or_create(date=entry_date)
    form = EntryForm(instance=entry)

    parameter_keys = list(Parameter.objects.filter(active=True).values_list("key", flat=True))

    # Собираем уже сохранённые значения
    selected_values = {
        ev.parameter.key: ev.value
        for ev in EntryValue.objects.filter(entry=entry, parameter__active=True)
    }

    context = {
        "form": form,
        "entry": entry,
        "entry_date": entry_date.isoformat(),
        "today_str": date.today().isoformat(),
        "parameter_keys": parameter_keys,
        "selected_values": selected_values,
        "range_6": range(6),
    }
    return render(request, "diary/add_entry.html", context)
def entry_success(request):
    return HttpResponseRedirect(reverse("diary:add_entry"))

# ---------------------------------------------------------------------------
# AJAX endpoints
# ---------------------------------------------------------------------------


def update_value(request):
    """AJAX‑эндпоинт.
    Получает JSON {"parameter": <key>, "value": <int|None>, "date": "YYYY-MM-DD"}
    Сохраняет/удаляет значение EntryValue **без** перезагрузки страницы.
    """
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        param_key = data["parameter"]
        raw_value = data["value"]
        # если пользователь кликает повторно по выбранной оценке – считаем, что хочет удалить
        value = _safe_float(raw_value) if raw_value not in ("", None, "None") else 0.0
        entry_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.exception("Bad payload for update_value")
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        entry, _ = Entry.objects.get_or_create(date=entry_date)
        parameter = Parameter.objects.get(key=param_key, active=True)
    except Parameter.DoesNotExist:
        return JsonResponse({"error": "Unknown parameter"}, status=400)

    # Значение 0 интерпретируем как удаление
    if value == 0.0:
        deleted_cnt, _ = EntryValue.objects.filter(entry=entry, parameter=parameter).delete()
        logger.info("Deleted %s for %s (%s rows)", param_key, entry_date, deleted_cnt)
    else:
        ev, _ = EntryValue.objects.get_or_create(entry=entry, parameter=parameter)
        ev.value = value
        ev.save()
        logger.info("Saved %s = %s for %s", param_key, value, entry_date)

    return JsonResponse({"success": True})
@csrf_exempt
def predict_today(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        user_input = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        df = get_diary_dataframe().copy()
        numeric_columns = [c for c in df.columns if c not in ("date",)]

        name_to_key = {p.name_ru: p.key for p in Parameter.objects.filter(active=True)}
        key_to_rus = {v: k for k, v in name_to_key.items()}

        today_row: dict[str, float] = {}
        for rus in numeric_columns:
            key = name_to_key.get(rus, rus)
            val = _safe_float(user_input.get(key)) if key in user_input else 0.0
            today_row[rus] = val

        predictions: dict[str, float] = {}
        for target in numeric_columns:
            exclude = [target]  # ❗️Возвращено поведение старой версии
            try:
                model_info = base_model.train_model(df, target, exclude=exclude)
                model = model_info["model"]
                features = model_info.get("features", getattr(model, "feature_names_in_", []))
                if not features:
                    logger.warning("Skipped prediction for %s — no features left after exclude", target)
                    for h in logger.handlers:
                        try:
                            h.flush()
                        except Exception:
                            pass
                    continue
                X_today = pd.DataFrame([{f: today_row.get(f, 0.0) for f in features}])
                pred_val = round(float(model.predict(X_today)[0]), 2)
                predictions[name_to_key.get(target, target)] = pred_val
            except Exception as e:
                logger.exception("Model training failed for %s", target)
                for h in logger.handlers:
                    try:
                        h.flush()
                    except Exception:
                        pass
                continue

        logger.debug("predict_today → %s", predictions)
        for h in logger.handlers:
            try:
                h.flush()
            except Exception:
                pass
        return JsonResponse(predictions)

    except Exception as exc:
        logger.exception("predict_today failed")
        return JsonResponse({"error": str(exc)}, status=500)

import subprocess
import logging
from django.http import HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger(__name__)

def train_models_view(request):
    logger.info("🟡 train_models_view вызван")
    try:
        result = subprocess.run(["python", "manage.py", "train_models"], check=True, capture_output=True, text=True)
        logger.info("🟢 train_models выполнена успешно")
        logger.info("STDOUT:\n%s", result.stdout)
        logger.info("STDERR:\n%s", result.stderr)
    except subprocess.CalledProcessError as e:
        logger.error("🔴 Ошибка при запуске train_models: %s", str(e))
        logger.error("STDOUT:\n%s", e.stdout)
        logger.error("STDERR:\n%s", e.stderr)

    return HttpResponseRedirect(reverse("diary:add_entry") + "?trained=1")