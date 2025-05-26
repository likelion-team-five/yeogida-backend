# users/api.py

from typing import List, Optional

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from ninja import Query, Router, Schema
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken

from courses.models import FavoriteCourse

# Schema for refresh token input
class RefreshTokenInput(Schema):
    refresh: str

from courses.schemas import CourseOut, SiteSchema

from .models import CustomUser, Region, UserVisitedRegion
from .schemas import TokenObtainPairOutput, UpdateUserIn, UserOut


# 인증 관련 엔드포인트를 위한 라우터
auth_router = Router(tags=["Authentication"])


# 사용자 정보 관련 엔드포인트를 위한 라우터
user_router = Router(tags=["Users"])


# 토큰과 사용자 정보를 담을 응답 스키마 정의 (카카오 로그인 응답용)
class TokenObtainPairOutput(Schema):
    access_token: str
    refresh_token: str
    user: Optional[dict] = None

# 새롭게 추가: 프론트엔드에서 카카오 인가 코드를 보낼 스키마
class KakaoCodeInput(Schema):
    code: str

# 카카오 로그인 시작 엔드포인트 (변경 없음)
@auth_router.get("/login/kakao/") # 최종 경로: /api/v1/auth/login/kakao/
def kakao_login(request: HttpRequest) -> HttpResponse:
    """
    카카오 로그인 프로세스를 시작하기 위해 카카오 인가 코드 요청 URL로 리다이렉트합니다.
    """
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}&response_type=code"
    )
    return redirect(kakao_auth_url)


# 카카오 콜백 엔드포인트 (역할 변경: 인가 코드 수신 및 프론트엔드로 리다이렉트)
@auth_router.get("/kakao/callback/") # 최종 경로: /api/v1/auth/kakao/callback/
def kakao_callback(request: HttpRequest, code: str):
    """
    카카오로부터 인가 코드를 받아 프론트엔드로 전달합니다.
    (실제 토큰 발급은 별도의 POST 엔드포인트에서 처리)
    """
    redirect_to = f"{settings.FRONTEND_LOGIN_SUCCESS_URI}?code={code}"
    return redirect(redirect_to)


# 새로운 카카오 로그인 처리 엔드포인트 (POST로 변경)
@auth_router.post("/kakao/login/process", response=TokenObtainPairOutput) # 최종 경로: /api/v1/auth/kakao/login/process
def kakao_login_process(request: HttpRequest, data: KakaoCodeInput):
    """
    프론트엔드로부터 카카오 인가 코드를 받아 카카오 토큰을 발급하고
    사용자 정보를 기반으로 우리 서비스의 JWT를 생성합니다.
    """
    code = data.code # POST 요청 바디에서 code를 가져옵니다.

    try:
        # 카카오 토큰 요청
        token_url = "https://kauth.kakao.com/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_REST_API_KEY,
            "redirect_uri": settings.KAKAO_REDIRECT_URI, # 카카오 앱 설정에 등록된 리다이렉트 URI와 동일해야 합니다.
            "code": code,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_response = requests.post(token_url, data=payload, headers=headers)
        token_response.raise_for_status()
        token_data = token_response.json()

        if "error" in token_data:
            print(
                f"Token Error: {token_data.get('error')}, {token_data.get('error_description')}"
            )
            # 프론트엔드에 오류 응답
            return {"error": "Failed to get Kakao token", "details": token_data.get("error_description")}

        kakao_access_token = token_data.get("access_token")

        if not kakao_access_token:
            print("Error: Kakao access_token not received")
            return {"error": "Kakao access_token not received"}

        # 카카오 사용자 정보 요청
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        user_info_headers = {"Authorization": f"Bearer {kakao_access_token}"}
        user_info_response = requests.get(user_info_url, headers=user_info_headers)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()

        print(f"Kakao User Info: {user_info}")

        kakao_id = user_info.get("id")
        if not kakao_id:
            print("Error: Kakao ID not received")
            return {"error": "Kakao ID not received"}

        kakao_id_str = str(kakao_id)
        properties = user_info.get("properties", {})
        nickname = properties.get("nickname")
        profile_image_url = properties.get("profile_image")

        try:
            user = CustomUser.objects.get(id=kakao_id_str)
            print(f"Existing user found: {user.id}")

            # 카카오에서 받아온 최신 정보로 사용자 정보 업데이트
            user.nickname = nickname
            user.profile_image_url = profile_image_url
            user.save()

        except CustomUser.DoesNotExist:
            print(f"No existing user, creating new one for Kakao ID: {kakao_id_str}")
            try:
                user = CustomUser.objects.create_user(
                    id=kakao_id_str,
                    nickname=nickname,
                    profile_image_url=profile_image_url,
                )
                print(f"New user created with ID: {user.id}")
            except Exception as create_error:
                print(f"Error creating new user: {create_error}")
                import traceback

                traceback.print_exc()
                return {"error": f"Failed to create user: {str(create_error)}"}

        # Django-Ninja-JWT를 사용하여 토큰 생성
        refresh = RefreshToken.for_user(user)
        app_access_token = str(refresh.access_token)
        app_refresh_token = str(refresh)

        # 사용자 정보 직렬화
        user_data = {
            "id": str(user.id),
            "nickname": user.nickname,
            "profile_image_url": user.profile_image_url,
        }

        return TokenObtainPairOutput(
            access_token=app_access_token,
            refresh_token=app_refresh_token,
            user=user_data,
        )

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error during Kakao API call: {e}")
        error_details = e.response.json() if e.response else str(e)
        return {"error": "Error during Kakao API call", "details": error_details}
    except requests.exceptions.RequestException as e:
        print(f"Request Error during Kakao API call: {e}")
        return {"error": "Error during Kakao API call", "details": str(e)}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback

        traceback.print_exc()
        return {"error": "An unexpected error occurred", "details": str(e)}

