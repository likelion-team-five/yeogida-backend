from typing import List, Optional, Union, Dict, Any

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from ninja import Query, Router, Schema
from ninja.responses import codes_4xx
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.tokens import RefreshToken


from .models import CustomUser
from .schemas import TokenObtainPairOutput, UpdateUserIn, UserOut


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
    """
    카카오 로그인 프로세스를 시작합니다.
    사용자를 카카오 인가 코드 요청 URL로 리다이렉트합니다.
    """
    kakao_auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?response_type=code"
        f"&client_id={settings.KAKAO_REST_API_KEY}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
    )
    return redirect(kakao_auth_url)


@auth_router.get("/kakao/callback/")
def kakao_callback(request: HttpRequest, code: str = Query(...)):
    """
    카카오 서버로부터 인가 코드를 받아 프론트엔드로 전달합니다.
    프론트엔드는 이 코드를 사용하여 백엔드의 토큰 발급 API를 호출합니다.
    """
    redirect_url_to_frontend = f"{settings.FRONTEND_LOGIN_SUCCESS_URI}?code={code}"
    return redirect(redirect_url_to_frontend)


@auth_router.post(
    "/kakao/login/process",
    response={200: TokenObtainPairOutput, codes_4xx: ErrorDetail},
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
    # Client Secret을 사용하는 경우 (카카오는 필수는 아님)
    # if getattr(settings, 'KAKAO_CLIENT_SECRET', None):
    #     request_data["client_secret"] = settings.KAKAO_CLIENT_SECRET

    try:
        token_response = requests.post(kakao_token_api_uri, data=request_data, timeout=10)
        token_response.raise_for_status() # HTTP 에러 발생 시 예외 발생
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
            except ValueError: # JSON 디코딩 실패 시
                error_message = f"카카오 인증 실패: 응답을 해석할 수 없습니다. Status: {e.response.status_code}, Body: {e.response.text[:200]}"
        else:
            error_message = f"{error_message} 오류: {str(e)}"
        
        print(f"DEBUG: {error_message}")
        return status_code_to_return if status_code_to_return < 500 else 400, ErrorDetail(detail=error_message)

    kakao_access_token = kakao_tokens.get("access_token")
    if not kakao_access_token:
        return 400, ErrorDetail(detail="카카오로부터 액세스 토큰을 받지 못했습니다.")

    # 카카오 사용자 정보 요청
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
        # 이미 발급받은 카카오 토큰을 만료시키는 것이 좋을 수 있습니다. (선택 사항)
        # requests.post("https://kapi.kakao.com/v1/user/unlink", headers={"Authorization": f"Bearer {kakao_access_token}"})
        return 408, ErrorDetail(detail="카카오 사용자 정보 조회 중 시간 초과가 발생했습니다.")
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: 카카오 사용자 정보 요청 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"DEBUG: 카카오 사용자 정보 요청 응답 내용: {e.response.text}")
        return 400, ErrorDetail(detail="카카오 사용자 정보를 가져오는데 실패했습니다.")

    # --- 카카오 사용자 정보 파싱 ---
    kakao_id = str(user_info.get("id"))
    if not kakao_id: # 카카오 ID는 필수
        return 400, ErrorDetail(detail="카카오 사용자 ID를 확인할 수 없습니다.")

    kakao_account = user_info.get("kakao_account", {})
    
    email = None
    # 사용자가 이메일 제공에 동의했고, 카카오 계정에 이메일이 실제로 있는 경우
    if kakao_account.get("has_email") and not kakao_account.get("email_needs_agreement", True): # email_needs_agreement가 False여야 동의한 것
        email = kakao_account.get("email")

    profile_data = kakao_account.get("profile", {})
    nickname = None
    profile_image_url = None
    # 사용자가 프로필 정보 제공에 동의한 경우
    if not kakao_account.get("profile_needs_agreement", True): # profile_needs_agreement가 False여야 동의한 것
        nickname = profile_data.get("nickname")
        profile_image_url = profile_data.get("profile_image_url") # 썸네일 대신 일반 프로필 이미지

    # --- 사용자 식별 및 생성/업데이트 ---
    try:
        user = CustomUser.objects.get(kakao_id=kakao_id)
        # 기존 사용자 정보 업데이트
        fields_to_update = []
        if email and user.email != email:
            # 이메일 변경 시, 해당 이메일이 다른 계정에서 사용 중인지 확인하는 로직 추가 가능
            # if CustomUser.objects.filter(email=email).exclude(pk=user.pk).exists():
            #     return 400, ErrorDetail(detail="해당 이메일은 이미 다른 계정에서 사용 중입니다.")
            user.email = email
            fields_to_update.append('email')
        
        # 닉네임은 카카오 닉네임으로 덮어쓸지, 기존 닉네임 유지할지 정책 필요
        # 여기서는 카카오 닉네임으로 업데이트 (값이 있는 경우)
        if nickname and user.nickname != nickname:
            user.nickname = nickname
            fields_to_update.append('nickname')
        
        if profile_image_url and user.profile_image_url != profile_image_url:
            user.profile_image_url = profile_image_url
            fields_to_update.append('profile_image_url')
        
        if not user.is_active:
            user.is_active = True
            fields_to_update.append('is_active')
        
        if fields_to_update:
            user.save(update_fields=fields_to_update)

    except CustomUser.DoesNotExist:
        # 새 사용자 생성
        generated_username = f"kakao_{kakao_id}" # 고유 username 생성 (정책에 따라 변경 가능)
        
        # username 중복 시 처리 (간단한 예시, 실제로는 더 견고하게)
        # _username = generated_username
        # count = 1
        # while CustomUser.objects.filter(username=_username).exists():
        #     _username = f"{generated_username}_{count}"
        #     count += 1
        # generated_username = _username
            
        # 이메일 중복 체크 (카카오에서 이메일을 받았고, 해당 이메일로 이미 가입된 사용자가 있는지)
        if email and CustomUser.objects.filter(email=email).exists():
            return 400, ErrorDetail(detail=f"이미 해당 이메일({email})로 가입된 계정이 존재합니다. 다른 방법으로 로그인해주세요.")

        try:
            # CustomUser 모델의 create_user 메소드가 아래 인자들을 처리할 수 있도록 구현되어야 함
            user = CustomUser.objects.create_user(
                username=generated_username,
                email=email, # 모델에서 null=True 허용 필요
                nickname=nickname, # 모델에서 null=True 허용 필요
                profile_image_url=profile_image_url, # 모델에서 null=True 허용 필요
                kakao_id=kakao_id,
                # name 필드가 있다면, name=nickname 또는 다른 값으로 설정
                # password는 소셜 로그인 시 보통 None 또는 사용 불가능한 값으로 설정됨
            )
            # user.set_unusable_password() # create_user 내에서 처리될 수도 있음
            # user.save() # create_user 내에서 save가 호출됨
        except Exception as e: # IntegrityError 등 다양한 예외 처리
            print(f"사용자 생성 오류: {type(e).__name__} - {e}")
            return 500, ErrorDetail(detail=f"사용자 계정 생성 중 오류가 발생했습니다.")

    if not user.is_active: # 혹시 모를 비활성 상태 체크
        return 403, ErrorDetail(detail="사용자 계정이 비활성화 상태입니다.")

    # JWT 토큰 발급
    refresh = RefreshToken.for_user(user)
    return TokenObtainPairOutput(
        refresh=str(refresh),
        access=str(refresh.access_token),
    )


