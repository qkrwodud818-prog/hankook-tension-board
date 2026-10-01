/*
 * 광고 설정 — publisher ID 는 여기 한 곳에서만 바꾸면 됩니다.
 *
 * 1) Google AdSense
 *    - AdSense 콘솔 > 계정 > 계정 정보 에서 publisher ID(ca-pub-XXXXXXXXXXXXXXXX) 복사
 *    - 아래 ADSENSE_CLIENT 에 붙여넣으면 모든 .ads 슬롯에 자동 삽입됩니다.
 *    - 빈 값이면 광고 스크립트를 아예 로드하지 않습니다(잘못된 ID로 인한 오류 방지).
 *
 * 2) 슬롯 ID
 *    - AdSense > 광고 > AdSense 광고유닛 에서 슬롯별 ID 를 만들어
 *      data-ad-slot 속성에 넣어두면 그 ID 가 사용됩니다.
 */
// 계정 ID (Account ID): AF5644596
// 아래에는 publisher ID 를 넣습니다. 형식: ca-pub-1234567890123456
// (AdSense > 관리 > 계정 정보 > "광고 코드" 화면의 ca-pub- 줄에서 확인)
const ADSENSE_CLIENT = "";
const ADSENSE_ENABLED = ADSENSE_CLIENT.startsWith("ca-pub-");

function mountAds() {
  document.querySelectorAll(".ads").forEach(function (el) {
    if (!ADSENSE_ENABLED) {
      el.innerHTML = '<span class="ad-off">광고 영역</span>';
      return;
    }
    const slot = el.dataset.adSlot || "";
    el.innerHTML =
      '<ins class="adsbygoogle" style="display:block" ' +
      (slot ? 'data-ad-client="' + ADSENSE_CLIENT + '" data-ad-slot="' + slot + '" ' : "") +
      'data-ad-format="auto" data-full-width-responsive="true"></ins>';
  });
  if (ADSENSE_ENABLED) {
    const s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + ADSENSE_CLIENT;
    document.head.appendChild(s);
    try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
  }
}
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mountAds);
} else {
  mountAds();
}