@auth_router.post("/token/refresh", response=TokenObtainPairOutput)
def refresh_jwt_token(request, payload: RefreshTokenInput):
    """
    액세스 토큰 만료 시 리프레시 토큰을 사용하여 새로운 액세스 토큰을 발급합니다.
    """
    try:
        refresh = RefreshToken(payload.refresh)
        access_token = str(refresh.access_token)
        return TokenObtainPairOutput(
            access_token=access_token,
            refresh_token=str(refresh),
        )
    except Exception as e:
        # Handle invalid token errors (e.g., expired or invalid refresh token)
        print(f"Token refresh error: {e}")
        # It's good practice to return a 401 Unauthorized or similar for invalid tokens
        return {"detail": "Invalid token or token expired"}, 401

# --- (이 아래 사용자 관련 엔드포인트는 변경 없음) ---

#  마이페이지 (내 정보 조회)
@user_router.get("/me", response=UserOut, auth=JWTAuth()) # 최종 경로: /api/v1/users/me
def me(request: HttpRequest):
    """
    로그인한 사용자의 정보를 조회합니다.
    마이페이지에서 사용자 이름, 닉네임, 이메일, 레벨, 프로필 사진 등을 확인할 때 사용할 수 있습니다.
    """
    user: CustomUser = request.user
    return UserOut(
        userId=user.id,
        nickname=user.nickname,
        name=user.name,
        email=user.email,
        level=user.level,
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )


#  마이페이지 (내 정보 수정)
@user_router.patch("/me", response=UserOut, auth=JWTAuth()) # 최종 경로: /api/v1/users/me
def update_me(request: HttpRequest, data: UpdateUserIn):
    """
    로그인한 사용자의 정보를 수정합니다.
    닉네임이나 프로필 사진 등을 일부 변경할 수 있습니다.
    """
    user: CustomUser = request.user
    if data.nickname is not None:
        user.nickname = data.nickname
    if data.profile_image_url is not None:
        user.profile_image_url = data.profile_image_url
    user.save()
    return UserOut(
        userId=user.id,
        nickname=user.nickname,
        name=user.name,
        email=user.email,
        level=user.level,
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )


#  마이페이지 (회원 탈퇴)
@user_router.delete("/me", auth=JWTAuth()) # 최종 경로: /api/v1/users/me
def delete_me(request: HttpRequest):
    """
    현재 로그인한 사용자의 계정을 삭제합니다.
    탈퇴 요청 시 사용자 정보를 삭제하며, 복구는 불가능합니다.
    """
    user: CustomUser = request.user
    user.delete()
    return {"detail": "User account deleted"}


#  마이페이지 (찜한 코스 목록 조회)
@user_router.get("/me/favorites", response=List[CourseOut], auth=JWTAuth()) # 최종 경로: /api/v1/users/me/favorites
def get_favorite_courses(
    request, limit: Optional[int] = Query(None, description="가져올 최대 찜 코스 수")
):
    """
    로그인한 사용자가 찜한 코스 목록을, 찜한 순서대로 조회합니다.
    - limit가 주어지면 최대 limit개만 반환합니다.
    """
    favs = (
        FavoriteCourse.objects.filter(user=request.user)
        .select_related("course")
        .order_by("-created_at")
    )
    if limit:
        favs = favs[:limit]

    result = []
    for fav in favs:
        c = fav.course
        result.append(
            CourseOut(
                id=c.id,
                name=c.name,
                description=c.description,
                duration=c.duration,
                location=c.location,
                theme=c.theme,
                imageUrl=c.image_url,
                rating=c.rating,
                estimatedCost={
                    "currency": c.currency,
                    "amount": c.amount,
                },
                sites=[
                    SiteSchema(id=s.id, name=s.name, type=s.type) for s in c.sites.all()
                ],
            )
        )
    return result


@user_router.get("/me/visited-regions", auth=JWTAuth()) # 최종 경로: /api/v1/users/me/visited-regions
def get_my_visited_regions(request):
    """
    로그인한 사용자의 지역별 방문 횟수를 조회합니다.
    """
    visited = UserVisitedRegion.objects.filter(user=request.user).select_related(
        "region"
    )

    return [
        {
            "region_code": v.region.code,
            "region_name": v.region.name,
            "visit_count": v.visit_count,
        }
        for v in visited
    ]