from django.contrib import admin
from .models import Parameter, Entry, EntryValue
import re

# Простая таблица транслитерации
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
    prepopulated_fields = {"key": ("name_ru",)}  # JS автозаполнение

    def save_model(self, request, obj, form, change):
        if not obj.key:
            obj.key = translit(obj.name_ru)
        super().save_model(request, obj, form, change)

admin.site.register(Parameter, ParameterAdmin)
admin.site.register(Entry)
admin.site.register(EntryValue)
