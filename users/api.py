import requests
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from ninja import Router

from .models import CustomUser

router = Router(tags=["Kakao Auth"])


# 카카오 로그인 시작 엔드포인트
@router.get("/login/kakao/")
def kakao_login(request: HttpRequest) -> HttpResponse:
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}&response_type=code"
    )
    return redirect(kakao_auth_url)


# 카카오 콜백 엔드포인트
@router.get("/kakao/callback/")
def kakao_callback(request: HttpRequest, code: str):
    try:
        token_url = "https://kauth.kakao.com/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_REST_API_KEY,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
            "code": code,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_response = requests.post(token_url, data=payload, headers=headers)
        token_data = token_response.json()

        if "error" in token_data:
            print(
                f"Token Error: {token_data.get('error')}, {token_data.get('error_description')}"
            )
            return {"error": "Failed to get Kakao token"}

        access_token = token_data.get("access_token")
        # refresh_token = token_data.get("refresh_token")

        # 액세스 토큰으로 사용자 정보 가져오기
        user_info_url = "https://kapi.kakao.com/v2/user/me"
        user_info_headers = {"Authorization": f"Bearer {access_token}"}
        user_info_response = requests.get(user_info_url, headers=user_info_headers)
        user_info = user_info_response.json()

        print(f"Kakao User Info: {user_info}")  # 디버깅용 출력

        kakao_id = user_info.get("id")
        properties = user_info.get("properties", {})

        nickname = properties.get("nickname")
        profile_image_url = properties.get("profile_image")

        if not kakao_id:
            print("Error: Kakao ID not received")
            return {"error": "Kakao ID not received"}

        try:
            user = CustomUser.objects.get(id=str(kakao_id))

            print(f"Existing user found: {user.id}")
            login(request, user)
            return {
                "message": "Kakao login successful",
                "user": {"id": user.id, "nickname": user.nickname},
            }

        except CustomUser.DoesNotExist:
            print(f"No existing user, creating new one for Kakao ID: {kakao_id}")

            user = CustomUser.objects.create_user(
                id=str(kakao_id), nickname=nickname, profile_image_url=profile_image_url
            )

            login(request, user)
            return {
                "message": "Kakao signup and login successful",
                "user": {"id": user.id, "nickname": user.nickname},
            }

    except requests.exceptions.RequestException as e:
        print(f"Request Error during Kakao API call: {e}")
        return {"error": "Error during Kakao API call"}
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return {"error": "An unexpected error occurred"}


# 예시: 로그인 성공 후 리다이렉트할 빈 페이지 (실제 서비스에서는 유효한 URL 사용)
# TODO: 실제 로그인 성공 후 랜딩 페이지에 대한 Ninja 엔드포인트 필요
# @router.get("/login/success/")
# def login_success_page(request: HttpRequest):
#     if request.user.is_authenticated:
#         return {"message": f"Welcome, {request.user.nickname}!"}
#     return {"message": "Login required"}
