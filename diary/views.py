import logging
from django.shortcuts import render, redirect
from .models import Entry, EntryValue, Parameter
from .forms import EntryForm
from datetime import date

# Настройка логгера для отладки
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)


def add_entry(request):
    today = date.today()
    logger.debug(f"[add_entry] Today: {today}")
    entry, created = Entry.objects.get_or_create(date=today)
    logger.debug(f"[add_entry] Entry fetched: id={entry.id}, created={created}, comment='{entry.comment}'")

    # Предзаполнение
    initial_data = {"comment": entry.comment}
    logger.debug(f"[add_entry] Initial comment: {entry.comment}")
    for ev in EntryValue.objects.filter(entry=entry):
        initial_data[ev.parameter.key] = ev.value
        logger.debug(f"[add_entry] Pre-fill {ev.parameter.key} = {ev.value}")

    logger.debug(f"[add_entry] Complete initial_data: {initial_data}")

    if request.method == "POST":
        logger.debug(f"[add_entry] POST data: {dict(request.POST)}")
        form = EntryForm(request.POST)
        if form.is_valid():
            logger.debug("[add_entry] Form is valid. Cleaned data: %s", form.cleaned_data)
            entry.comment = form.cleaned_data["comment"]
            entry.save()
            logger.debug(f"[add_entry] Saved entry.comment = '{entry.comment}'")

            for param in Parameter.objects.filter(active=True):
                val = form.cleaned_data.get(param.key)
                logger.debug(f"[add_entry] Parameter '{param.key}', form value = {val}")
                if val is not None:
                    ev_obj, ev_created = EntryValue.objects.update_or_create(
                        entry=entry,
                        parameter=param,
                        defaults={"value": val}
                    )
                    logger.debug(f"[add_entry] EntryValue for '{param.key}': value={ev_obj.value}, created={ev_created}")
            return redirect("entry_success")
        else:
            logger.debug(f"[add_entry] Form errors: {form.errors}")
    else:
        form = EntryForm(initial=initial_data)
        logger.debug("[add_entry] Rendering form with initial data.")

    context = {"form": form, "range_6": range(6)}
    logger.debug(f"[add_entry] Context prepared, rendering template.")
    return render(request, "diary/add_entry.html", context)


def entry_success(request):
    return render(request, "diary/success.html")
