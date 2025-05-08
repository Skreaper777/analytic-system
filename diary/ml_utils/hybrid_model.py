# diary/ml_utils/hybrid_model.py
import logging
from sklearn.linear_model import LinearRegression

def train_model(df, target, exclude=None):
    """
    Гибридная модель: использует как значения параметров, так и бинарные признаки *_есть.
    Учитывает и наличие симптома, и его выраженность.
    """
    if exclude is None:
        exclude = []

    df = df.copy()

    # Определяем признаки, которые можно использовать
    features = [col for col in df.columns if col not in ('date', target) and col not in exclude]

    # Добавляем *_есть признаки
    for col in features:
        df[f"{col}_есть"] = (df[col] > 0).astype(int)

    # Полный список фичей = значения + флаги
    used_columns = features + [f"{col}_есть" for col in features]
    X = df[used_columns]
    y = df[target]

    model = LinearRegression()
    logger = logging.getLogger('diary.ml_utils.hybrid_model')
    logger.debug(f"Training hybrid_model with features: {list(X.columns)}")
    model.fit(X, y)
    coef_info = list(zip(X.columns, model.coef_))
    coef_info.sort(key=lambda x: abs(x[1]), reverse=True)
    for name, coef in coef_info:
        logger.debug(f"Feature: {name} — Weight: {coef:.4f}")

    return {"model": model}
