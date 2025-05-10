
import os
import joblib
import logging
from datetime import date

from diary.ml_utils.utils import get_diary_dataframe
from diary.ml_utils.base_model import train_model

logger = logging.getLogger("train_all")
logging.basicConfig(level=logging.INFO)

MODEL_DIR = os.path.join("diary", "trained_models", "base")
os.makedirs(MODEL_DIR, exist_ok=True)

# Удаление старых моделей
for file in os.listdir(MODEL_DIR):
    if file.endswith(".pkl"):
        os.remove(os.path.join(MODEL_DIR, file))
logger.info("Удалены старые модели перед обучением.")


def main():
    df = get_diary_dataframe()

    today = date.today()
    df = df[df["date"] < today]

    logger.info("Начинаем обучение по %d дням...", len(df))

    for target in df.columns:
        if target in ("date", "Дата"):
            continue
        result = train_model(df.copy(), target=target, exclude=[])
        model = result.get("model")
        if model:
            file_path = os.path.join(MODEL_DIR, f"{target}.pkl")
            joblib.dump(model, file_path)
            logger.info("Обучено: %s → %s", target, file_path)
        else:
            logger.warning("Пропущено: %s — модель не обучена (признаков нет)", target)

if __name__ == "__main__":
    main()
