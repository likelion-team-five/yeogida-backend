from ninja import Router

from .views import user_router

urlpatterns = user_router.urls
