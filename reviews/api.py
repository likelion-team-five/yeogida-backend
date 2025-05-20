from ninja import Router, Schema
from .models import Review
from datetime import datetime
from django.db.models import Q
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError
from ninja.security import django_auth
from .models import ReviewComment
from users.models import CustomUser

router = Router()

class ReviewListOut(Schema):
    reviewId: int
    title: str
    author: str
    region: str
    place: str
    likes: int
    views: int
    createdAt: datetime

class ReviewDetailOut(Schema):
    reviewId: int
    title: str
    author: str
    content: str
    region: str
    place: str
    likes: int
    views: int
    createdAt: datetime

class ReviewUpdateIn(Schema):
    title: str | None = None
    content: str | None = None
    region: str | None = None
    place: str | None = None

class ReviewCreateIn(Schema):
    title: str
    content: str
    region: str
    place: str

class CommentCreateIn(Schema):
    content: str

class CommentOut(Schema):
    commentId: int
    author: str
    content: str
    createdAt: datetime

@router.get("", response=list[ReviewListOut])
def list_reviews(request, searchType: str = None, keyword: str = None,
                 sortBy: str = "created_at", order: str = "desc", region: str = None):

    queryset = Review.objects.all()

    # 검색 필터
    if searchType and keyword:
        if searchType == "title":
            queryset = queryset.filter(title__icontains=keyword)
        elif searchType == "author":
            queryset = queryset.filter(author__username__icontains=keyword)

    # 지역 필터
    if region:
        queryset = queryset.filter(region__icontains=region)

    # 정렬
    if sortBy in ["created_at", "likes", "views"]:
        sort_prefix = "" if order == "asc" else "-"
        queryset = queryset.order_by(f"{sort_prefix}{sortBy}")

    response = []
    for r in queryset:
        response.append({
            "reviewId": r.id,
            "title": r.title,
            "author": r.author.username,  # ForeignKey → str
            "region": r.region,
            "place": r.place,
            "likes": r.likes,
            "views": r.views,
            "createdAt": r.created_at
        })

    return response

@router.get("/{review_id}", response=ReviewDetailOut)
def retrieve_review(request, review_id: int):
    review = get_object_or_404(Review, id=review_id)

    # 조회수 증가
    review.views += 1
    review.save()

    return {
        "reviewId": review.id,
        "title": review.title,
        "author": review.author.nickname,
        "content": review.content,
        "region": review.region,
        "place": review.place,
        "likes": review.likes,
        "views": review.views,
        "createdAt": review.created_at,
    }

@router.patch("/{review_id}", response=ReviewDetailOut)
def update_review(request, review_id: int, payload: ReviewUpdateIn):
    review = get_object_or_404(Review, id=review_id)

    # 필드가 넘어왔을 때만 수정
    if payload.title is not None:
        review.title = payload.title
    if payload.content is not None:
        review.content = payload.content
    if payload.region is not None:
        review.region = payload.region
    if payload.place is not None:
        review.place = payload.place

    review.save()

    return {
        "reviewId": review.id,
        "title": review.title,
        "author": review.author.nickname,
        "content": review.content,
        "region": review.region,
        "place": review.place,
        "likes": review.likes,
        "views": review.views,
        "createdAt": review.created_at,
    }

@router.delete("/{review_id}")
def delete_review(request, review_id: int):
    review = get_object_or_404(Review, id=review_id)
    review.delete()
    return {"message": f"Review {review_id} has been deleted."}

@router.post("", response=ReviewDetailOut, auth=django_auth)

def create_review(request, payload: ReviewCreateIn):
    user = request.auth  # 로그인된 사용자

    if not user:
        raise HttpError(401, "Unauthorized")

    review = Review.objects.create(
        author=user,
        title=payload.title,
        content=payload.content,
        region=payload.region,
        place=payload.place,
    )

    return {
        "reviewId": review.id,
        "title": review.title,
        "author": review.author.nickname,
        "content": review.content,
        "region": review.region,
        "place": review.place,
        "likes": review.likes,
        "views": review.views,
        "createdAt": review.created_at,
    }

@router.post("/{review_id}/likes")
def like_review(request, review_id: int):
    review = get_object_or_404(Review, id=review_id)
    review.likes += 1
    review.save()
    return {"message": f"Review {review_id} liked!", "likes": review.likes}

@router.delete("/{review_id}/likes")
def unlike_review(request, review_id: int):
    review = get_object_or_404(Review, id=review_id)

    # 음수 방지
    if review.likes > 0:
        review.likes -= 1
        review.save()
        return {"message": f"Review {review_id} unliked", "likes": review.likes}
    else:
        return {"message": "Like count is already 0", "likes": review.likes}
    
@router.post("/{review_id}/comments", response=CommentOut)
def create_comment(request, review_id: int, payload: CommentCreateIn):
    review = get_object_or_404(Review, id=review_id)
    user = CustomUser.objects.first()  # 테스트용 사용자 지정
    #user = request.auth  # 실제 로그인된 사용자 기준-> 연동할때 수정
    #if not user:
        #raise HttpError(401, "로그인이 필요합니다.")
    comment = ReviewComment.objects.create(
        review=review,
        author=user,
        content=payload.content
    )

    return {
        "commentId": comment.id,
        "author": comment.author.nickname,
        "content": comment.content,
        "createdAt": comment.created_at,
    }