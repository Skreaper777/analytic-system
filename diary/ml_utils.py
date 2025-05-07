import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from diary.models import Entry, EntryValue, Parameter

def get_diary_dataframe():
    """
    Возвращает DataFrame с данными дневника:
    | date       | toshnota | golovokruzhenie | ... |
    |------------|----------|------------------|-----|
    | 2025-05-01 |   3      |        1         | ... |
    """
    param_qs = Parameter.objects.filter(active=True)
    param_map = {p.id: p.key for p in param_qs}

    values_qs = EntryValue.objects.select_related("entry", "parameter")
    data = {}
    for ev in values_qs:
        date = ev.entry.date
        param_key = param_map.get(ev.parameter.id)
        if not param_key:
            continue
        if date not in data:
            data[date] = {}
        data[date][param_key] = ev.value

    rows = []
    for date, vals in data.items():
        row = {"date": date}
        row.update(vals)
        rows.append(row)

    df = pd.DataFrame(rows)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def train_model(df: pd.DataFrame, target: str, exclude: list = []):
    """
    Обучает линейную регрессию для предсказания параметра `target`
    exclude — список параметров, которые не нужно использовать как фичи
    """
    if target not in df.columns:
        raise ValueError(f"Целевой параметр '{target}' не найден в данных")

    features = [col for col in df.columns if col not in ['date', target] + exclude]
    df_model = df.dropna(subset=[target] + features)

    if df_model.empty:
        raise ValueError("Недостаточно данных для обучения модели")

    X = df_model[features]
    y = df_model[target]

    model = LinearRegression()
    model.fit(X, y)
    y_pred = model.predict(X)

    mae = np.mean(np.abs(y - y_pred))
    rmse = np.sqrt(np.mean((y - y_pred) ** 2))

    coef_table = pd.DataFrame({
        'parameter': features,
        'coefficient': model.coef_
    }).sort_values(by='coefficient', key=np.abs, ascending=False)

    return {
        'mae': mae,
        'rmse': rmse,
        'coefficients': coef_table,
        'model': model
    }
