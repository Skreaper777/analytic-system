from django.core.management.base import BaseCommand
import logging
from diary.ml_utils.utils import get_diary_dataframe
from diary.ml_utils.base_model import train_model
import os
import joblib
from datetime import date

logger = logging.getLogger("train_models")

class Command(BaseCommand):
    help = "Обучает все модели и сохраняет .pkl"

    def handle(self, *args, **kwargs):
        MODEL_DIR = os.path.join("diary", "trained_models", "base")
        os.makedirs(MODEL_DIR, exist_ok=True)

        df = get_diary_dataframe()
        today = date.today()
        df = df[df["date"] < today]

        logger.info("🟡 Старт обучения моделей...")
        logger.info("📄 Доступные столбцы: %s", ", ".join(df.columns))
        logger.info("📆 Даты в обучении: от %s до %s", df["date"].min(), df["date"].max())

        # Удаление старых моделей
        for file in os.listdir(MODEL_DIR):
            if file.endswith(".pkl"):
                os.remove(os.path.join(MODEL_DIR, file))
        logger.info("🧹 Удалены старые модели перед обучением.")

        for target in df.columns:
            if target in ("date", "Дата"):
                continue
            result = train_model(df.copy(), target=target, exclude=[])
            model = result.get("model")
            if model:
                file_path = os.path.join(MODEL_DIR, f"{target}.pkl")
                joblib.dump(model, file_path)
                logger.info("✅ Обучено: %s → %s", target, file_path)
            else:
                logger.warning("⛔ Пропущено: %s — модель не обучена", target)
