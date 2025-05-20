from django.contrib import admin

from .models import Course, FavoriteCourse, Site

admin.site.register(Course)
admin.site.register(Site)
admin.site.register(FavoriteCourse)
