# 여기다 백엔드

### 초기 세팅

```
git clone https://github.com/likelion-team-five/yeogida-backend
cd yeogida-backend
poetry install
eval $(poetry env activate)
pre-commit install
python manage.py runserver
```

### commit 방법

```
pre-commit install
git add .
git commit -m "커밋할 메세지 내용, 상세하게"
git push origin main
```

커밋도중 Failed가 하나라도 발생했다면

```
git add .
git commit -m "커밋할 메세지 내용, 상세하게"
```

다시 실행하셔야 합니다.
