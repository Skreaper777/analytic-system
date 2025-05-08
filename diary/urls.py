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
    path("predict/", views.predict_today, name="predict_today"),
    path("update-value/", views.update_value, name="update_value"),

    # Редирект после успешного сохранения
    path("success/", views.entry_success, name="entry_success"),
]