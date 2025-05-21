from django.shortcuts import render
from ninja import Router

from .models import Carpool

carpool_router = Router()


@carpool_router.get("/")
def list_carpools(request):
    carpools = Carpool.objects.all().order_by("-created_at")

    result = [
        {
            "id": carpool.id,
            "driver_nickname": carpool.driver.nickname,
            "origin": carpool.origin,
            "destination": carpool.destination,
            "departure_time": carpool.departure_time,
            "available_seats": carpool.available_seats,
            "description": carpool.description,
            "created_at": carpool.created_at,
        }
        for carpool in carpools
    ]

    return result


@carpool_router.get("/{carpool_id}/comments")
def list_carpool_comments(request, carpool_id: int):
    # 해당 카풀 가져오기 (존재하지 않으면 404 반환)
    carpool = get_object_or_404(Carpool, id=carpool_id)

    # 해당 카풀의 모든 댓글 조회
    comments = carpool.comments.all().order_by("-created_at")

    # 댓글 목록 반환
    result = [
        {
            "id": comment.id,
            "author": comment.author.nickname,
            "content": comment.content,
            "created_at": comment.created_at,
        }
        for comment in comments
    ]

    return result
