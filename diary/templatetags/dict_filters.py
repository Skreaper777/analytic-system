# diary/templatetags/dict_filters.py
from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    if isinstance(d, dict):
        return d.get(key, '')
    return ''
