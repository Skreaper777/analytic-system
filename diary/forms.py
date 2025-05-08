# diary/forms.py
"""Динамическая форма дневника.

• Поле ``comment`` – многострочный текст.
• Все остальные числовые поля добавляются на лету из модели ``Parameter``.
• Аргумент ``instance`` тихо сохраняется в ``self.instance``.
"""
from __future__ import annotations

from typing import Any

from django import forms

from .models import Parameter


class EntryForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args: Any, **kwargs: Any):
        # Сохраняем ссылку на Entry, если передали
        self.instance = kwargs.pop("instance", None)
        super().__init__(*args, **kwargs)

        # Динамически создаём числовые поля по активным параметрам
        for param in Parameter.objects.filter(active=True):
            self.fields[param.key] = forms.IntegerField(
                label=param.name_ru,
                required=False,
                min_value=0,
                max_value=5,
            )

    def save(self):
        """Заглушка: логика сохранения реализуется в другом месте."""
        return self.cleaned_data
