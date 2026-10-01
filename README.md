# 한반도 긴장도 지수

뉴스 헤드라인을 실시간 집계해 0~100 정보 밀도 지수로 압축하고, 안보 신호를 자동 분류해 보여주는 대시보드.

> 이 지수는 위협 평가·예측 도구가 아닙니다. 헤드라인에서 어떤 단어가 얼마나 나왔는지를 집계한 값입니다.

## 로컬 실행

```bash
python server.py          # http://localhost:8848
python weekly.py          # 주간 회고 즉시 생성
```

의존성 없음 (표준 라이브러리만 사용). Python 3.11+.

## 구조

| 파일 | 역할 |
|---|---|
| `server.py` | RSS 수집 · 지수 계산 · HTTP 서버 · 자동 주간회고(30분) |
| `weekly.py` | 7일치 헤드라인을 신호별로 묶어 `weekly.html` 생성 |
| `index.html` | 대시보드 |
| `guides.html` | 실질 가이드 콘텐츠 (애드센스 원본 콘텐츠 요건) |
| `about/contact/privacy/terms.html` | 심사 필수 페이지 |
| `style.css` | 공통 스타일 |
| `sitemap.xml` (동적) · `robots.txt` | 검색엔진 제출용 |

## 데이터 출처

구글 뉴스 RSS 6종 + 연합뉴스 속보. 매체별 RSS는 대부분 404라 사용하지 않습니다.

- 수집·가중치 설계 노트는 스킬 `news-tension-dashboard` 참고

## 배포 (Render)

1. 저장소를 GitHub에 올립니다.
2. Render → New → Blueprint → 저장소 선택 (`render.yaml` 자동 인식).
3. `HOST=0.0.0.0` 이 설정되어 포트가 바인딩됩니다 (`PORT` 환경변수 사용).
4. 배포 후 `server.py` 의 `BASE_URL` 을 실제 도메인으로 변경하고, `robots.txt` 의 Sitemap 주소도 변경합니다.

Railway / Fly.io 도 동일하게 `python server.py` 로 동작합니다.

## 애드센스 신청 전 체크

- [ ] 도메인 연결 + HTTPS
- [ ] `BASE_URL`, `robots.txt` Sitemap 주소 실제 도메인으로 변경
- [ ] `contact.html` 의 placeholder 이메일 교체
- [ ] `privacy.html` 의 AdSense publisher ID 삽입, 실제 광고 스크립트 반영
- [ ] 콘텐츠 15개 이상 (현재 대시보드 1 + 가이드 1 + 주간회고 8종 = 충족)
- [ ] AdSense 계정 생성 → 사이트 추가 → 애드센스 코드 붙여넣기

광고 슬롯은 각 페이지의 `.ads` div 입니다.

## 주의

- 뉴스 제목은 인용하고 원문으로 링크합니다. 본문 복제하지 않습니다.
- 전쟁 예측·공포 조장 각도의 콘텐츠는 전자신문법 14조 및 애드센스 정책 위험이 있습니다. 이 사이트는 실데이터 요약에 한정합니다.