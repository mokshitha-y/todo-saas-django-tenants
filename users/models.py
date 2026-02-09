from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Global PUBLIC user.
    No tenant-specific data here.
    """

    keycloak_id = models.CharField(max_length=255, null=True, blank=True, unique=True)

    def __str__(self):
        return self.username
