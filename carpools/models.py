from django.db import models

from users.models import CustomUser

# Create your models here.


class Carpool(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    departure = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    departure_time = models.DateTimeField()
    seats_available = models.PositiveIntegerField()
    author = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    likes = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class CarpoolComment(models.Model):
    carpool = models.ForeignKey(
        Carpool, on_delete=models.CASCADE, related_name="comments"
    )
    content = models.TextField()
    author = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment on {self.carpool.id} - {self.content[:20]}"
