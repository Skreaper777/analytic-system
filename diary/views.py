from django.shortcuts import render, redirect
from .models import Entry, EntryValue, Parameter
from .forms import EntryForm
from datetime import date

def add_entry(request):
    if request.method == "POST":
        form = EntryForm(request.POST)
        if form.is_valid():
            entry, created = Entry.objects.get_or_create(date=date.today())
            entry.comment = form.cleaned_data["comment"]
            entry.save()
            for param in Parameter.objects.filter(active=True):
                val = form.cleaned_data.get(param.key)
                if val is not None:
                    EntryValue.objects.update_or_create(
                        entry=entry,
                        parameter=param,
                        defaults={"value": val}
                    )
            return redirect("entry_success")
    else:
        form = EntryForm()
    return render(request, "diary/add_entry.html", {"form": form})

def entry_success(request):
    return render(request, "diary/success.html")
