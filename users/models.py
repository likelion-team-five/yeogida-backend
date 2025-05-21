from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


# 커스텀 유저 매니저 정의
class CustomUserManager(BaseUserManager):
    def create_user(self, id, nickname, password=None, **extra_fields):
        if not id:
            raise ValueError("Users must have an ID")
        if not nickname:
            raise ValueError("Users must have a nickname")

        user = self.model(id=id, nickname=nickname, **extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, id, nickname, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(id, nickname, password, **extra_fields)


# 커스텀 유저 모델 정의
class CustomUser(AbstractBaseUser, PermissionsMixin):
    id = models.CharField(unique=True, max_length=20, primary_key=True)
    nickname = models.CharField(max_length=30)
    profile_image_url = models.URLField(max_length=500, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = CustomUserManager()  # 위에서 정의한 매니저 할당

    USERNAME_FIELD = "id"
    REQUIRED_FIELDS = ["nickname"]

    def __str__(self):
        return self.nickname

    def has_perm(self, perm, obj=None):
        return self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_superuser


# 지역 모델 추가
class Region(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


# 방문 기록 모델 추가
class UserVisitedRegion(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    visit_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user", "region")

    def __str__(self):
        return f"{self.user.nickname} - {self.region.name} ({self.visit_count} visits)"
