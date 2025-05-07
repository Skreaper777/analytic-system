from django.contrib import admin
from .models import Parameter, Entry, EntryValue

admin.site.register(Parameter)
admin.site.register(Entry)
admin.site.register(EntryValue)
