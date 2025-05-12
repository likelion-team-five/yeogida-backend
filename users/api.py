from typing import Optional

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from ninja import Router, Schema
from ninja_jwt.tokens import RefreshToken

from .models import CustomUser

# 인증 관련 엔드포인트를 위한 라우터
auth_router = Router(tags=["Authentication"])

# 사용자 정보 관련 엔드포인트를 위한 라우터
user_router = Router(tags=["Users"])


# 토큰과 사용자 정보를 담을 응답 스키마 정의
class TokenObtainPairOutput(Schema):
    access_token: str
    refresh_token: str
    user: Optional[dict] = None


# 카카오 로그인 시작 엔드포인트
@auth_router.get("/login/kakao/")
def kakao_login(request: HttpRequest) -> HttpResponse:
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}&response_type=code"
    )
    return redirect(kakao_auth_url)


# 카카오 콜백 엔드포인트
@auth_router.get("/kakao/callback/")
def kakao_callback(request: HttpRequest, code: str):
    try:
        # 카카오 토큰 요청
        token_url = "https://kauth.kakao.com/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": settings.KAKAO_REST_API_KEY,
            "redirect_uri": settings.KAKAO_REDIRECT_URI,
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
            return {
                "error": "Failed to get Kakao token",
                "details": token_data.get("error_description"),
            }

        kakao_access_token = token_data.get("access_token")

        if not kakao_access_token:
            print("Error: Kakao access_token not received")
            return {"error": "Kakao access_token not received"}

        user_info_url = "https://kapi.kakao.com/v2/user/me"
        user_info_headers = {"Authorization": f"Bearer {kakao_access_token}"}
        user_info_response = requests.get(user_info_url, headers=user_info_headers)
        user_info_response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        user_info = user_info_response.json()

        print(f"Kakao User Info: {user_info}")

        kakao_id = user_info.get("id")
        if not kakao_id:
            print("Error: Kakao ID not received")
            return {"error": "Kakao ID not received"}

        kakao_id_str = str(kakao_id)  # DB 저장을 위해 문자열로 변환
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

        # 사용자 정보 직렬화 (필요에 따라 내용을 커스터마이징)
        user_data = {
            "id": str(user.id),
            "nickname": user.nickname,
            "profile_image_url": user.profile_image_url,
        }

        # TokenObtainPairOutput 스키마를 사용하여 응답 반환
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
