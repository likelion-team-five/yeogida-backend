from ninja import Router
from users.models import CustomUser
from typing import List
from django.http import JsonResponse

router = Router()

@router.get("")
def get_rankings(request, sortBy: str = "level", order: str = "desc", limit: int = 10):
    sort_field = sortBy
    if order == "desc":
        sort_field = f"-{sortBy}"
    
    users = CustomUser.objects.all().order_by(sort_field)[:limit]

    data = []
    for idx, user in enumerate(users, start=1):
        data.append({
            "rank": idx,
            "nickname": user.nickname,
            "level": user.level,
            "reviewCount": user.review_count,
            "likeCount": user.like_count,
            "badge": user.badge,
            "profile_Image": user.profile_image_url
        })

    return JsonResponse(data, safe=False)