# Railway 배포 진행 상황

## ✅ 완료된 작업

1. **Railway CLI 설치** ✓
2. **Railway 로그인** ✓ (peter@forlabs.io)
3. **프로젝트 생성** ✓
   - 프로젝트 이름: `welcoming-wonder`
   - 프로젝트 ID: `578ec388-a37c-4f30-95b0-518e88024894`
   - URL: https://railway.com/project/578ec388-a37c-4f30-95b0-518e88024894

4. **PostgreSQL 추가** ✓
5. **Redis 추가** ✓
6. **Backend 환경변수 설정** ✓
   - SECRET_KEY: `vV3Tn4lpwE6UkvH3RMC-402paclLSGqnqoqJP_SXx4Q`
   - DATABASE_URL: 자동 설정됨
   - REDIS_URL: 자동 설정됨

7. **Backend 배포 시작** ✓
   - 빌드 진행 중

## 🔄 남은 작업 (웹에서 완료)

Railway CLI의 제한으로 인해 나머지 작업은 **Railway 웹 대시보드**에서 완료하는 것이 더 쉽습니다.

### 1단계: Backend 배포 확인 및 도메인 생성

1. 프로젝트 대시보드 열기: https://railway.com/project/578ec388-a37c-4f30-95b0-518e88024894
2. Backend 서비스 클릭 (이름: `backend` 또는 자동 생성된 이름)
3. **Settings** 탭 → **Networking** 섹션
4. **Generate Domain** 클릭
5. 생성된 URL 복사 (예: `https://backend-production-xxxx.up.railway.app`)

### 2단계: Frontend 서비스 추가

1. 프로젝트 대시보드에서 **New** 클릭
2. **GitHub Repo** 선택
3. 같은 리포지토리 `forlabsio/crypto-exchange` 선택
4. **Settings** → **Source** → **Root Directory** 를 `frontend`로 변경
5. **Save** 클릭

### 3단계: Frontend 환경변수 설정

1. Frontend 서비스 → **Variables** 탭
2. 다음 변수 추가:
   ```
   NEXT_PUBLIC_API_URL=<Backend URL from Step 1>
   ```
   예: `NEXT_PUBLIC_API_URL=https://backend-production-xxxx.up.railway.app`
3. **Save** 클릭
4. 자동으로 재배포됨

### 4단계: Frontend 도메인 생성

1. Frontend 서비스 → **Settings** → **Networking**
2. **Generate Domain** 클릭
3. 생성된 URL로 서비스 접속
   예: `https://frontend-production-xxxx.up.railway.app`

### 5단계: Backend CORS 설정 확인

Backend가 배포된 후, Frontend에서 API 호출이 실패하면:

1. Backend 서비스 → **Variables** 탭
2. 다음 변수 추가:
   ```
   FRONTEND_URL=<Frontend URL from Step 4>
   ```
3. `backend/app/main.py` 파일에서 CORS 설정 확인:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["*"],  # 또는 Frontend URL 지정
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

## 🎯 최종 확인 사항

배포 완료 후 다음을 확인하세요:

1. **Backend 상태**
   - Deployments 탭에서 "Success" 확인
   - Logs에서 에러 없는지 확인
   - Health check 통과 확인

2. **Frontend 상태**
   - Deployments 탭에서 "Success" 확인
   - 생성된 URL로 접속하여 정상 작동 확인

3. **데이터베이스 초기화**
   - Backend가 시작되면 자동으로 `alembic upgrade head` 실행됨
   - PostgreSQL 테이블이 생성됨

4. **관리자 계정 생성**
   - Frontend에서 회원가입
   - PostgreSQL Data 탭에서 SQL 실행:
     ```sql
     UPDATE users SET role = 'admin' WHERE email = 'your-email@example.com';
     ```

## 📊 예상 비용

- Backend: ~$5-10/월
- Frontend: ~$0-5/월
- PostgreSQL: ~$5/월
- Redis: ~$5/월

**총 예상 비용**: $15-25/월 (무료 $5 크레딧 포함)

## 🔗 유용한 링크

- 프로젝트 대시보드: https://railway.com/project/578ec388-a37c-4f30-95b0-518e88024894
- Railway 문서: https://docs.railway.app
- 배포 가이드: [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md)

## 🆘 문제 해결

### Backend 배포 실패
- Logs 탭에서 에러 확인
- 환경변수 재확인 (DATABASE_URL, REDIS_URL, SECRET_KEY)

### Frontend 빌드 실패
- Root Directory가 `frontend`로 설정되었는지 확인
- Build Command: 기본값 사용 (Next.js 자동 감지)
- Start Command: 기본값 사용 (`npm start`)

### WebSocket 연결 실패
- Backend 로그에서 Binance WebSocket 연결 확인
- Redis 연결 상태 확인

### CORS 에러
- Backend의 CORS 설정 확인
- Frontend URL이 허용 목록에 있는지 확인
