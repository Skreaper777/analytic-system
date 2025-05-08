# diary/forms.py
"""Динамическая форма дневника.

• Добавляет числовые поля 0‑5 для всех `Parameter` с `active=True`.
• При переданном `instance` (Entry) подтягивает существующие значения
  из `EntryValue` и проставляет их как initial, чтобы выбранные кнопки
  были подсвечены при открытии страницы.
• Аргумент `instance` сохраняется в `self.instance`.
"""
from __future__ import annotations

from typing import Any

from django import forms

from .models import Parameter, EntryValue


class EntryForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args: Any, **kwargs: Any):
        # Забираем Entry, если передан
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        # ------------------------------------------------------------------
        # Динамически создаём числовые поля 0‑5 по активным параметрам
        # ------------------------------------------------------------------
        for param in Parameter.objects.filter(active=True):
            self.fields[param.key] = forms.IntegerField(
                label=param.name_ru,
                required=False,
                min_value=0,
                max_value=5,
            )

        # ------------------------------------------------------------------
        # Проставляем initial из EntryValue, чтобы кнопки подсветились
        # ------------------------------------------------------------------
        if self.instance and self.instance.pk:
            values_qs = EntryValue.objects.filter(entry=self.instance).select_related("parameter")
            for ev in values_qs:
                key = ev.parameter.key
                if key in self.fields:
                    self.initial[key] = ev.value

    # Пока сохранение логики нет — заглушка
    def save(self):
        return self.cleaned_data
