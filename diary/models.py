from django.db import models

class Parameter(models.Model):
    key = models.CharField(max_length=50, unique=True)
    name_ru = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_ru

class Entry(models.Model):
    date = models.DateField(unique=True)
    comment = models.TextField(blank=True)

    def __str__(self):
        return f"Запись за {self.date}"

class EntryValue(models.Model):
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE)
    value = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('entry', 'parameter')
