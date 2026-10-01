"""
한반도 긴장도 지수 대시보드 — stdlib only 백엔드
실행: python server.py  ->  http://localhost:8848

동작:
  /api/status  : RSS 헤드라인을 수집해 긴장도 지수(0~100) + 이벤트 타임라인 계산
  /api/feed    : 원본 헤드라인 목록 (출처/시각 포함)
  /            : index.html 정적 서빙
"""
import json
import re
import html
import math
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

KST = timezone(timedelta(hours=9))
CACHE_TTL = 300  # 5분

def gnews(query, days=7):
    q = urllib.parse.quote(f"{query} when:{days}d")
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"

# (라벨, URL, 원본명 유지 여부)
FEEDS = [
    ("구글뉴스 · 북한안보", gnews("북한 안보"), False),
    ("구글뉴스 · 미사일", gnews("북한 미사일"), False),
    ("구글뉴스 · 접경포격", gnews("접경지 북한"), False),
    ("구글뉴스 · 병력", gnews("북한 병력 군부대"), False),
    ("구글뉴스 · 대화", gnews("대북 대화"), False),
    ("구글뉴스 · 한미일", gnews("한미일 군사훈련"), False),
    ("연합뉴스 속보", "https://www.yna.co.kr/rss/news.xml", True),
]

# 운동·연예 등 오탐 방지 제외어
NOISE = re.compile(
    r"아시안게임|올림픽|프로야구|프로축구|배구|양손|체전|챔피언스|우승|결승전|예약석|티켓|콘서트|배우|가수|드라마|영화|연예|예능|맛집|프로필|연애|결혼|임신|출산"
    r"|선수|구단|리그|경기|결승|정상\s*탈환|피구|타구|안타|홈런|골대"
    r"|경찰|체포|살인|방화|횡령|도주|임금체불|부동산|프로필"
)

# 키워드 가중치 (긴장도 점수)
WEIGHTS = [
    (r"미사일|탄도미사일|대륙간|ICBM", 12),
    (r"다발|동시\s*발사|연이어|연일", 8),
    (r"경의선|접경지|접근\s*금지", 10),
    (r"폭파|파괴|철거", 9),
    (r"포병|포격|사격\s*준비|완전사격", 11),
    (r"긴급안보|비상안보|국가안보회의|국방부\s*대응", 7),
    (r"무인기|드론\s*침투|정찰", 7),
    (r"병력|군부대|증원", 5),
    (r"방사능|핵실험|핵탄두", 6),
    (r"해제|평화|호위\s*중단|대화\s*중단", -6),
    (r"협상|대화\s*재개|회의\s*개최|통일\s*논의", -7),
    (r"긴장\s*완화|톤\s*완화|온화", -8),
    (r"사망|부상|총상", 6),
]

# 이벤트 라벨: (패턴, 라벨, 이모지)
EVENTS = [
    (r"미사일.{0,8}발사|발사.{0,8}미사일|미사일\s*사한|미사일\s*사거리|단거리미사일|대륙간", "미사일 발사", "🚀"),
    (r"접경지|접근\s*금지|경의선", "적 접근 / 비무장지대", "🚧"),
    (r"폭파|파괴", "시설 파괴", "💥"),
    (r"포격|포병|완전사격|실사격|사격\s*준비", "포격·사격", "🔴"),
        (r"국가안보회의|안보상황점검", "안보회의 소집", "🏛"),
    (r"무인기|드론|침투", "무인기 활동", "🛸"),
    (r"대북\s*대화|남북\s*대화|북미\s*대화|대화\s*재개|고위급\s*대화", "대체 국면", "🕊"),
    (r"선제공격|전쟁|출병", "전쟁·출병 언급", "⚠"),
    (r"지뢰\s*(추정|발견)|불명지뢰", "지뢰 발견", "🧨"),
]

_cache = {"ts": 0, "data": None}
_lock = threading.Lock()


