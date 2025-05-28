from typing import List

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja_jwt.authentication import JWTAuth # JWTAuth import 확인

# users.models 에서 CustomUser import가 필요하다면 추가 (request.auth를 통해 접근 가능)
# from users.models import CustomUser

from .models import Course, FavoriteCourse
from .schemas import CourseOut, SiteSchema

router = Router(tags=["Courses"], auth=JWTAuth()) # 라우터 레벨에서 JWTAuth 적용


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


# 찜 목록 불러오기 (새로운 엔드포인트)
@router.get("/favorites/", response=List[CourseOut]) # URL을 /favorites/ 등으로 변경
def list_favorite_courses(request):
    # request.auth 에 인증된 사용자 객체가 들어옵니다 (ninja-jwt 사용 시)
    user = request.auth
    # 사용자가 찜한 FavoriteCourse 목록을 가져오고, 관련된 Course 정보도 함께 가져옵니다.
    favorite_relations = FavoriteCourse.objects.filter(user=user).select_related('course').prefetch_related('course__sites')

    result = []
    for fav_relation in favorite_relations:
        course = fav_relation.course
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
@router.post("/{course_id}/favorite/") # 일관성을 위해 끝에 / 추가 (선택 사항)
def add_favorite_course(request, course_id: int):
    course = get_object_or_404(Course, id=course_id)
    # request.auth 에 인증된 사용자 객체가 들어옵니다.
    FavoriteCourse.objects.get_or_create(user=request.auth, course=course)
    return {"detail": "찜 완료!"}


# 찜 삭제
@router.delete("/{course_id}/favorite/") # 일관성을 위해 끝에 / 추가 (선택 사항)
def remove_favorite_course(request, course_id: int):
    course = get_object_or_404(Course, id=course_id)
    # request.auth 에 인증된 사용자 객체가 들어옵니다.
    FavoriteCourse.objects.filter(user=request.auth, course=course).delete()
    return {"detail": "찜 취소 완료!"}