from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Global PUBLIC user.
    No tenant-specific data here.
    """

    # You can later switch to email login if needed
    # email = models.EmailField(unique=True)

    def __str__(self):
        return self.username
