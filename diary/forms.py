from django import forms
from .models import Parameter

class EntryForm(forms.Form):
    comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={'rows': 2})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for param in Parameter.objects.filter(active=True):
            self.fields[param.key] = forms.IntegerField(
                label=param.name_ru,
                required=False,
                min_value=0,
                max_value=5
            )
