from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja_jwt.authentication import JWTAuth

from users.models import CustomUser

from .models import Course, FavoriteCourse
from .schemas import CourseOut, SiteSchema

router = Router(tags=["Courses"], auth=JWTAuth())


@router.get("/", response=List[CourseOut])
def list_courses(request):
    courses = Course.objects.prefetch_related("sites").all()
    result = []
    for course in courses:
        result.append(
            CourseOut(
                id=course.id,
                name=course.name,
                description=course.description,
                duration=course.duration,
                location=course.location,
                theme=course.theme,
                imageUrl=course.image_url,
                rating=course.rating,
                estimatedCost={"currency": course.currency, "amount": course.amount},
                sites=[
                    SiteSchema(id=site.id, name=site.name, type=site.type)
                    for site in course.sites.all()
                ],
            )
        )
    return result


# 찜 추가
@router.post("/{course_id}/favorite")
def add_favorite_course(request, course_id: int):
    course = get_object_or_404(Course, id=course_id)
    FavoriteCourse.objects.get_or_create(user=request.user, course=course)
    return {"detail": "찜 완료!"}


# 찜 삭제
@router.delete("/{course_id}/favorite")
def remove_favorite_course(request, course_id: int):
    course = get_object_or_404(Course, id=course_id)
    FavoriteCourse.objects.filter(user=request.user, course=course).delete()
    return {"detail": "찜 취소 완료!"}
