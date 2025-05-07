from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Entry, EntryValue, Parameter
from .forms import EntryForm
from datetime import date


def add_entry(request):
    today = date.today()
    entry, _ = Entry.objects.get_or_create(date=today)

    # 🔹 Собираем данные для предзаполнения формы
    initial_data = {"comment": entry.comment}
    for ev in EntryValue.objects.filter(entry=entry):
        initial_data[ev.parameter.key] = ev.value

    if request.method == "POST":
        form = EntryForm(request.POST)
        if form.is_valid():
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
        form = EntryForm(initial=initial_data)  # ← предзаполняем

    return render(request, "diary/add_entry.html", {"form": form})

def entry_success(request):
    return HttpResponse("✅ Запись успешно добавлена или обновлена.")