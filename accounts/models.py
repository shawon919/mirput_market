from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
from cloudinary.models import CloudinaryField

# USER MODEL
class User(AbstractUser):
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email

# PROFILE MODEL
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    image = CloudinaryField(
        blank=True,
        null=True
    )


# OTP MODEL
class OTP(models.Model):
    email = models.EmailField(null=True, blank=True)
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, default="verify")
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def is_valid(self):
        expiry_time = self.created_at + timedelta(minutes=10)
        return (not self.is_used) and timezone.now() < expiry_time