# --- 사용자 정보 관련 엔드포인트 ---

@user_router.get("/me", response={200: UserOut, codes_4xx: ErrorDetail}, auth=JWTAuth())
def me(request: HttpRequest):
    user: CustomUser = request.user
    # UserOut 스키마에 정의된 필드에 맞춰서 반환
    return UserOut(
        userId=user.username, # 또는 user.id, UserOut 스키마 정의에 따름
        nickname=user.nickname,
        name=getattr(user, 'name', None), # CustomUser 모델에 name 필드가 있다면
        email=user.email,
        level=getattr(user, 'level', None), # CustomUser 모델에 level 필드가 있다면
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )


@user_router.patch("/me", response={200: UserOut, codes_4xx: ErrorDetail}, auth=JWTAuth())
def update_me(request: HttpRequest, data: UpdateUserIn):
    user: CustomUser = request.user
    update_data = data.model_dump(exclude_unset=True) # Pydantic v2 방식
    
    # 닉네임 중복 검사 등 유효성 검사 추가 가능
    # if 'nickname' in update_data and CustomUser.objects.filter(nickname=update_data['nickname']).exclude(pk=user.pk).exists():
    #     return 400, ErrorDetail(detail="이미 사용 중인 닉네임입니다.")

    for key, value in update_data.items():
        setattr(user, key, value)
    
    try:
        user.save()
    except Exception as e: # 저장 중 발생할 수 있는 오류 (e.g., DB 제약조건 위반)
        print(f"사용자 정보 업데이트 오류: {e}")
        return 400, ErrorDetail(detail="사용자 정보 업데이트 중 오류가 발생했습니다.")
        
    return UserOut(
        userId=user.username,
        nickname=user.nickname,
        name=getattr(user, 'name', None),
        email=user.email,
        level=getattr(user, 'level', None),
        profileImage=user.profile_image_url,
        is_active=user.is_active,
    )


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