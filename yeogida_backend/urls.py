from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

from carpools.api import router as carpool_router
from courses.api import router as course_router
from rankings.api import router as ranking_router

# from reviews.api import router as review_router
from users.api import auth_router, user_router

api = NinjaAPI()


api.add_router("/carpools", carpool_router)
api.add_router("/courses", course_router)
api.add_router("/rankings", ranking_router)
# api.add_router("/reviews", review_router)
api.add_router("/auth", auth_router)
api.add_router("/users", user_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]
