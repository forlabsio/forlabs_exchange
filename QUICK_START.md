# 🚀 ForLabsEX 빠른 시작 가이드

## 현재 상황

✅ **자동 완료된 작업**
- Railway 프로젝트 생성
- PostgreSQL + Redis 추가
- Backend 배포 시작
- 환경변수 모두 설정

🔄 **배포 진행 중**
- Backend 애플리케이션 빌드 및 배포 중

## ⚡ 지금 바로 시작하기

### 1️⃣ Railway 대시보드 열기

👉 https://railway.com/project/578ec388-a37c-4f30-95b0-518e88024894

### 2️⃣ Backend 배포 확인

1. **"Postgres" 서비스** 클릭 (실제로는 Backend 애플리케이션)
2. **Deployments** 탭에서 최신 배포 확인
3. 상태가 **"Success"** 가 되면 완료! ✅
4. **Settings** → **Networking** → **Generate Domain** (도메인이 없다면)

### 3️⃣ Backend URL 확인

배포 완료 후:
- Settings → Networking에서 생성된 도메인 복사
- 예: `https://backend-production-xxxx.up.railway.app`

### 4️⃣ Frontend 서비스 추가

1. 프로젝트 대시보드로 돌아가기
2. 우측 상단 **"+ New"** 클릭
3. **"GitHub Repo"** 선택
4. `forlabsio/crypto-exchange` 리포지토리 선택
5. **"Add Service"** 클릭

### 5️⃣ Frontend 설정

새로 생성된 서비스에서:

**A. Root Directory 설정**
- **Settings** 탭
- **Source** 섹션
- **Root Directory**: `frontend` 입력
- **Save Changes**

**B. 환경변수 설정**
- **Variables** 탭
- **New Variable** 클릭
- **Variable Reference**:
  ```
  NEXT_PUBLIC_API_URL
  ```
- **Value**: Backend URL 붙여넣기 (Step 3에서 복사한 URL)
- **Add** 클릭

**C. 도메인 생성**
- **Settings** → **Networking**
- **Generate Domain** 클릭
- 생성된 URL 복사

### 6️⃣ 서비스 접속

Frontend URL로 접속하여:
1. 회원가입
2. 초기 자금 10,000 USDT 자동 지급 확인
3. `/exchange/BTC_USDT`에서 실시간 거래 테스트!

## 🎯 빠른 체크리스트

- [ ] Backend 배포 완료 확인 (Deployments 탭에서 "Success")
- [ ] Backend 도메인 생성
- [ ] Frontend 서비스 추가
- [ ] Frontend Root Directory = `frontend`
- [ ] Frontend 환경변수 = `NEXT_PUBLIC_API_URL=<Backend URL>`
- [ ] Frontend 도메인 생성
- [ ] Frontend URL로 접속하여 회원가입 테스트

## 👑 관리자 설정 (선택사항)

봇을 생성하려면:

1. Railway → **Postgres** 서비스 → **Data** 탭
2. SQL 실행:
   ```sql
   UPDATE users SET role = 'admin'
   WHERE email = 'your-email@example.com';
   ```
3. 로그아웃 → 재로그인
4. `/admin/bots`에서 봇 생성!

## 🐛 문제 해결

### Backend 502 에러
- Deployments 탭에서 로그 확인
- 환경변수 재확인: DATABASE_URL, REDIS_URL, SECRET_KEY
- 재배포: Deployments → 최신 배포 → **"Redeploy"**

### Frontend 빌드 실패
- Root Directory가 정확히 `frontend`인지 확인
- 환경변수에 Backend URL이 올바른지 확인
- Logs 탭에서 상세 에러 확인

### CORS 에러
- Backend URL이 Frontend 환경변수에 올바르게 설정되었는지 확인
- Backend 재배포 시도

## 💰 비용 안내

- 무료 $5 크레딧으로 시작
- 예상 월 비용: $15-25
- 무료 크레딧 소진 시 자동 정지 (과금 방지)

## 🔗 참고 문서

- [상세 배포 가이드](RAILWAY_DEPLOYMENT.md)
- [배포 상태](DEPLOYMENT_STATUS.md)
- [최종 단계](FINAL_STEPS.md)
- [개발 문서](DEVELOPMENT.md)

---

**문제가 있으면 언제든 질문하세요!** 😊
