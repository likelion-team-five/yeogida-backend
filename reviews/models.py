from django.db import models

from users.models import CustomUser


class Review(models.Model):
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.author.nickname}"


class ReviewComment(models.Model):
    review = models.ForeignKey(
        Review, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.nickname}: {self.content[:20]}"
