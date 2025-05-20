from django.db import models

from users.models import CustomUser  # 사용자 모델


class Course(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    duration = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    theme = models.JSONField()  # 문자열 리스트 저장
    image_url = models.URLField()
    rating = models.FloatField()
    currency = models.CharField(max_length=10)
    amount = models.IntegerField()


class Site(models.Model):
    course = models.ForeignKey(Course, related_name="sites", on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)


class FavoriteCourse(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "course")  # 중복 찜 방지
        ordering = ["created_at"]  # 찜한 순서대로 정렬

    def __str__(self):
        return f"{self.user.nickname} - {self.course.name}"