def fetch(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TensionBoard/1.0",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_date(s):
    s = (s or "").strip()
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(KST)
        except ValueError:
            continue
    return None


def collect():
    items, errors = [], []
    for name, url, keep_label in FEEDS:
        try:
            raw = fetch(url)
            root = ET.fromstring(raw)
            found = 0
            for it in root.iter("item"):
                title = html.unescape((it.findtext("title") or "").strip())
                if not title:
                    continue
                src = name
                if not keep_label:
                    src_el = it.find("source")
                    src = (src_el.text or "").strip() if src_el is not None and src_el.text else name
                    # 구글뉴스 제목 끝의 " - 매체명" 제거
                    title = re.sub(r"\s+-\s+[^-]{2,30}$", "", title)
                if NOISE.search(title):
                    continue
                link = (it.findtext("link") or "").strip()
                pub = parse_date(it.findtext("pubDate"))
                desc = html.unescape(re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))
                items.append(
                    {
                        "source": src,
                        "title": title,
                        "link": link,
                        "published": pub.isoformat() if pub else None,
                        "ts": pub.timestamp() if pub else 0,
                        "summary": re.sub(r"\s+", " ", desc).strip()[:220],
                    }
                )
                found += 1
                if found >= 60:
                    break
        except Exception as e:  # noqa: BLE001
            errors.append(f"{name}: {type(e).__name__}")

    now = time.time()
    items.sort(key=lambda x: x["ts"], reverse=True)
    seen, dedup = set(), []
    for i in items:
        key = re.sub(r"\W", "", i["title"])[:40]
        if key and key in seen:
            continue
        seen.add(key)
        dedup.append(i)
    items = dedup
    recent = [i for i in items if i["ts"] and now - i["ts"] < 60 * 60 * 24 * 7]

    # 긴장도: 최근 48시간 헤드라인 가중합 → 0~100 정규화
    score = 0
    for i in recent:
        if now - i["ts"] > 48 * 3600:
            continue
        text = i["title"] + " " + i["summary"]
        decay = 1.0 - min(1.0, (now - i["ts"]) / (48 * 3600)) * 0.5
        for pat, w in WEIGHTS:
            if re.search(pat, text):
                score += w * decay
    level = max(0, min(100, int(round(100 * (1 - math.exp(-max(score, 0) / 55))))))

    by_source = {}
    for i in items:
        if now - i["ts"] > 60 * 60 * 24 * 7:
            continue
        by_source.setdefault(i["source"], []).append(i)

    # 소스별 공정 배분 (한 매체가 화면을 독점하지 않도록)
    interleaved, round_no = [], 0
    while len(interleaved) < 60:
        added = False
        for src in by_source:
            lst = by_source[src]
            if round_no < len(lst):
                interleaved.append(lst[round_no])
                added = True
                if len(interleaved) >= 60:
                    break
        if not added:
            break
        round_no += 1

    # 이벤트 타임라인 (중복 제거)
    timeline, tl_seen = [], set()
    for i in recent[:200]:
        for pat, label, emoji in EVENTS:
            if re.search(pat, i["title"]):
                tkey = (label, re.sub(r"\W", "", i["title"])[:30])
                if tkey in tl_seen:
                    break
                tl_seen.add(tkey)
                timeline.append(
                    {
                        "ts": i["ts"],
                        "published": i["published"],
                        "label": label,
                        "emoji": emoji,
                        "title": i["title"],
                        "source": i["source"],
                        "link": i["link"],
                    }
                )
                break
    timeline.sort(key=lambda x: x["ts"], reverse=True)
    timeline = timeline[:40]

    state = "관측" if level < 35 else "주의" if level < 60 else "경계" if level < 80 else "위기"
    guidance = {
        "관측": "일상생활 제한 없음. 공식 채널만 확인하세요.",
        "주의": "SNS·헤드라인이 과장되기 쉬운 국면. 공식 채널을 확인하세요.",
        "경계": "지자체 대피경로와 가족 연락 방법을 미리 정해두세요.",
        "위기": "낚시·SNS 정보가 아니라 공식 대체 공백(방송·지자체 앱)만 기준하세요.",
    }[state]

    return {
        "updated": datetime.now(KST).isoformat(),
        "level": level,
        "state": state,
        "guidance": guidance,
        "raw_score": round(score, 1),
        "timeline": timeline,
        "feed": interleaved,
        "feeds_ok": len(FEEDS) - len(errors),
        "feeds_total": len(FEEDS),
        "errors": errors,
    }


