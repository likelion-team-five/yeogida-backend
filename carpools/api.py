from datetime import datetime
from typing import List

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Query, Router, Schema

from .models import Carpool, CarpoolComment

router = Router()


class CarpoolCommentSchema(Schema):
    id: int
    content: str
    created_at: datetime


class CarpoolSchema(Schema):
    id: int
    departure: str
    destination: str
    departure_time: datetime
    seats_available: int
    title: str
    description: str
    comments: List[CarpoolCommentSchema]


class CarpoolCreateSchema(Schema):
    departure: str
    destination: str
    departure_time: datetime
    seats_available: int
    title: str
    description: str


@router.get("", response=List[CarpoolSchema])
def list_carpools(
    request,
    departure: str = Query(None),
    destination: str = Query(None),
    sort: str = Query("departure_time"),
):
    qs = Carpool.objects.prefetch_related("comments").all()

    if departure:
        qs = qs.filter(departure__icontains=departure)
    if destination:
        qs = qs.filter(destination__icontains=destination)

    if sort in ["departure_time", "-departure_time"]:
        qs = qs.order_by(sort)

    return list(qs)


@router.post("", response=CarpoolSchema)
def create_carpool(request, data: CarpoolCreateSchema):
    carpool = Carpool.objects.create(**data.dict())
    return carpool


@router.get("/{carpool_id}", response=CarpoolSchema)
def get_carpool(request, carpool_id: int):
    carpool = get_object_or_404(
        Carpool.objects.prefetch_related("comments"), id=carpool_id
    )
    return carpool


@router.patch("/{carpool_id}", response=CarpoolSchema)
def update_carpool(request, carpool_id: int, data: CarpoolCreateSchema):
    carpool = get_object_or_404(Carpool, id=carpool_id)
    for attr, value in data.dict().items():
        setattr(carpool, attr, value)
    carpool.save()
    return carpool


@router.delete("/{carpool_id}")
def delete_carpool(request, carpool_id: int):
    carpool = get_object_or_404(Carpool, id=carpool_id)
    carpool.delete()
    return {"success": True}


@router.post("/{carpool_id}/likes")
def like_carpool(request, carpool_id: int):
    carpool = get_object_or_404(Carpool, id=carpool_id)
    carpool.likes += 1
    carpool.save()
    return {"likes": carpool.likes}


@router.delete("/{carpool_id}/likes")
def unlike_carpool(request, carpool_id: int):
    carpool = get_object_or_404(Carpool, id=carpool_id)
    if carpool.likes > 0:
        carpool.likes -= 1
        carpool.save()
    return {"likes": carpool.likes}


@router.post("/{carpool_id}/comments")
def add_comment(request, carpool_id: int, data: CarpoolCommentSchema):
    carpool = get_object_or_404(Carpool, id=carpool_id)
    carpool.comments.create(content=data.content)
    return {"message": "댓글이 작성되었습니다."}


@router.delete("/{carpool_id}/comments/{comment_id}")
def delete_carpool_comment(request, carpool_id: int, comment_id: int):
    """
    지정된 카풀(carpool_id)의 댓글(comment_id)을 삭제합니다.
    """
    comment = get_object_or_404(CarpoolComment, id=comment_id, carpool_id=carpool_id)
    comment.delete()
    return {"message": "댓글이 삭제되었습니다."}


@router.get("")
def list_carpools(request):
    carpools = Carpool.objects.all().order_by("-created_at")
    data = [
        {
            "id": carpool.id,
            "title": carpool.title,
            "description": carpool.description,
            "departure": carpool.departure,
            "destination": carpool.destination,
            "departure_time": carpool.departure_time,
            "user_id": carpool.user.id,
        }
        for carpool in carpools
    ]
    return JsonResponse(data, safe=False)


@router.get("/{carpool_id}/comments")
def get_carpool_comments(request, carpool_id: int):
    carpool = get_object_or_404(Carpool, id=carpool_id)
    comments = carpool.comments.select_related("author").all()

    comment_list = [
        {
            "id": comment.id,
            "author": comment.author.username,
            "content": comment.content,
            "created_at": comment.created_at.isoformat(),
        }
        for comment in comments
    ]

    return JsonResponse(comment_list, safe=False)
