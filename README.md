# 여기다 백엔드

### 초기 세팅

```
git clone https://github.com/likelion-team-five/yeogida-backend
cd yeogida-backend
poetry install
poetry run pre-commit install
poetry run python manage.py runserver
```

### 주의사항

python 명령어를 실행시키기 전에 반드시

```
poetry run
```

을 앞에 붙이고 실행하셔야 합니다.

### commit 방법

```
pre-commit install
git add .
git commit -m "커밋할 메세지 내용, 상세하게"
git push origin main
```
