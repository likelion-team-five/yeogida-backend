from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, render
from ninja import Router
from ninja.errors import HttpError

from .models import Review, ReviewComment

review_router = Router()


@review_router.post("/")
def create_review(request, title: str, content: str):
    # 인증된 사용자만 게시글 생성 가능
    if not request.user.is_authenticated:
        raise HttpError(401, "Unauthorized")

    try:
        # 후기 게시글 생성
        review = Review.objects.create(
            author=request.user, title=title, content=content
        )
        return {
            "id": review.id,
            "author": review.author.nickname,
            "title": review.title,
            "content": review.content,
            "created_at": review.created_at,
        }

    except IntegrityError as e:
        raise HttpError(400, "Failed to create review.")


@review_router.get("/{review_id}/comments")
def list_review_comments(request, review_id: int):
    # 해당 리뷰 가져오기 (존재하지 않으면 404 반환)
    review = get_object_or_404(Review, id=review_id)

    # 해당 리뷰의 모든 댓글 조회
    comments = review.comments.all().order_by("-created_at")

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


@review_router.delete("/{review_id}/comments/{comment_id}")
def delete_review_comment(request, review_id: int, comment_id: int):
    # 리뷰가 존재하는지 먼저 확인
    review = get_object_or_404(Review, id=review_id)

    # 특정 댓글 가져오기 (존재하지 않으면 404 반환)
    comment = get_object_or_404(ReviewComment, id=comment_id, review=review)

    # 본인 댓글인지 확인 (인증된 사용자라면)
    if request.user.is_authenticated and comment.author != request.user:
        raise HttpError(403, "You are not allowed to delete this comment.")

    # 댓글 삭제
    comment.delete()
    return {"detail": "Comment deleted successfully."}
