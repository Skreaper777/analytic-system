from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path
from django.contrib import messages
from .models import Parameter, Entry, EntryValue
from diary.scripts.import_excel_to_db import run_excel_import

import re

RU_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "shch", "ы": "y", "э": "e", "ю": "yu", "я": "ya",
    "ь": "", "ъ": ""
}

def translit(text):
    text = text.lower()
    result = "".join(RU_TO_LATIN.get(char, char) for char in text)
    result = re.sub(r"[^a-z0-9_]+", "_", result)
    return result.strip("_")

class ParameterAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "key", "active")
    change_list_template = "admin/import_with_button.html"
    prepopulated_fields = {"key": ("name_ru",)}
    change_list_template = "admin/import_with_button.html"

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.key = translit(obj.name_ru)
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import_excel/', self.admin_site.admin_view(self.import_excel), name="import_excel"),
        ]
        return custom_urls + urls

    def import_excel(self, request):
        created, updated = run_excel_import()
        self.message_user(request, f"✅ Импорт завершён. Создано: {created}, обновлено: {updated}", messages.SUCCESS)
        return redirect("..")

admin.site.register(Parameter, ParameterAdmin)
admin.site.register(Entry)
admin.site.register(EntryValue)