def get_data(force=False):
    with _lock:
        if force or _cache["data"] is None or time.time() - _cache["ts"] > CACHE_TTL:
            try:
                _cache["data"] = collect()
                _cache["ts"] = time.time()
            except Exception as e:  # noqa: BLE001
                if _cache["data"] is None:
                    return {
                        "error": str(e),
                        "level": 0,
                        "state": "오류",
                        "timeline": [],
                        "feed": [],
                        "updated": datetime.now(KST).isoformat(),
                        "guidance": "수집 실패 — 네트워크 또는 피드 상태를 확인하세요.",
                        "feeds_ok": 0,
                        "feeds_total": len(FEEDS),
                        "errors": [str(e)],
                    }
        return _cache["data"]


BASE_URL = "https://tension-board.example"
PAGES = {
    "about": "about.html",
    "contact": "contact.html",
    "privacy": "privacy.html",
    "terms": "terms.html",
    "guides": "guides.html",
}
PAGE_TITLES = {
    "": "한반도 긴장도 지수",
    "guides": "긴장 고조 때 미리 해둘 것",
    "weekly": "이번 주 한반도 안보 회고",
    "about": "소개",
    "contact": "문의",
    "privacy": "개인정보처리방침",
    "terms": "이용약관",
}


def read_file(name):
    with open(name, encoding="utf-8") as f:
        return f.read()


def sitemap():
    urls = "".join(
        f"<url><loc>{BASE_URL}/{p}</loc><changefreq>hourly</changefreq>"
        f"<priority>{'1.0' if p == '' else '0.7' if p == 'weekly' else '0.6'}</priority></url>"
        for p in PAGE_TITLES
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + urls
        + "</urlset>"
    )


def weekly_loop():
    """주간 회고를 30분마다 자동 생성한다."""
    import importlib
    while True:
        try:
            importlib.import_module("weekly").build()
            print("weekly.html 갱신 완료")
        except Exception as e:  # noqa: BLE001
            print(f"weekly 생성 실패: {type(e).__name__}: {e}")
        time.sleep(1800)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/api/status", "/api/feed"):
            self._send(200, json.dumps(get_data(), ensure_ascii=False), "application/json; charset=utf-8")
            return
        if path == "/style.css":
            self._send(200, read_file("style.css"), "text/css; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            self._send(200, read_file("index.html"), "text/html; charset=utf-8")
            return
        page = PAGES.get(path.lstrip("/"))
        if page:
            self._send(200, read_file(page), "text/html; charset=utf-8")
            return
        if path == "/weekly":
            self._send(200, read_file("weekly.html"), "text/html; charset=utf-8")
            return
        if path == "/robots.txt":
            self._send(200, read_file("robots.txt"), "text/plain; charset=utf-8")
            return
        if path == "/sitemap.xml":
            self._send(200, sitemap(), "application/xml; charset=utf-8")
            return
        self._send(404, "not found", "text/plain; charset=utf-8")

    def log_message(self, fmt, *a):
        print(f"[{datetime.now(KST).strftime('%H:%M:%S')}] {fmt % a}")


if __name__ == "__main__":
    import os

    print("한반도 긴장도 대시보드  →  http://localhost:8848")
    port = int(os.environ.get("PORT", 8848))
    host = os.environ.get("HOST", "127.0.0.1")
    if not os.path.exists("weekly.html"):
        try:
            import weekly
            weekly.build()
        except Exception as e:  # noqa: BLE001
            print(f"초기 weekly 생성 실패: {e}")
    threading.Thread(target=weekly_loop, daemon=True).start()
    ThreadingHTTPServer((host, port), Handler).serve_forever()