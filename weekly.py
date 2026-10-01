"""
주간 회고 생성기 — 최근 7일 안보 헤드라인을 집계해 weekly.html 을 만든다.
사용:  python weekly.py
서버 시작 시 30분마다 server.py 가 30분 주기로 자동 실행하도록 연결되어 있다.
"""
import html
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

import server

KST = server.KST

# 이벤트 라벨별 이번 주 요약 문장 (자체 텍스트 — 검색엔진이 요구하는 '원본 해석')
SUMMARY = {
    "미사일 발사": "미사일 발사 관련 보도가 가장 큰 변화를 만들었습니다. 발사 사실보다 사거리와 개수가 실제 신호로 읽힙니다.",
    "적 접근 / 비무장지대": "비무장지대와 접경지에서의 움직임이 이어졌습니다. 주민 불편과 관련한 보도도 함께 확인됩니다.",
    "포격·사격": "포격·사격 관련 표현이 등장했습니다. 실제 발사인지 훈련·유엔 연습인지 원문을 확인하는 것이 먼저입니다.",
    "안보회의 소집": "안보회의와 상황에 관한 소집이 있었습니다. 회의 결과보다 소집 자체가 신호라는 점을 유의할 만합니다.",
    "무인기 활동": "무인기·drone 관련 보도가 늘었다면 정보 유포를 자동으로 하지 말고 출처를 먼저 확인하세요.",
    "대체 국면": "대화와 협상 국면의 보도가 함께 확인됩니다. 긴장과 완화는 국면마다 함께 나타납니다.",
    "전쟁·출병 언급": "전쟁·출병을 직접 언급한 보도가 있었습니다. 전문·오피니언 기사인 경우가 많아 실제 행동과는 차이가 큽니다.",
    "지뢰 발견": "지뢰 관련 보도가 확인되었습니다. 민간인이 가장 먼저 위험에 노출되는 유형이라 주변 지역 확인이 유용합니다.",
    "시설 파괴": "시설 파괴 관련 보도가 있었습니다. 피해 규모보다 여파가 남는 기간이 중요합니다.",
}


def esc(s):
    return html.escape(s or "", quote=True)


def build():
    data = server.get_data(force=True)
    now = datetime.now(KST)
    week_ago = now - timedelta(days=7)
    items = [
        i
        for i in data["feed"]
        if i["ts"] and datetime.fromtimestamp(i["ts"], KST) >= week_ago
    ]

    # 이벤트 분류 재계산 (타임라인은 최근순 상한이 있으므로 전체 대상으로 다시 돌림)
    by_label = defaultdict(list)
    for it in items:
        for pat, label, emoji in server.EVENTS:
            if re.search(pat, it["title"]):
                by_label[label].append(it)
                break

    src_count = Counter(i["source"] for i in items)
    day_count = Counter(
        datetime.fromtimestamp(i["ts"], KST).strftime("%m/%d(%a)") for i in items
    )

    rows = []
    for label, lst in sorted(by_label.items(), key=lambda kv: -len(kv[1])):
        lst.sort(key=lambda x: -x["ts"])
        head = lst[:6]
        rows.append(
            f"""
    <div class="card">
      <h2>{esc(label)} <small>{len(lst)}건</small></h2>
      <p>{esc(SUMMARY.get(label, "해당 주의 관련 보도를 모았습니다. 원문에서 시점과 출처를 확인하세요."))}</p>
      <ul class="feed">{''.join(
          f'<li><a href="{esc(h["link"])}" target="_blank" rel="noopener">{esc(h["title"])}</a>'
          f'<div class="s">{esc(h["source"])} · '
          f'{datetime.fromtimestamp(h["ts"], KST).strftime("%m/%d %H:%M") if h["ts"] else ""}</div></li>'
          for h in head
      )}</ul>
      {f'<p class="dis">외 {len(lst)-len(head)}건 더 있음 — <a href="/">대시보드에서 전체 보기</a></p>' if len(lst) > len(head) else ''}
    </div>"""
        )

    top_src = " · ".join(f"{s} {c}건" for s, c in src_count.most_common(6))
    day_rows = "".join(
        f"<tr><td>{esc(d)}</td><td>{c}건</td></tr>" for d, c in sorted(day_count.items())
    )

    html_out = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>이번 주 한반도 안보 회고 · {week_ago:%Y년 %m월 %d일} – {now:%Y년 %m월 %d일}</title>
