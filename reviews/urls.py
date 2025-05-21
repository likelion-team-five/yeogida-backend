from ninja import Router

from .views import review_router

urlpatterns = review_router.urls
