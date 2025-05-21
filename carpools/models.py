from django.db import models

from users.models import CustomUser


class Carpool(models.Model):
    driver = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name="carpools"
    )
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    departure_time = models.DateTimeField()
    available_seats = models.PositiveIntegerField(default=4)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.origin} -> {self.destination} (Driver: {self.driver.nickname})"


class CarpoolComment(models.Model):
    carpool = models.ForeignKey(
        Carpool, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.nickname}: {self.content[:20]}"
