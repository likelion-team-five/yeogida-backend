from django.contrib import admin

from .models import Carpool, CarpoolComment

# Register your models here.
admin.site.register(Carpool)
admin.site.register(CarpoolComment)
