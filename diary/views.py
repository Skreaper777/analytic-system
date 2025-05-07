import logging
from django.shortcuts import render, redirect
from .models import Entry, EntryValue, Parameter
from .forms import EntryForm
from datetime import date, datetime

# Настройка логгера для отладки
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)


def add_entry(request):
    # Определяем дату: из GET-параметра или текущая
    date_str = request.GET.get('date')
    try:
        entry_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        entry_date = date.today()
        logger.debug(f"[add_entry] Invalid date format '{date_str}', fallback to today")

    logger.debug(f"[add_entry] Entry date: {entry_date}")
    entry, created = Entry.objects.get_or_create(date=entry_date)
    logger.debug(f"[add_entry] Entry fetched: id={entry.id}, created={created}, comment='{entry.comment}'")

    # Предзаполнение
    initial_data = {"comment": entry.comment}
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
            return redirect(f"/add/?date={entry_date}")
        else:
            logger.debug(f"[add_entry] Form errors: {form.errors}")
    else:
        form = EntryForm(initial=initial_data)
        logger.debug("[add_entry] Rendering form with initial data.")

    context = {
        "form": form,
        "range_6": range(6),
        "today_str": entry_date.strftime('%Y-%m-%d'),
    }
    logger.debug(f"[add_entry] Context prepared: date={context['today_str']}")
    return render(request, "diary/add_entry.html", context)


def entry_success(request):
    return render(request, "diary/success.html")
