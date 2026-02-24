# Railway 배포 가이드

이 가이드는 ForLabsEX 암호화폐 거래소를 Railway에 배포하는 방법을 설명합니다.

## 사전 준비

- Railway 계정 (https://railway.app - GitHub 계정으로 로그인)
- GitHub 리포지토리 접근 권한

## 배포 단계

### 1단계: Railway 프로젝트 생성

1. https://railway.app 접속 및 로그인
2. **New Project** 클릭
3. **Deploy from GitHub repo** 선택
4. `forlabsio/crypto-exchange` 리포지토리 선택

### 2단계: PostgreSQL 데이터베이스 추가

1. 프로젝트 대시보드에서 **New** 클릭
2. **Database** → **PostgreSQL** 선택
3. 자동으로 생성됨 (DATABASE_URL 환경변수가 자동 설정됨)

### 3단계: Redis 추가

1. 프로젝트 대시보드에서 **New** 클릭
2. **Database** → **Redis** 선택
3. 자동으로 생성됨 (REDIS_URL 환경변수가 자동 설정됨)

### 4단계: Backend 서비스 설정

Railway는 자동으로 `backend` 폴더를 감지하고 배포합니다.

#### Backend 환경변수 설정

Backend 서비스 → **Variables** 탭에서 다음 추가:

```
SECRET_KEY=your-secret-key-here-generate-random-string
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

**중요**: `SECRET_KEY`는 강력한 랜덤 문자열로 설정하세요.

생성 방법:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Backend 배포 확인

- `railway.toml` 파일이 이미 설정되어 있어 자동으로 배포됩니다
- 시작 명령: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health` 엔드포인트

### 5단계: Frontend 서비스 설정

1. 프로젝트 대시보드에서 **New** 클릭
2. **GitHub Repo** → 같은 리포지토리 선택
3. **Root Directory**를 `frontend`로 설정

#### Frontend 환경변수 설정

Frontend 서비스 → **Variables** 탭:

```
NEXT_PUBLIC_API_URL=https://your-backend-service.railway.app
```

**중요**: Backend 배포 후 생성된 URL을 여기에 입력하세요.

Backend URL 찾기:
- Backend 서비스 → **Settings** → **Domains** → **Generate Domain**

### 6단계: 배포 확인

1. **Backend 상태 확인**
   - Backend 서비스 → **Deployments** 탭에서 배포 로그 확인
   - 성공 메시지: `Application startup complete`
   - Health check 통과 확인

2. **Frontend 상태 확인**
   - Frontend 서비스 → **Deployments** 탭에서 빌드 로그 확인
   - 성공 메시지: `Build successful`

3. **서비스 접속**
   - Frontend 서비스 → **Settings** → **Domains** → **Generate Domain**
   - 생성된 URL로 접속하여 서비스 확인

## 초기 설정

### 관리자 계정 생성

1. Frontend에서 회원가입 (일반 유저로 생성됨)
2. PostgreSQL에 직접 접속하여 권한 변경:

```sql
-- Railway 대시보드 → PostgreSQL 서비스 → Data 탭에서 실행
UPDATE users SET role = 'admin' WHERE email = 'your-email@example.com';
```

3. 관리자 로그인 후 `/admin/bots`에서 봇 생성

### 테스트 자금 지급 (선택)

```sql
-- 특정 유저에게 추가 USDT 지급
UPDATE wallets
SET balance = balance + 10000
WHERE user_id = (SELECT id FROM users WHERE email = 'test@example.com')
AND asset = 'USDT';
```

## 문제 해결

### Backend 배포 실패

**증상**: 빌드는 성공하지만 Health check 실패

**해결**:
1. Backend 로그에서 에러 확인
2. 환경변수가 올바르게 설정되었는지 확인
3. PostgreSQL 연결 확인:
   ```
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   ```

### Frontend에서 API 연결 실패

**증상**: CORS 에러 또는 API 호출 실패

**해결**:
1. `NEXT_PUBLIC_API_URL`이 올바른 Backend URL인지 확인
2. Backend의 CORS 설정 확인 (`app/main.py`의 `allow_origins`)
3. Frontend를 재배포 (환경변수 변경 후)

### WebSocket 연결 실패

**증상**: 실시간 시세 업데이트 안 됨

**해결**:
1. Railway는 WebSocket을 지원하므로 별도 설정 불필요
2. Backend 로그에서 Binance WebSocket 연결 확인
3. Redis 연결 상태 확인

### Redis 연결 실패

**해결**:
1. Redis 서비스가 정상 실행 중인지 확인
2. `REDIS_URL` 환경변수 확인
3. Backend 재시작

## 비용 관리

Railway 무료 티어:
- $5/월 무료 크레딧 제공
- 사용량 초과 시 자동 정지 (과금 방지)

예상 사용량:
- Backend: ~$5-10/월
- Frontend: ~$0-5/월 (트래픽에 따라)
- PostgreSQL: ~$5/월
- Redis: ~$5/월

**총 예상 비용**: $15-25/월

## 모니터링

Railway 대시보드에서 실시간 모니터링:
- CPU, 메모리 사용량
- 배포 로그
- 에러 로그
- 데이터베이스 크기

## 자동 배포 설정

GitHub에 푸시하면 자동으로 Railway에 배포됩니다:

```bash
cd /Users/peterchae/crypto-exchange
git add .
git commit -m "Update configuration"
git push origin main
```

Railway가 자동으로 감지하고 재배포합니다.

## 추가 최적화

### 1. Custom Domain 설정
Railway에서 제공하는 도메인 대신 자신의 도메인 사용 가능

### 2. 환경별 분리
Production/Staging 환경 분리 권장

### 3. 모니터링 도구
- Sentry (에러 추적)
- LogTail (로그 관리)

## 참고 링크

- Railway 공식 문서: https://docs.railway.app
- FastAPI 배포 가이드: https://fastapi.tiangolo.com/deployment/
- Next.js 배포 가이드: https://nextjs.org/docs/deployment
