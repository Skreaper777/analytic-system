from django.urls import path
from .views import add_entry, entry_success, predict_today, update_value

urlpatterns = [
    path('add/', add_entry, name='add_entry'),
    path('add/success/', entry_success, name='entry_success'),
    path('predict/', predict_today, name='predict_today'),
    path('update-value/', update_value, name='update_value'),
]