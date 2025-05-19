from django.shortcuts import get_object_or_404
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from .models import CarpoolComment

router = Router(tags=["Carpools"], auth=JWTAuth())


@router.delete("/{carpool_id}/comments/{comment_id}")
def delete_carpool_comment(request, carpool_id: int, comment_id: int):
    """
    지정된 카풀(carpool_id)의 댓글(comment_id)을 삭제합니다.
    """
    comment = get_object_or_404(CarpoolComment, id=comment_id, carpool_id=carpool_id)
    comment.delete()
    return {"detail": "댓글이 삭제되었습니다."}