<meta name="description" content="최근 7일간 Heure반도 안보 관련 헤드라인을 신호별로 묶어 해석한 주간 회고. 긴장도 지수 {(data['level'])}점, 국면 {data['state']}.">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<div class="nav"><a href="/">← 대시보드</a><a href="/weekly">주간 회고</a><a href="/guides">생활 가이드</a><a href="/about">소개</a><a href="/contact">문의</a><a href="/privacy">개인정보</a><a href="/terms">약관</a></div>

<h1>이번 주 한반도 안보 회고
  <span>{week_ago:%Y년 %m월 %d일} – {now:%Y년 %m월 %d일} · 집계 헤드라인 {len(items)}건</span>
</h1>

<div class="card">
  <p><b>이번 주 지수: {data['level']}점 / 국면 "{data['state']}"</b></p>
  <p>{esc(data['guidance'])}</p>
  <div class="bar"><i style="width:{data['level']}%;background:{'#ff5470' if data['level']>=80 else '#ff8b5e' if data['level']>=60 else '#ffc857' if data['level']>=35 else '#3ddc97'}"></i></div>
  <p class="dis">생성 {now:%Y-%m-%d %H:%M} · 수집 매체 {data['feeds_ok']}/{data['feeds_total']}</p>
</div>

<div class="card">
  <h2>이번 주를 한 문장으로</h2>
  <p>{_headline(by_label, items)}</p>
  <p class="dis">이 문장은 이번 주 수집된 헤드라인의 분포를 요약한 것으로, 예측이 아닙니다.</p>
</div>

<div class="ads">[ 광고 영역 ]</div>

{''.join(rows) if rows else '<div class="card"><p>이번 주 분류된 이벤트가 없습니다.</p></div>'}

<div class="card">
  <h2>집계 내역</h2>
  <table><tr><th>일자</th><th>수집 건수</th></tr>{day_rows}</table>
  <p class="dis">상위 출처: {esc(top_src)}</p>
</div>

<div class="card">
  <h2>읽는 법</h2>
  <p>각 항목은 헤드라인을 신호별로 묶은 것입니다. 같은 사건을 여러 매체가 다르게 프레이밍하는 경우가 많으므로, 판단의 근거는 반드시 원문에서 확인하세요. 이 회고는 헤드라인의 분포를 보여줄 뿐 그 자체로 판단을 대신하지 않습니다.</p>
</div>

<footer>© 2026 한반도 긴장도 지수 · <a href="/">대시보드</a> · <a href="/about">소개</a> · <a href="/contact">문의</a> · <a href="/privacy">개인정보처리방침</a></footer>
</body>
</html>
"""
    with open("weekly.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    return len(items), len(by_label)


def _headline(by_label, items):
    if not by_label:
        return "이번 주 집계된 안보 이벤트가 없습니다."
    ranked = sorted(by_label.items(), key=lambda kv: -len(kv[1]))
    top, top_items = ranked[0]
    n = len(top_items)
    second = ranked[1:2]
    tail = f" 동시에 {second[0][0]} 관련 보도도 {len(second[0][1])}건 확인됩니다." if second else ""
    return (
        f"이번 7일간 수집된 {len(items)}건 가운데 '{top}' 신호가 {n}건으로 가장 많았습니다.{tail} "
        "지수 단일 숫자보다 이 분포를 함께 봐야 국면이 선명하게 보입니다."
    )


if __name__ == "__main__":
    n, labels = build()
    print(f"weekly.html 생성 완료 — 헤드라인 {n}건, 신호 분류 {labels}종")