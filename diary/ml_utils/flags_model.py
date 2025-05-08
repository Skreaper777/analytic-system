# ml_utils/base_model.py
from sklearn.linear_model import LinearRegression

def train_model(df, target, exclude=None):
    if exclude is None:
        exclude = []

    X = df.drop(columns=exclude + [target])
    y = df[target]

    model = LinearRegression()
    model.fit(X, y)

    return {"model": model}


# ml_utils/flags_model.py
from sklearn.linear_model import LinearRegression

def train_model(df, target, exclude=None):
    """
    Модель с бинарными флагами *_есть. Подходит для симптомов, где важно не только значение, но и сам факт наличия.
    """
    if exclude is None:
        exclude = []

    df = df.copy()

    # Выбираем признаки, для которых создадим бинарный флаг
    columns_to_flag = [col for col in df.columns if col not in ('date', target) and col not in exclude]

    # Добавляем бинарные признаки *_есть = 1 если значение > 0
    for col in columns_to_flag:
        df[f"{col}_есть"] = (df[col] > 0).astype(int)

    # Исключаем оригинальные признаки и таргет из X
    X = df.drop(columns=exclude + [target])
    y = df[target]

    model = LinearRegression()
    model.fit(X, y)

    return {"model": model}
