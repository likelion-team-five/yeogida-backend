from typing import List, Optional, Union, Dict, Any

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from ninja import Query, Router, Schema
from ninja.responses import codes_4xx, codes_5xx # codes_5xx 추가
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken


from .models import CustomUser # Region, UserVisitedRegion 등은 필요시 주석 해제
from .schemas import TokenObtainPairOutput, UpdateUserIn, UserOut # UserOut의 userId 필드 확인 필요


class ErrorDetail(Schema):
    detail: str

# 인증 관련 엔드포인트를 위한 라우터
auth_router = Router(tags=["Authentication"])

# 사용자 정보 관련 엔드포인트를 위한 라우터
user_router = Router(tags=["Users"])


# --- 스키마 정의 ---
class KakaoLoginProcessInput(Schema):
    code: str

# --- 카카오 인증 관련 엔드포인트 ---

@auth_router.get("/login/kakao/")
def kakao_login_start(request: HttpRequest) -> HttpResponse:
    # ... (이전과 동일)
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?response_type=code"
        f"&client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
    )
    return redirect(kakao_auth_url)


@auth_router.get("/kakao/callback/")
def kakao_callback(request: HttpRequest, code: str = Query(...)):
    # ... (이전과 동일)
    redirect_url_to_frontend = f"{settings.FRONTEND_LOGIN_SUCCESS_URI}?code={code}"
    return redirect(redirect_url_to_frontend)


