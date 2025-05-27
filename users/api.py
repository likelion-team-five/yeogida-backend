from typing import List, Optional, Union, Dict, Any

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from ninja import Query, Router, Schema
from ninja.responses import codes_4xx
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken

from courses.models import FavoriteCourse
from courses.schemas import CourseOut, SiteSchema

from .models import CustomUser, Region, UserVisitedRegion
from .schemas import TokenObtainPairOutput, UpdateUserIn, UserOut

class ErrorDetail(Schema):
    detail: str

auth_router = Router(tags=["Authentication"])

user_router = Router(tags=["Users"])


# --- 스키마 정의 ---
class KakaoLoginProcessInput(Schema):
    code: str

# --- 카카오 인증 관련 엔드포인트 ---

@auth_router.get("/login/kakao/")
def kakao_login_start(request: HttpRequest) -> HttpResponse:
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?response_type=code"
        f"&client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
    )
    return redirect(kakao_auth_url)


@auth_router.get("/kakao/callback/")
def kakao_callback(request: HttpRequest, code: str = Query(...)):
    redirect_url_to_frontend = f"{settings.FRONTEND_LOGIN_SUCCESS_URI}?code={code}"
    return redirect(redirect_url_to_frontend)


@auth_router.post(
    "/kakao/login/process",
    response={200: TokenObtainPairOutput, codes_4xx: ErrorDetail}, # 성공 및 에러 응답 스키마 명시
    summary="카카오 인가 코드로 로그인 처리 및 JWT 발급"
)
def kakao_login_process(request: HttpRequest, payload: KakaoLoginProcessInput) -> Union[tuple[int, ErrorDetail], TokenObtainPairOutput]:
    authorization_code = payload.code
    kakao_token_api_uri = "https://kauth.kakao.com/oauth/token"
    
    request_data = {
        "grant_type": "authorization_code",
        "client_id": settings.KAKAO_REST_API_KEY,
        "redirect_uri": settings.KAKAO_REDIRECT_URI,
        "code": authorization_code,
    }

    # if getattr(settings, 'KAKAO_CLIENT_SECRET', None):
    #     request_data["client_secret"] = settings.KAKAO_CLIENT_SECRET

    try:
        token_response = requests.post(kakao_token_api_uri, data=request_data, timeout=10) # 타임아웃 증가
        token_response.raise_for_status()
        kakao_tokens = token_response.json()
    except requests.exceptions.Timeout:
        print("DEBUG: 카카오 토큰 발급 요청 시간 초과")
        return 408, ErrorDetail(detail="카카오 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.")
    except requests.exceptions.RequestException as e:
        error_message = "카카오 토큰 발급 요청 중 오류가 발생했습니다."
        status_code_to_return = 400 # 기본값
        if hasattr(e, 'response') and e.response is not None:
            status_code_to_return = e.response.status_code if e.response.status_code >= 400 else 400
            try:
                error_details = e.response.json()
                error_message = f"카카오 인증 실패: {error_details.get('error', 'Unknown Error')} - {error_details.get('error_description', 'No description')}"
            except ValueError:
                error_message = f"카카오 인증 실패: 응답을 해석할 수 없습니다. Status: {e.response.status_code}, Body: {e.response.text[:200]}" # 너무 긴 응답 자르기
        else:
            error_message = f"{error_message} 오류: {str(e)}"
        
        print(f"DEBUG: {error_message}")
        return status_code_to_return if status_code_to_return < 500 else 400, ErrorDetail(detail=error_message)


    kakao_access_token = kakao_tokens.get("access_token")
    if not kakao_access_token:
        return 400, ErrorDetail(detail="카카오로부터 액세스 토큰을 받지 못했습니다.")

    kakao_user_info_api_uri = "https://kapi.kakao.com/v2/user/me"
    headers = {
        "Authorization": f"Bearer {kakao_access_token}",
    }
    try:
        user_info_response = requests.get(kakao_user_info_api_uri, headers=headers, timeout=5)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
    except requests.exceptions.Timeout:
        print("DEBUG: 카카오 사용자 정보 요청 시간 초과")
        return 408, ErrorDetail(detail="카카오 사용자 정보 조회 중 시간 초과가 발생했습니다.")
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: 카카오 사용자 정보 요청 실패: {e}")
        return 400, ErrorDetail(detail="카카오 사용자 정보를 가져오는데 실패했습니다.")

    kakao_id = str(user_info.get("id"))
    if not kakao_id:
        return 400, ErrorDetail(detail="카카오 사용자 ID를 확인할 수 없습니다.")

    kakao_account = user_info.get("kakao_account", {})
    email = kakao_account.get("email")
    profile_info = kakao_account.get("profile", {})
    nickname = profile_info.get("nickname")
    profile_image_url = profile_info.get("profile_image_url")

    try:
        user = CustomUser.objects.get(kakao_id=kakao_id)
        if email and user.email != email: user.email = email
        if nickname and user.nickname != nickname: user.nickname = nickname
        if profile_image_url and user.profile_image_url != profile_image_url: user.profile_image_url = profile_image_url
        if not user.is_active: user.is_active = True # 휴면이었으면 활성화
        user.save()
    except CustomUser.DoesNotExist:
        username = f"kakao_{kakao_id}"
        try:
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                nickname=nickname,
                profile_image_url=profile_image_url,
                kakao_id=kakao_id,
                # name=profile_info.get("name", nickname),
            )
        except Exception as e:
            print(f"사용자 생성 오류: {e}")
            if email and CustomUser.objects.filter(email=email).exists():
                 return 400, ErrorDetail(detail=f"이미 해당 이메일({email})로 가입된 계정이 존재합니다.")
            return 500, ErrorDetail(detail="사용자 계정 생성 중 서버 내부 오류가 발생했습니다.")

    if not user.is_active:
        return 403, ErrorDetail(detail="사용자 계정이 비활성화 상태입니다.")

    refresh = RefreshToken.for_user(user)
    return TokenObtainPairOutput(
        refresh=str(refresh),
        access=str(refresh.access_token),
    )


