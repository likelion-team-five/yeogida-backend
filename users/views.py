from django.shortcuts import get_object_or_404, render
from ninja import Router
from ninja.errors import HttpError

from .models import CustomUser, UserVisitedRegion

user_router = Router()


@user_router.get("/me/visited-regions")
def get_visited_regions(request):
    if not request.user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    visited_regions = UserVisitedRegion.objects.filter(user=request.user)
    return [
        {"region": v.region.name, "code": v.region.code, "visit_count": v.visit_count}
        for v in visited_regions
    ]