@auth_router.post(
    "/kakao/login/process",
    response={
        200: TokenObtainPairOutput,
        codes_4xx: ErrorDetail,
        codes_5xx: ErrorDetail # 500 에러 스키마 추가
    },
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

    try:
        token_response = requests.post(kakao_token_api_uri, data=request_data, timeout=10)
        token_response.raise_for_status()
        kakao_tokens = token_response.json()
    except requests.exceptions.Timeout:
        print("DEBUG: 카카오 토큰 발급 요청 시간 초과")
        return 408, ErrorDetail(detail="카카오 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요.")
    except requests.exceptions.RequestException as e:
        error_message_detail = "카카오 토큰 발급 요청 중 오류가 발생했습니다."
        status_code_to_return = 400
        if hasattr(e, 'response') and e.response is not None:
            status_code_to_return = e.response.status_code if e.response.status_code >= 400 else 400
            try:
                error_details_json = e.response.json()
                kakao_error_code = error_details_json.get('error', 'Unknown Error Code')
                kakao_error_desc = error_details_json.get('error_description', 'No description')
                error_message_detail = f"카카오 인증 실패: {kakao_error_code} - {kakao_error_desc}"
                print(f"DEBUG: 카카오 API 에러 응답 JSON: {error_details_json}")
            except ValueError:
                error_response_text = e.response.text[:500]
                error_message_detail = f"카카오 인증 실패: 응답을 JSON으로 해석 불가. Status: {e.response.status_code}, Body: {error_response_text}"
                print(f"DEBUG: 카카오 API 에러 응답 TEXT: {error_response_text}")
        else:
            error_message_detail = f"{error_message_detail} 오류: {str(e)}"
        
        print(f"DEBUG 최종 에러 메시지 (클라이언트 전달용): {error_message_detail}")
        return status_code_to_return if status_code_to_return < 500 else 400, ErrorDetail(detail=error_message_detail)


    kakao_access_token = kakao_tokens.get("access_token")
    if not kakao_access_token:
        return 400, ErrorDetail(detail="카카오로부터 액세스 토큰을 받지 못했습니다.")

    kakao_user_info_api_uri = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {kakao_access_token}"}
    try:
        user_info_response = requests.get(kakao_user_info_api_uri, headers=headers, timeout=5)
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
    except requests.exceptions.Timeout:
        # ...
        return 408, ErrorDetail(detail="카카오 사용자 정보 조회 중 시간 초과가 발생했습니다.")
    except requests.exceptions.RequestException as e:
        # ...
        return 400, ErrorDetail(detail="카카오 사용자 정보를 가져오는데 실패했습니다.")

    # --- 카카오 사용자 정보 파싱 ---
    user_id_from_kakao = str(user_info.get("id")) # CustomUser의 id 필드 (USERNAME_FIELD)
    if not user_id_from_kakao:
        return 400, ErrorDetail(detail="카카오 사용자 ID를 확인할 수 없습니다.")

    kakao_account = user_info.get("kakao_account", {})
    
    # 카카오 응답에서 'email' 키가 있는지 확인 후 가져오기
    email = kakao_account.get('email') if kakao_account.get("has_email") and not kakao_account.get("email_needs_agreement", True) else None
    
    profile_data = kakao_account.get("profile", {})
    # 카카오 응답에서 'nickname' 키가 있는지 확인 후 가져오기
    nickname_from_kakao = profile_data.get('nickname') if not kakao_account.get("profile_needs_agreement", True) else None
    
    # 카카오 응답에서 'profile_image_url' 키가 있는지 확인 후 가져오기
    profile_image_url_from_kakao = profile_data.get('profile_image_url') if not kakao_account.get("profile_needs_agreement", True) else None

    # CustomUserManager.create_user는 nickname을 필수로 요구함
    if not nickname_from_kakao:
        pass


    # --- 사용자 식별 및 생성/업데이트 ---
    try:
        user = CustomUser.objects.get(id=user_id_from_kakao) # USERNAME_FIELD인 id로 조회
        
        # 기존 사용자 정보 업데이트
        fields_to_update = []
        if email is not None and user.email != email: # email 필드가 있고, 카카오 이메일과 다를 경우
            user.email = email
            fields_to_update.append('email')
        
        if nickname_from_kakao and user.nickname != nickname_from_kakao: # nickname 필드가 있고, 카카오 닉네임과 다를 경우
            user.nickname = nickname_from_kakao
            fields_to_update.append('nickname')
        
        if profile_image_url_from_kakao and user.profile_image_url != profile_image_url_from_kakao:
            user.profile_image_url = profile_image_url_from_kakao
            fields_to_update.append('profile_image_url')
        
        if not user.is_active:
            user.is_active = True
            fields_to_update.append('is_active')
        
        if fields_to_update:
            user.save(update_fields=fields_to_update)

    except CustomUser.DoesNotExist:
        if email and CustomUser.objects.filter(email=email).exists():
            return 400, ErrorDetail(detail=f"이미 해당 이메일({email})로 가입된 계정이 존재합니다.")

        # UserManager의 create_user는 nickname을 필수로 요구
        if not nickname_from_kakao:
            return 400, ErrorDetail(detail="카카오 프로필에서 닉네임 정보를 가져올 수 없습니다. (닉네임 필수)")


        try:
            user = CustomUser.objects.create_user(
                id=user_id_from_kakao,          # USERNAME_FIELD 값
                nickname=nickname_from_kakao,   # 필수 인자
                password=None,                  # 소셜 로그인이므로 비밀번호 없음
                email=email,                    # extra_fields로 전달
                profile_image_url=profile_image_url_from_kakao, # extra_fields로 전달
            )
        except ValueError as ve: # UserManager에서 발생시킨 ValueError (예: nickname 누락)
             print(f"사용자 생성 중 ValueError: {ve}")
             return 400, ErrorDetail(detail=str(ve)) # UserManager의 에러 메시지 그대로 전달
        except Exception as e:
            print(f"사용자 생성 오류: {type(e).__name__} - {e}")
            return 500, ErrorDetail(detail=f"사용자 계정 생성 중 오류가 발생했습니다.")

    if not user.is_active:
        return 403, ErrorDetail(detail="사용자 계정이 비활성화 상태입니다.")

    refresh = RefreshToken.for_user(user)
    return TokenObtainPairOutput(
        refresh=str(refresh),
        access=str(refresh.access_token),
    )


# --- 사용자 정보 관련 엔드포인트 ---
@user_router.get("/me", response={200: UserOut, codes_4xx: ErrorDetail, codes_5xx: ErrorDetail}, auth=JWTAuth())
def me(request: HttpRequest):
    user: CustomUser = request.user
    # UserOut 스키마의 userId가 CustomUser의 어떤 필드를 참조하는지 확인 필요 (현재 id를 USERNAME_FIELD로 사용)
    return UserOut(
        userId=user.id, # USERNAME_FIELD인 id를 사용
        nickname=user.nickname,
        name=getattr(user, 'name', None),
        email=user.email,
        level=str(getattr(user, 'level', "1")), # level 필드가 숫자면 str로 변환, 문자열이면 그대로
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )

@user_router.patch("/me", response={200: UserOut, codes_4xx: ErrorDetail, codes_5xx: ErrorDetail}, auth=JWTAuth())
def update_me(request: HttpRequest, data: UpdateUserIn):
    # ... (이전과 동일, UserOut 스키마 userId 필드 확인)
    user: CustomUser = request.user
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    try:
        user.save()
    except Exception as e:
        print(f"사용자 정보 업데이트 오류: {e}")
        return 400, ErrorDetail(detail="사용자 정보 업데이트 중 오류가 발생했습니다.")
    return UserOut(
        userId=user.id,
        nickname=user.nickname,
        name=getattr(user, 'name', None),
        email=user.email,
        level=str(getattr(user, 'level', "1")),
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )

@user_router.delete("/me", response={200: Dict[str, str], codes_4xx: ErrorDetail, codes_5xx: ErrorDetail}, auth=JWTAuth())
def delete_me(request: HttpRequest):
    user: CustomUser = request.user
    try:
        user.delete()
    except Exception as e:
        print(f"사용자 계정 삭제 오류: {e}")
        return 500, ErrorDetail(detail="사용자 계정 삭제 중 오류가 발생했습니다.")
    return {"detail": "User account successfully deleted."}


@user_router.delete("/me", response={200: Dict[str, str], codes_4xx: ErrorDetail}, auth=JWTAuth())
def delete_me(request: HttpRequest):
    user: CustomUser = request.user
    try:
        # user.is_active = False # 비활성화 처리
        # user.save()
        user.delete() # 실제 삭제
    except Exception as e:
        print(f"사용자 계정 삭제 오류: {e}")
        return 500, ErrorDetail(detail="사용자 계정 삭제 중 오류가 발생했습니다.")
    return {"detail": "User account successfully deleted."} # 204 No Content를 선호하면 빈 응답 반환


from courses.models import FavoriteCourse
from courses.schemas import CourseOut, SiteSchema 

@user_router.get("/me/favorites", response={200: List[CourseOut], codes_4xx: ErrorDetail}, auth=JWTAuth())
def get_favorite_courses(
    request, limit: Optional[int] = Query(None, description="가져올 최대 찜 코스 수")
):
    user: CustomUser = request.user
    favs = (
        FavoriteCourse.objects.filter(user=user)
        .select_related("course")
        .order_by("-created_at")
    )
    if limit is not None and limit > 0:
        favs = favs[:limit]

    result = []
    for fav in favs:
        c = fav.course
        result.append(
            CourseOut(
                id=c.id,
                name=c.name,
                description=getattr(c, 'description', None),
            )
        )
    return result


from .models import UserVisitedRegion

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