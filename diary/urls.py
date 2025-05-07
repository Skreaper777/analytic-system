from django.urls import path
from . import views

urlpatterns = [
    path("add/", views.add_entry, name="add_entry"),
    path("success/", views.entry_success, name="entry_success"),
]
