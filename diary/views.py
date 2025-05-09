# diary/views.py
"""Вьюхи дневника – актуальная версия с рабочими прогнозами и логами."""
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

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler("diary.log", encoding="utf-8")
file_handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", "%d/%b/%Y %H:%M:%S")
)
logger.addHandler(file_handler)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        return float(value) if value not in ("", None) else 0.0
    except (TypeError, ValueError):
        return 0.0

# ---------------------------------------------------------------------------
# Main page
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

    parameter_keys = list(Parameter.objects.filter(active=True).values_list("key", flat=True))

    context = {
        "form": form,
        "entry": entry,
        "entry_date": entry_date.isoformat(),
        "today_str": date.today().isoformat(),
        "parameter_keys": parameter_keys,
        "range_6": range(6),
    }
    return render(request, "diary/add_entry.html", context)

# ---------------------------------------------------------------------------
# Redirect after save
# ---------------------------------------------------------------------------

def entry_success(request):
    return HttpResponseRedirect(reverse("diary:add_entry"))

# ---------------------------------------------------------------------------
# AJAX: update single value
# ---------------------------------------------------------------------------

def update_value(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))
        param_key = data["parameter"]
        value = _safe_float(data["value"])
        day = datetime.strptime(data["date"], "%Y-%m-%d").date()
    except (KeyError, ValueError, json.JSONDecodeError) as exc:
        logger.exception("update_value bad payload")
        return JsonResponse({"error": str(exc)}, status=400)

    entry, _ = Entry.objects.get_or_create(date=day)
    parameter = Parameter.objects.get(key=param_key)
    EntryValue.objects.update_or_create(entry=entry, parameter=parameter, defaults={"value": value})
    logger.debug("update_value: %s=%s on %s", param_key, value, day)
    return JsonResponse({"status": "ok"})

# ---------------------------------------------------------------------------
# AJAX: predictions
# ---------------------------------------------------------------------------

@csrf_exempt
def predict_today(request):
    """POST‑JSON → прогнозы {param_key: value}."""
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

        today_row = {
            col: _safe_float(user_input.get(name_to_key.get(col, col), 0.0))
            for col in numeric_columns
        }

        predictions: dict[str, float] = {}
        for target in numeric_columns:
            exclude = [c for c in numeric_columns if c != target]
            model_info = base_model.train_model(df, target, exclude=exclude)
            model = model_info["model"]
            features = model_info.get("features", getattr(model, "feature_names_in_", []))
            X_today = pd.DataFrame([{f: today_row.get(f, 0.0) for f in features}])
            predictions[name_to_key.get(target, target)] = round(float(model.predict(X_today)[0]), 2)

        logger.debug("predict_today → %s", predictions)
        return JsonResponse(predictions)

    except Exception as exc:
        logger.exception("predict_today failed")
        return JsonResponse({"error": str(exc)}, status=500)
