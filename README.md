# OM Research Radar

매일 아침 sustainable operations, ESG, supply chain resilience, energy/AI 데이터센터, circular economy 관련 뉴스 5개를 골라 **연구 관점(OM angle, 연구 질문, 데이터와 식별 전략)**을 붙여 Gmail로 보내주는 개인 뉴스레터입니다. 월요일에는 MS, M&SOM, POM, JOM 최신 논문도 함께 받습니다.

## 작동 방식

```
RSS 14곳 + Google News 검색 10개 + Crossref(학술지)
        │  최근 36시간, 이미 보낸 기사는 제외 (하루 약 200개 후보)
        ▼
① Claude: 후보 중 5개 선정 (주제 분산, 같은 사건 중복 제거)
② Claude + 웹 검색: 원문을 찾아 사실 확인 후 리서치 노트 작성
③ Claude: 노트만 근거로 뉴스레터 작성 (구조화된 JSON)
        ▼
Gmail 발송 → data/에 아카이브 커밋 (archive.csv, issues/날짜.html)
```

## 설정 (처음 한 번)

### 1. Anthropic API 키
- https://console.anthropic.com 에서 가입 → Billing에서 크레딧 충전 → API Keys에서 키 발급
- Claude Pro/Max 구독과 별개인 종량제 결제입니다.
- 예상 비용은 하루 몇십 센트 수준(월 $10~20 정도 추정)입니다. 처음 며칠 동안 콘솔의 Usage에서 실제 금액을 확인해 주세요. 줄이고 싶으면 `config.yaml`에서 `effort: low`로 바꾸거나 검색 횟수를 줄이면 됩니다.

### 2. Gmail 앱 비밀번호
- Google 계정에 2단계 인증이 켜져 있어야 합니다.
- https://myaccount.google.com/apppasswords 에서 앱 비밀번호(16자리)를 만드세요. 평소 쓰는 Gmail 비밀번호가 아니라 이 앱 비밀번호를 사용합니다.

### 3. 로컬에서 테스트
```bash
cd ~/Desktop/Research/om-news-digest
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
cp .env.example .env        # .env를 열어 값 채우기
./.venv/bin/python run.py --candidates-only   # 후보만 확인 (무료)
./.venv/bin/python run.py --dry-run --papers  # 메일 없이 output/preview.html 생성
./.venv/bin/python run.py                     # 실제 발송
```

### 4. GitHub Actions로 매일 자동 실행
1. 이 폴더를 **private** GitHub 저장소로 올립니다.
2. 저장소 Settings → Secrets and variables → Actions에서 다음 4개를 등록합니다:
   `ANTHROPIC_API_KEY`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `DIGEST_RECIPIENT`(받을 주소, 비우면 본인)
3. Actions 탭 → "Daily digest" → **Run workflow**로 한 번 실행해 봅니다.
4. 이후에는 매일 10:30 UTC(미 동부 오전 6:30, 겨울엔 5:30)에 자동으로 실행됩니다. 시간은 `.github/workflows/daily.yml`의 cron에서 바꿀 수 있습니다.

## 커스터마이즈 (`config.yaml`)
- `research_profile`: Claude가 기사를 고르는 기준입니다. 관심사가 바뀌면 여기를 고치세요.
- `google_news_queries`, `rss_feeds`: 뉴스 소스
- `num_news`, `academic_weekdays`: 개수와 학술 섹션 요일

## 주요 기능
- **매일 메일** (06:30 ET): 주요 기사 5개 + 기사별 관련 논문 + Also worth noting + 새 논문. 제목에 날짜가 들어갑니다.
- **후속 기사 연결**: 예전에 다룬 사건의 후속이면 "↳ Follow-up to ..."로 이전 기사와 연결되고, 아카이브 *Story threads* 탭에서 타임라인으로 묶입니다.
- **데이터셋 모음**: 기사마다 제안된 데이터 소스가 아카이브 *Datasets* 탭에 데이터셋별로 쌓입니다.
- **★ 별표**: 아카이브에서 ☆를 누르면 바로 별표, ★를 누르면 해제됩니다. 브라우저마다 처음 한 번 GitHub 토큰(이 저장소의 Issues 읽기/쓰기만 허용)을 연결해야 하며, 토큰은 그 브라우저에만 저장됩니다. 메일의 ☆ Star 링크는 아카이브를 열어 별표를 답니다. ★ Starred 탭에서 메모를 달 수 있고, 별표와 메모는 다음 날부터 기사 선정과 주간 리뷰에 반영됩니다.
- **필터**: 테마는 하나, 키워드는 여러 개 고를 수 있습니다(모두 포함한 기사만 표시). 고를 때마다 남은 기사에 있는 테마와 키워드만 보입니다.
- **주간 리뷰** (일요일 09:00 ET): 한 주 기사를 다시 읽고 패턴, 진행 중인 이야기, 더 구체화한 연구 아이디어 2~3개를 보내줍니다. `python run_weekly.py --dry-run`으로 미리 볼 수 있습니다.
- **실패 알림**: 매일/주간 실행이 실패하면 "⚠️ ... failed" 메일이 로그 링크와 함께 옵니다. Gmail 설정 자체가 문제라 알림 메일도 못 보내는 경우에는 GitHub가 계정 이메일로 실패 알림을 보냅니다.

## 아카이브 활용
- **아카이브 사이트 (`docs/index.html`)**: 매일 실행할 때 자동으로 다시 만들어집니다.
  - 날짜별 타임라인으로 지난 이슈를 볼 수 있습니다.
  - 테마나 키워드 태그를 누르면 해당 기사 목록이 나오고, 제목을 누르면 그 뉴스레터의 해당 기사로 이동합니다.
  - 검색창에서 제목, 요약, 연구 질문을 검색할 수 있습니다.
  - 키워드는 기존 태그를 재사용하도록 Claude에게 지시해 두어서, 쌓일수록 같은 태그로 모입니다.
  - 로컬에서 보려면: `./.venv/bin/python -m http.server -d docs 8000` 실행 후 http://localhost:8000
  - 수동으로 다시 만들려면: `./.venv/bin/python -m digest.archive`
- `data/archive.csv`: 지금까지 받은 모든 기사, 연구 질문, 키워드가 누적됩니다. 엑셀이나 pandas로 분석할 때 쓰세요.
- `data/issues/`: 날짜별 뉴스레터 원본(HTML, JSON)
