from ninja import Router

from .views import carpool_router

urlpatterns = carpool_router.urls
