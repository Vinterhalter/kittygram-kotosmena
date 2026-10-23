from django.conf import settings
from django.db import models


class Achievement(models.Model):
    name = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Cat(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cats"
    )
    name = models.CharField(max_length=32)
    color = models.CharField(max_length=32)
    birth_year = models.PositiveSmallIntegerField()
    image = models.ImageField(upload_to="cats/", blank=True)
    achievements = models.ManyToManyField(Achievement, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name