@user_router.get("/me", response={200: UserOut, codes_4xx: ErrorDetail}, auth=JWTAuth())
def me(request: HttpRequest):
    user: CustomUser = request.user # JWTAuth는 인증 실패 시 자동으로 401을 반환합니다.
    return UserOut(
        userId=user.id,
        nickname=user.nickname,
        name=getattr(user, 'name', None),
        email=user.email,
        level=getattr(user, 'level', None),
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )

@user_router.patch("/me", response={200: UserOut, codes_4xx: ErrorDetail}, auth=JWTAuth())
def update_me(request: HttpRequest, data: UpdateUserIn):
    user: CustomUser = request.user
    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(user, key, value)
    user.save()
    return UserOut(
        userId=user.id,
        nickname=user.nickname,
        name=getattr(user, 'name', None),
        email=user.email,
        level=getattr(user, 'level', None),
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )

@user_router.delete("/me", response={200: Dict[str, str], codes_4xx: ErrorDetail}, auth=JWTAuth()) # 204 No Content가 더 적절할 수 있음
def delete_me(request: HttpRequest):
    user: CustomUser = request.user
    try:
        user.delete() # 또는 is_active = False
    except Exception as e:
        print(f"사용자 삭제 오류: {e}")
        return 500, ErrorDetail(detail="사용자 계정 삭제 중 오류가 발생했습니다.")
    return 200, {"detail": "User account successfully deleted."} # 또는 204 상태코드와 빈 응답


@user_router.get("/me/favorites", response={200: List[CourseOut], codes_4xx: ErrorDetail}, auth=JWTAuth())
def get_favorite_courses(
    request, limit: Optional[int] = Query(None, description="가져올 최대 찜 코스 수")
):
    user: CustomUser = request.user
    favs = (
        FavoriteCourse.objects.filter(user=user)
        .select_related("course__region", "course__author")
        .order_by("-created_at")
    )
    if limit is not None and limit > 0:
        favs = favs[:limit]

    result = []
    # ... (CourseOut 변환 로직은 동일)
    for fav in favs:
        c = fav.course
        result.append(
            CourseOut(
                id=c.id,
                name=c.name,
                description=getattr(c, 'description', None),
                duration=getattr(c, 'duration', None),
                location=getattr(c, 'location', None),
                theme=getattr(c, 'theme', None),
                imageUrl=getattr(c, 'image_url', None),
                rating=getattr(c, 'rating', 0.0),
                estimatedCost=getattr(c, 'estimated_cost', {"currency": "KRW", "amount": 0}),
                sites=[
                    SiteSchema(id=s.id, name=s.name, type=getattr(s, 'type', 'unknown')) for s in c.sites.all()
                ] if hasattr(c, 'sites') and c.sites.exists() else [],
            )
        )
    return result


@user_router.get("/me/visited-regions", response={200: List[Dict[str, Any]], codes_4xx: ErrorDetail}, auth=JWTAuth())
def get_my_visited_regions(request):
    user: CustomUser = request.user
    visited = UserVisitedRegion.objects.filter(user=user).select_related("region")
    return [
        {
            "region_code": v.region.code,
            "region_name": v.region.name,
            "visit_count": v.visit_count,
            "last_visited_at": v.last_visited_at.isoformat() if hasattr(v, 'last_visited_at') and v.last_visited_at else None,
        }
        for v in visited
    ]