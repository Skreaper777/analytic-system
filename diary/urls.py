# diary/urls.py
"""URL-маршруты дневника.

• `/` и `/add/` ведут на одну и ту же страницу ввода.
• Остальные — AJAX/REST-эндпоинты.
"""
from django.urls import path

from . import views

app_name = "diary"

urlpatterns = [
    # Основная страница дневника (корень) + alias /add/
    path("", views.add_entry, name="add_entry"),
    path("add/", views.add_entry, name="add_entry_alias"),

    # API-эндпоинты
    path("update-value/", views.update_value, name="update_value"),
    path("predict/", views.predict, name="predict"),

    # Редирект после успешного сохранения
    path("success/", views.entry_success, name="entry_success"),

    # Обучение моделей
    path("train-models/", views.train_models_view, name="train_models"),
]
