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
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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

@csrf_exempt
@require_POST
def predict(request):
    logger.debug("🚀 Вызов функции predict - старт обработки запроса")
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
        base_raw = _predict_for_row(df, today_values, mode="base")

        response = {
            "live": {k: {"value": v} for k, v in live_raw.items()},
            "base": {k: {"value": v} for k, v in base_raw.items()},
        }
        logger.debug("📤 Прогнозы отправлены: %s", response)
        return JsonResponse(response)
    except Exception as exc:
        logger.exception("predict failed")
        return JsonResponse({"error": str(exc)}, status=500)
