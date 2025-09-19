# -*- coding: utf-8 -*-
from django.db import models

import pytz

# ──────────────────────────────────────────────────────────────────────────────
# USER PROFILE 
# ──────────────────────────────────────────────────────────────────────────────
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    timezoneChoices = [(x, x) for x in pytz.common_timezones]
    timezone = models.CharField(
        max_length=100,
        choices=timezoneChoices,
    )
    configMaxBet = models.DecimalField(default=0, max_digits=14, decimal_places=2)
    configProcessEnabled = models.BooleanField(default=False)
    configTest = models.BooleanField(default=False)

    configGlobalTPEnabled = models.BooleanField(default=True)
    configGlobalTPThreshold = models.DecimalField(default=0, max_digits=5, decimal_places=2)
    configGlobalTPSleepdown = models.IntegerField(default=100)
    configGlobalTPWakeUp = models.DateTimeField(auto_now=False, auto_now_add=False, null=True)

    configLegacyGraph = models.BooleanField(default=True)

    def __str__(self):
        return (self.user.username)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()