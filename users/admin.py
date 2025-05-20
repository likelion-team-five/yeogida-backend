from django.contrib import admin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ("id", "nickname", "level", "review_count", "like_count", "badge")
    search_fields = ("nickname",)
