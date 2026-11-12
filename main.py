import random
import string
import threading
import time
import uuid

import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────
# 게임 설정 (여기 숫자만 바꾸면 규칙이 바뀝니다)
# ─────────────────────────────────────────────
START_CASH = 1_000_000      # 시작 예산
START_PRICE = 50_000        # 주식 초기 가격 (최소 5만 원 시작)
MAX_PRICE = 500_000         # 주가 상한 (최대 30만원 상승 반영)
MIN_PRICE = 10_000          # 주가 하한
MAX_PRICE_UP = 300_000      # 한 라운드 최대 상승 금액 (+30만원)
MAX_PRICE_DOWN = 200_000    # 한 라운드 최대 하락 금액 (-20만원)
ROUND_SECONDS = 300         # 매매 시간(5분)
MINIGAME_CHANCE = 0.3       # 라운드 사이 미니게임 확률
MINIGAME_FORCE_AFTER = 4    # 4번 연속 안 나오면 5번째에는 반드시 발생
FALSE_HINT_RATE = 0.1       # 힌트가 거짓일 확률
POLL_SECONDS = 2            # 화면 자동 새로고침 주기

# 종목 이름은 여기서만 바꾸면 됩니다
STOCKS = {
    "ship": {"name": "조선업", "icon": "🚢",
             "desc": "배를 설계하고 만드는 산업이에요. 한 번 수주하면 몇 년치 일감이 생기지만, 원자재 가격·파업·해운 경기에 크게 영향을 받아요."},
    "chip": {"name": "IT반도체 산업", "icon": "💾",
             "desc": "스마트폰·AI·서버에 들어가는 반도체를 만드는 산업이에요. 기술 경쟁, 세계 수요, 공장 가동 상황에 민감해요."},
    "car": {"name": "자동차산업", "icon": "🚗",
            "desc": "자동차를 만들어 국내외에 파는 산업이에요. 수출, 관세, 신차 인기, 전기차 전환이 주가에 영향을 줘요."},
    "ent": {"name": "엔터테인먼트 산업", "icon": "🎤",
            "desc": "음악·드라마·공연으로 돈을 버는 산업이에요. 인기 가수의 활동, 해외 흥행, 소속사 이슈에 크게 흔들려요."},
    "fin": {"name": "금융업", "icon": "🏦",
            "desc": "은행·보험·증권처럼 돈을 빌려주고 불려주는 산업이에요. 금리, 경기, 대출 부실 여부에 영향을 받아요."},
    "mat": {"name": "재료산업", "icon": "🧱",
            "desc": "철강·화학·신소재처럼 다른 산업의 원료를 만드는 산업이에요. 원자재 가격과 정부 정책에 영향을 받아요."},
}

KIND_LABEL = {"headline": "📰 헤드라인", "special": "📢 특보(찌라시)", "sns": "💬 SNS 누리꾼 대화"}
ACCURACY = {"headline": 0.9, "special": 0.6, "sns": 0.25}

PRICE_DELTA_UP = {
    "headline": (20_000, 120_000),
    "special": (50_000, 200_000),
    "sns": (80_000, 300_000),
}
PRICE_DELTA_DOWN = {
    "headline": (20_000, 100_000),
    "special": (40_000, 150_000),
    "sns": (60_000, 200_000),
}


def sc(kind, title, body, effects, true_reason, fake_reason):
    return dict(kind=kind, title=title, body=body, effects=effects,
                true_reason=true_reason, fake_reason=fake_reason)


# 16개의 상황 (특보는 3줄 정도로 간결하게 요약)
SCENARIOS = [
    sc("headline", "정부, 대규모 선박 수주 확정 발표",
       "국내 주요 조선사들이 해외 대형 해운사와 총 20조 원 규모의 선박 건조 계약을 체결했습니다. 친환경 연료 추진선과 대형 컨테이너선 등이 포함되어 장기적인 일감 확보에 청신호가 켜졌습니다. 다만 후판 등 원자재 가격 변동에 따른 수익성 추이를 지켜봐야 한다는 신중론도 나옵니다.",
       {"ship": +1}, "대규모 수주 확정으로 조선업 실적 기대감이 커졌습니다.",
       "발표와 달리 실제 수주 규모가 크게 줄어 실망 매물이 나왔습니다."),
    sc("headline", "글로벌 AI 기업, 국내 반도체 업체에 HBM 대량 주문",
       "글로벌 AI 산업 성장에 힘입어 국내 반도체 기업들이 고대역폭메모리(HBM) 대량 공급 주문을 확보했습니다. AI 서버용 고성능 메모리 수요가 급증하면서 실적 개선 기대감이 높아지고 있습니다. 다만 설비 투자 비용과 경쟁사 추격 여부가 향후 변수로 꼽힙니다.",
       {"chip": +1}, "AI 수요 폭증으로 반도체 주문이 늘었습니다.",
       "주문이 갑자기 취소되며 기대감이 꺼졌습니다."),
    sc("headline", "주요 수출국, 자동차 관세 대폭 인상 확정",
       "주요 수출국이 수입 자동차에 적용하는 관세를 대폭 인상하기로 결정했습니다. 현지 판매 가격 상승으로 인한 가격 경쟁력 약화와 수익성 악화 우려가 커지고 있습니다. 완성차 업계는 현지 생산 확대 및 판매 전략 재검토 등 비상 대응에 나섰습니다.",
       {"car": -1}, "관세 부담으로 자동차 수출 전망이 어두워졌습니다.",
       "관세 시행이 연기되면서 안도 매수가 몰렸습니다."),
    sc("headline", "중앙은행 기준금리 인상… 은행 예대마진 확대 전망",
       "중앙은행이 기준금리를 인상함에 따라 은행권의 예대마진이 확대될 것으로 예상됩니다. 단기적으로 이자이익이 증가하여 일부 금융사 실적이 개선될 전망입니다. 다만 가계와 기업의 이자 부담 가중에 따른 대출 부실 위험도 함께 제기됩니다.",
       {"fin": +1}, "금리 인상으로 금융권 수익성 개선 기대가 커졌습니다.",
       "대출 연체율 급증 소식이 겹치며 금융주가 약세를 보였습니다."),
    sc("headline", "원자재 가격 폭락… 철강·화학 업계 비상",
       "국제 원자재 가격이 단기간에 급락하면서 철강 및 화학 소재 산업의 경영 환경이 악화되었습니다. 높은 가격에 확보한 기존 재고로 인해 재고 평가 손실이 발생할 위험이 커졌습니다. 다만 신규 원료 매입 기업에는 비용 절감 요인이 될 수도 있습니다.",
       {"mat": -1}, "원자재 가격 급락으로 재료 기업의 수익성이 악화됐습니다.",
       "예상과 달리 원자재 가격이 반등하며 주가가 올랐습니다."),
    sc("headline", "국내 아이돌 그룹, 빌보드 1위 달성",
       "국내 아이돌 그룹이 미국 빌보드 메인 차트 1위를 달성하며 글로벌 흥행을 증명했습니다. 음원 및 음반 판매를 넘어 공연, 광고, 콘텐츠 유통 등 연관 사업 확장 기대감이 커졌습니다. 다만 지속적인 팬덤 유지와 후속 활동 성과가 중요합니다.",
       {"ent": +1}, "빌보드 1위 소식에 엔터 기업 가치가 올랐습니다.",
       "집계 오류가 확인되어 호재가 사라졌습니다."),

    # 특보 (3줄 요약 적용)
    sc("special", "[특보] 반도체 공장 대규모 정전 사고 발생… 생산 라인 일시 중단",
       "국내 주요 반도체 공장에서 대규모 정전 사고가 발생해 주요 생산 라인 가동이 한때 중단되었습니다.\n일부 민감 공정 장비의 피해 점검이 진행 중이며, 단기적 출하 차질 및 복구 비용 발생 우려가 커지고 있습니다.\n글로벌 반도체 공급 부족 우려가 고개 들며 시장에 긴장감이 감돌고 있습니다.",
       {"chip": -1}, "생산 차질 우려로 반도체주가 하락했습니다.",
       "정전은 곧 복구되어 생산에 영향이 없었고 오히려 주가가 올랐습니다."),
    sc("special", "[특보] 국내 대형 조선소 노조, 임금 협상 결렬 속 총파업 전격 예고",
       "대형 조선소 노조가 임단협 교섭 결렬을 선언하고 전면적인 총파업 돌입을 공식화했습니다.\n파업 강행 시 건조 중인 선박의 인도 지연 및 거액의 지체상금 발생 위기감이 고조되고 있습니다.\n노사 갈등이 장기화될 경우 조선업 전반의 수주 신뢰도 하락으로 이어질 수 있습니다.",
       {"ship": -1}, "파업 우려로 납기 지연 걱정이 커졌습니다.",
       "노사가 극적으로 합의해 파업이 철회되며 주가가 올랐습니다."),
    sc("special", "[찌라시] 국내 완성차 업체 신형 전기차, 출시 전 사전계약 폭주?",
       "신형 플래그십 전기차 모델이 사전계약 신기록을 경신하며 폭발적 반응을 얻고 있다는 소문이 확산 중입니다.\n초기 물량 확보를 위한 문의가 폭주해 예상 판매 목표를 크게 초과 달성할 것이라는 전망입니다.\n전기차 전환 가속화 기조 속에서 해당 기업의 강력한 실적 반등 모멘텀이 될 수 있습니다.",
       {"car": +1}, "신모델 사전계약이 몰리며 자동차주가 올랐습니다.",
       "사전계약 부진이 알려지며 기대가 꺾였습니다."),
    sc("special", "[특보] 대형 엔터테인먼트 소속사 대표, 수백억 원대 횡령 의혹 피소",
       "대형 엔터 기획사 총괄 대표가 회사 자금 횡령 혐의로 사법당국에 고발당해 충격을 주고 있습니다.\n경찰이 계좌 추적 및 내부 회계 장부 점검에 착수하며 오너 리스크 직격탄을 맞았습니다.\n주가 급락과 함께 아티스트 재계약 및 해외 활동 차질 우려가 확산되고 있습니다.",
       {"ent": -1}, "경영 불확실성에 엔터주가 하락했습니다.",
       "의혹이 사실무근으로 밝혀지며 오히려 주가가 반등했습니다."),
    sc("special", "[찌라시] 시중 대형 은행, 해외 부동산 투자서 천문학적 손실설",
       "대형 은행의 해외 상업용 부동산 및 파생상품 투자에서 대규모 부실과 손실 확정이 임박했다는 소문이 돌고 있습니다.\n고금리 장기화로 자산 가치가 폭락하여 추가 대손충당금 적립 압박을 받고 있다는 분석입니다.\n은행권 전반의 건전성 악화 우려로 투자자들의 불안감이 빠르게 확산되고 있습니다.",
       {"fin": -1}, "투자 손실 우려로 금융주가 흔들렸습니다.",
       "손실이 미미한 것으로 확인되어 안도감이 퍼졌습니다."),
    sc("special", "[특보] 국내 소재 전문 기업, 전고체 배터리 신소재 특허 세계 최초 취득",
       "소재 전문 기업이 전고체 배터리 안정성을 극대화할 핵심 원천 기술 특허를 세계 최초 취득했습니다.\n화재 위험 원천 차단 및 에너지 밀도 향상으로 글로벌 배터리·완성차 업체의 러브콜이 이어지고 있습니다.\n상용화 시기를 대폭 앞당길 혁신적 호재로 작용하며 주가에 강한 상승 압력을 넣고 있습니다.",
       {"mat": +1}, "신소재 기대감에 재료주가 올랐습니다.",
       "특허 분쟁 소식이 나오며 기대가 사라졌습니다."),

    # SNS 대화 설정
    sc("sns", "@주식고수: 이번에 조선이랑 자동차 둘 다 간다ㅋㅋ",
       "\"내가 아는 사람이 직접 들은 얘기임. 지금 안 사면 후회함 ㅋㅋ\"",
       {"ship": +1, "car": +1}, "소문대로 조선·자동차가 함께 급등했습니다.",
       "소문과 정반대로 조선·자동차가 함께 급락했습니다."),
    sc("sns", "익명 게시판: 반도체 회사 CEO 사임한다던데?",
       "\"곧 공식 발표 나온대. 내부자가 알려줌. 이건 진짜임\"",
       {"chip": -1}, "CEO 사임 발표로 반도체주가 급락했습니다.",
       "사임설은 가짜 뉴스로 밝혀지며 주가가 급등했습니다."),
    sc("sns", "커뮤니티: 엔터 대박 신인 데뷔한다, 금융주는 곧 폭락각",
       "\"신인 그룹 티저 영상 조회수 미쳤다. 반대로 은행주는 끝났다고 봄\"",
       {"ent": +1, "fin": -1}, "소문대로 엔터주는 오르고 금융주는 내렸습니다.",
       "소문과 반대로 엔터주는 내리고 금융주는 올랐습니다."),
    sc("sns", "인플루언서: 재료산업 곧 정부 지원금 받는대! 지금이 기회",
       "\"정부 관계자한테 들었음. 영끌각ㅋㅋ 이번엔 진짜\"",
       {"mat": +1}, "정부 지원 소식이 사실로 확인되어 급등했습니다.",
       "지원 소식은 헛소문이었고 실망 매물이 쏟아졌습니다."),
]

SNS_COMMENTS = {
    "sns_1": [
        ("김태린", "조선업 수주 규모가 꽤 큰데? 이번 계약이 실적에 반영되려면 시간이 좀 걸리겠지."),
        ("이서영", "자동차까지 같이 오른다는 얘기는 아직 근거가 부족한 것 같아."),
        ("박선유", "나는 친환경 선박 쪽 수요가 계속 늘어날지가 더 중요해 보여."),
        ("박경민", "뉴스만 보면 호재인데 원자재 가격도 같이 확인해야 할 듯."),
        ("이예나", "일단 시장 반응을 보고 들어가도 늦지 않을 것 같은데ㅋㅋ"),
        ("정하영", "수주 계약이 실제 매출로 잡히는 시점도 따져봐야지."),
        ("유예나", "그래도 조선업 분위기가 좋아지는 신호인 건 맞는 듯!"),
        ("손예원", "나는 자동차는 관세 이슈도 있어서 조금 더 지켜볼래."),
    ],
    "sns_2": [
        ("박수현", "CEO 사임설이면 회사 경영 방향에도 영향이 있을 수 있겠네."),
        ("곽이안", "근데 아직 공식 발표가 없잖아. 소문만 믿기는 위험하지."),
        ("김나윤", "반도체는 기술 경쟁도 심해서 경영진 변화가 변수일 수는 있겠다."),
        ("안민영", "내부자한테 들었다는 말은 출처부터 확인해야 함."),
        ("박효찬", "이런 글 올라오면 주가가 먼저 움직일 수도 있어서 무섭다."),
        ("이진우", "사실인지 아닌지는 공시나 공식 발표가 나와야 알겠지."),
        ("신재민", "불확실할 때는 무리하게 매수하지 않는 게 낫다고 봄."),
        ("이시우", "결국 확인된 정보와 온라인 소문은 구분해서 봐야지."),
    ],
    "sns_3": [
        ("김태린", "신인 그룹 티저 반응이 좋으면 엔터 쪽 기대감은 생기겠다."),
        ("박선유", "조회수만으로 흥행을 확신할 수는 없지 않을까?"),
        ("이예나", "팬덤이 실제 앨범이나 공연 소비로 이어지는지가 중요할 듯."),
        ("정하영", "금융주는 금리랑 연체율을 같이 봐야 해서 단순하게 판단하기 어렵겠어."),
        ("박수현", "한쪽은 신인 데뷔 기대감, 한쪽은 금융 불안 소문이네."),
        ("김나윤", "서로 다른 산업이라 각자 근거를 따져보는 게 좋겠어."),
        ("박경민", "나는 공식 일정이나 실적 자료가 나올 때까지 기다려볼래."),
        ("손예원", "SNS 반응이 뜨거워도 투자 판단은 따로 해야 한다는 거지ㅋㅋ"),
    ],
    "sns_4": [
        ("유예나", "정부 지원금 소식이면 소재 기업에는 분명 관심이 쏠릴 만하네."),
        ("곽이안", "지원 대상이 모든 기업인지 특정 기술 분야인지부터 확인해야 해."),
        ("안민영", "정책 발표 전에 기대감만으로 움직이는 경우도 많더라."),
        ("박효찬", "지원 규모가 실제 기업 매출에 얼마나 영향을 줄지도 중요하지."),
        ("이진우", "공식 보도자료가 있는지 찾아보는 게 먼저일 듯."),
        ("신재민", "재료산업은 원자재 가격도 변수라서 정책 하나만 보면 안 돼."),
        ("이서영", "그래도 신소재 분야가 주목받는 계기는 될 수는 있겠다."),
        ("이시우", "확인 전까지는 가능성 정도로만 생각하는 게 맞겠어."),
    ],
}

for i, scenario in enumerate([s for s in SCENARIOS if s["kind"] == "sns"], start=1):
    scenario["comments"] = SNS_COMMENTS[f"sns_{i}"]

UP_REASONS = ["뚜렷한 이유 없이 매수세가 몰렸습니다.", "시장 분위기가 좋아지며 소폭 상승했습니다.",
              "큰 뉴스는 없었지만 투자자들의 기대감이 올랐습니다."]
DOWN_REASONS = ["뚜렷한 이유 없이 차익 실현 매물이 나왔습니다.", "시장 분위기가 가라앉으며 소폭 하락했습니다.",
                "큰 뉴스는 없었지만 투자자들이 불안해했습니다."]


# ─────────────────────────────────────────────
# 서버 공용 저장소
# ─────────────────────────────────────────────
@st.cache_resource
def get_store():
    return {"rooms": {}, "lock": threading.RLock()}


STORE = get_store()
ROOMS = STORE["rooms"]
LOCK = STORE["lock"]


def make_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=5))
        if code not in ROOMS:
            return code


def new_room(code, host_id):
    return {
        "code": code, "host_id": host_id, "status": "lobby",
        "players": {}, "spectators": {},
        "prices": {k: START_PRICE for k in STOCKS},
        "history": {k: [START_PRICE] for k in STOCKS},
        "round": 0, "current": None, "upcoming": None, "order": [],
        "timer_end": 0.0, "result": [], "mini_misses": 0,
    }


def new_player(name):
    return {"name": name, "cash": START_CASH, "holdings": {k: 0 for k in STOCKS},
            "done": False, "quiz": None, "hints": []}


def total_value(room, p):
    return p["cash"] + sum(n * room["prices"][k] for k, n in p["holdings"].items())


# ─────────────────────────────────────────────
# 게임 로직
# ─────────────────────────────────────────────
def _rand_step_amount(lo, hi, step=1_000):
    return random.randrange(lo, hi + 1, step)


def build_outcome(scenarios):
    changes = {}
    for scn in scenarios:
        is_true = random.random() < ACCURACY[scn["kind"]]
        sign = 1 if is_true else -1
        for k, direction in scn["effects"].items():
            final_dir = direction * sign
            if final_dir > 0:
                lo, hi = PRICE_DELTA_UP[scn["kind"]]
                delta_amount = _rand_step_amount(lo, hi)
            else:
                lo, hi = PRICE_DELTA_DOWN[scn["kind"]]
                delta_amount = -_rand_step_amount(lo, hi)

            reason = scn["true_reason"] if is_true else scn["fake_reason"]
            if k in changes:
                old_delta, old_reason = changes[k]
                combined = max(-MAX_PRICE_DOWN, min(MAX_PRICE_UP, old_delta + delta_amount))
                changes[k] = (combined, old_reason + " / " + reason)
            else:
                changes[k] = (delta_amount, reason)

    target = min(4, max(len(changes), random.choice([2, 3, 3, 3, 3, 4])))
    others = [k for k in STOCKS if k not in changes]
    random.shuffle(others)
    while len(changes) < target and others:
        k = others.pop()
        up = random.random() < 0.5
        if up:
            delta_amount = _rand_step_amount(10_000, 60_000)
        else:
            delta_amount = -_rand_step_amount(10_000, 50_000)
        changes[k] = (delta_amount, random.choice(UP_REASONS if up else DOWN_REASONS))
    return changes


def draw(room):
    selected = []
    for kind in ("headline", "special", "sns"):
        scn = dict(random.choice([s for s in SCENARIOS if s["kind"] == kind]))
        if kind == "sns":
            all_c = _normalise_comments(scn.get("comments", []))
            if all_c:
                cnt = random.choice([2, 3])
                scn["sampled_comments"] = random.sample(all_c, min(cnt, len(all_c)))
        selected.append(scn)
    return {"sc": selected[0], "articles": selected,
            "changes": build_outcome(selected)}


def start_round(room):
    room["round"] += 1
    room["current"] = room["upcoming"] or draw(room)
    room["upcoming"] = None
    for p in room["players"].values():
        p["done"] = False
        p["quiz"] = None
    room["timer_end"] = time.time() + ROUND_SECONDS
    room["status"] = "trading"


def resolve(room):
    res = []
    for k, (delta_amount, reason) in room["current"]["changes"].items():
        old = room["prices"][k]
        new = max(MIN_PRICE, min(MAX_PRICE, old + int(delta_amount)))
        room["prices"][k] = new
        res.append({"key": k, "old": old, "new": new, "reason": reason})
    for k in STOCKS:
        room["history"][k].append(room["prices"][k])
    room["result"] = res
    room["upcoming"] = draw(room)
    room["status"] = "result"


def tick(room):
    with LOCK:
        if room["status"] == "trading":
            players = room["players"].values()
            all_done = bool(room["players"]) and all(p["done"] for p in players)
            if all_done or time.time() >= room["timer_end"]:
                resolve(room)


def make_hint(room):
    changes = room["upcoming"]["changes"]
    k = random.choice(list(changes))
    up = changes[k][0] > 0
    if random.random() < FALSE_HINT_RATE:
        up = not up
    return f"다음 라운드에 '{STOCKS[k]['name']}' 주가가 {'오를' if up else '내릴'} 가능성이 높아 보입니다."


def add_hint(room, p):
    if room["upcoming"] is None:
        return False
    p["hints"].append({"round": room["round"] + 1, "text": make_hint(room)})
    return True


def make_quiz():
    t = random.choice(["add", "sub", "mul"])
    if t == "add":
        a, b = random.randint(100, 999), random.randint(100, 999)
        return {"q": f"{a} + {b} = ?", "a": a + b, "solved": None}
    if t == "sub":
        a = random.randint(300, 999)
        b = random.randint(100, a - 1)
        return {"q": f"{a} - {b} = ?", "a": a - b, "solved": None}
    a, b = random.randint(12, 49), random.randint(3, 9)
    return {"q": f"{a} × {b} = ?", "a": a * b, "solved": None}


def start_minigame(room):
    for p in room["players"].values():
        p["quiz"] = make_quiz()
    room["mini_misses"] = 0
    room["status"] = "minigame"


# ─────────────────────────────────────────────
# 버튼 콜백
# ─────────────────────────────────────────────
def login(code, pid, role):
    st.session_state.update(code=code, pid=pid, role=role)
    st.query_params.update(room=code, pid=pid, role=role)


def cb_create():
    with LOCK:
        code = make_code()
        pid = uuid.uuid4().hex[:12]
        ROOMS[code] = new_room(code, pid)
    login(code, pid, "host")


def cb_join_mode():
    st.session_state.mode = "join"


def cb_join():
    code = st.session_state.get("join_code", "").strip().upper()
    role = st.session_state.get("join_role", "참가자")
    name = st.session_state.get("join_name", "").strip()
    st.session_state.join_error = ""
    with LOCK:
        room = ROOMS.get(code)
        if room is None:
            st.session_state.join_error = "그런 방 코드가 없어요. 코드를 다시 확인해 주세요."
            return
        pid = uuid.uuid4().hex[:12]
        if role == "참가자":
            if room["status"] != "lobby":
                st.session_state.join_error = "이미 게임이 시작되어 참가자로는 들어갈 수 없어요. 관전자로 입장해 보세요."
                return
            if not name:
                st.session_state.join_error = "팀 이름을 입력해 주세요."
                return
            if any(p["name"] == name for p in room["players"].values()):
                st.session_state.join_error = "이미 있는 팀 이름이에요. 다른 이름을 써 주세요."
                return
            room["players"][pid] = new_player(name)
            login(code, pid, "player")
        else:
            room["spectators"][pid] = True
            login(code, pid, "spectator")
    st.session_state.mode = ""


def cb_leave():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()


def cb_start(room):
    with LOCK:
        if room["status"] == "lobby" and room["players"]:
            start_round(room)


def cb_next(room):
    with LOCK:
        if room["status"] != "result":
            return
        if room["mini_misses"] >= MINIGAME_FORCE_AFTER or random.random() < MINIGAME_CHANCE:
            start_minigame(room)
        else:
            room["mini_misses"] += 1
            start_round(room)


def cb_minigame(room):
    with LOCK:
        if room["status"] == "result":
            start_minigame(room)


def cb_end_minigame(room):
    with LOCK:
        if room["status"] == "minigame":
            start_round(room)


def cb_grant(room):
    pid = st.session_state.get("grant_pid")
    with LOCK:
        p = room["players"].get(pid)
        if p and room["status"] in ("result", "minigame") and add_hint(room, p):
            st.toast(f"{p['name']} 팀에게 힌트권을 줬어요!", icon="🎟️")


def cb_end_game(room):
    with LOCK:
        if room["status"] in ("trading", "result", "minigame"):
            for p in room["players"].values():
                p["cash"] = total_value(room, p)
                p["holdings"] = {k: 0 for k in STOCKS}
            room["status"] = "final"


def cb_trade(room, pid, k, side, custom_qty=None):
    with LOCK:
        p = room["players"].get(pid)
        if room["status"] != "trading" or not p or p["done"]:
            st.toast("지금은 거래할 수 없어요.", icon="⛔")
            return
        price = room["prices"][k]

        if side == "buy":
            qty = custom_qty if custom_qty is not None else int(st.session_state.get(f"qty_buy_{k}", 1))
            if qty <= 0:
                st.toast("수량을 올바르게 입력해주세요.", icon="🚫")
                return
            if price * qty > p["cash"]:
                st.toast("현금이 부족해요. 대출은 금지예요!", icon="🚫")
                return
            p["cash"] -= price * qty
            p["holdings"][k] += qty
            st.toast(f"{STOCKS[k]['name']} {qty}주 매수!", icon="🛒")
        else:
            qty = custom_qty if custom_qty is not None else int(st.session_state.get(f"qty_sell_{k}", 1))
            if qty <= 0:
                st.toast("수량을 올바르게 입력해주세요.", icon="🚫")
                return
            if qty > p["holdings"][k]:
                st.toast("가지고 있는 주식보다 많이 팔 수 없어요.", icon="🚫")
                return
            p["cash"] += price * qty
            p["holdings"][k] -= qty
            st.toast(f"{STOCKS[k]['name']} {qty}주 매도!", icon="💰")


def cb_done(room, pid):
    with LOCK:
        p = room["players"].get(pid)
        if p and room["status"] == "trading":
            p["done"] = True


def cb_answer(room, pid):
    ans = int(st.session_state.get("quiz_ans", 0))
    with LOCK:
        p = room["players"].get(pid)
        if room["status"] == "minigame" and p and p["quiz"] and p["quiz"]["solved"] is None:
            p["quiz"]["solved"] = (ans == p["quiz"]["a"])
            if p["quiz"]["solved"]:
                add_hint(room, p)
    st.session_state["quiz_ans"] = 0


# ─────────────────────────────────────────────
# 화면 조각들
# ─────────────────────────────────────────────
def fmt(n):
    return f"{n:,}원"


def fmt_delta(diff):
    if diff > 0:
        return f"▲ {diff:,}원"
    elif diff < 0:
        return f"▼ {abs(diff):,}원"
    return "0원 (-)"


def _normalise_comments(raw_comments):
    if not raw_comments:
        return []
    if isinstance(raw_comments, dict):
        raw_items = list(raw_comments.items())
    elif isinstance(raw_comments, (list, tuple)):
        raw_items = list(raw_comments)
    else:
        raw_items = [raw_comments]

    normalised = []
    for item in raw_items:
        if isinstance(item, dict):
            speaker = item.get("speaker") or item.get("name") or "누리꾼"
            comment = item.get("comment") or item.get("text") or ""
        elif isinstance(item, (list, tuple)):
            if len(item) >= 2:
                speaker, comment = item[0], item[1]
            elif len(item) == 1:
                speaker, comment = "누리꾼", item[0]
            else:
                continue
        else:
            speaker, comment = "누리꾼", item
        normalised.append((str(speaker), str(comment)))
    return normalised


def newspaper(articles):
    if isinstance(articles, dict):
        articles = articles.get("articles") or [articles]
    if not isinstance(articles, (list, tuple)):
        st.warning("이번 라운드의 신문 데이터를 불러오지 못했습니다.")
        return

    headline_scn = next((s for s in articles if s.get("kind") == "headline"), None)
    special_scn = next((s for s in articles if s.get("kind") == "special"), None)
    sns_scn = next((s for s in articles if s.get("kind") == "sns"), None)

    with st.container(border=True):
        st.markdown("<h3 style='text-align: center;'>📈 도농 경제신문</h3>", unsafe_allow_html=True)
        st.divider()

        left_col, right_col = st.columns(2)

        with left_col:
            if headline_scn:
                with st.container(border=True):
                    st.caption("📰 헤드라인 기사")
                    st.markdown(f"#### {headline_scn.get('title', '')}")
                    st.write(headline_scn.get('body', ''))
            else:
                st.info("헤드라인 기사가 없습니다.")

        with right_col:
            if special_scn:
                with st.container(border=True):
                    st.caption("📢 특보")
                    st.markdown(f"#### {special_scn.get('title', '')}")
                    st.write(special_scn.get('body', ''))
            else:
                st.info("특보가 없습니다.")

            if sns_scn:
                with st.container(border=True):
                    st.caption("💬 SNS 누리꾼 대화")
                    st.markdown(f"#### {sns_scn.get('title', '')}")
                    st.write(sns_scn.get('body', ''))

                    comments = sns_scn.get("sampled_comments")
                    if comments is None:
                        all_c = _normalise_comments(sns_scn.get("comments", []))
                        comments = random.sample(all_c, min(random.choice([2, 3]), len(all_c))) if all_c else []

                    if comments:
                        st.markdown("---")
                        for speaker, comment in comments:
                            st.markdown(f"💬 **{speaker}**: {comment}")
            else:
                st.info("SNS 대화가 없습니다.")


def players_df(room, status, spectator_view=False):
    rows = []
    for p in room["players"].values():
        row = {"팀": p["name"], "현금": fmt(p["cash"])}
        if not spectator_view:
            hold = ", ".join(
                f"{STOCKS[k]['name']} {n}주"
                for k, n in p["holdings"].items() if n
            ) or "-"
            row["보유 주식"] = hold
            row["총 자산"] = fmt(total_value(room, p))

        if status == "trading":
            row["상태"] = "✅ 완료" if p["done"] else "⏳ 거래 중"
        elif status == "result":
            row["상태"] = "라운드 종료"
        elif status == "minigame":
            q = p["quiz"]
            if not q:
                st_txt = "-"
            elif q["solved"] is None:
                st_txt = "⏳ 풀이 중"
            elif q["solved"]:
                st_txt = "⭕ 정답"
            else:
                st_txt = "❌ 오답"
            row["상태"] = st_txt
        rows.append(row)
    return pd.DataFrame(rows)


def spectator_progress_df(room):
    return pd.DataFrame([
        {"참가 팀": player["name"],
         "거래 상태": "✅ 주식 사고팔기 완료" if player["done"] else "⏳ 거래 진행 중"}
        for player in room["players"].values()
    ])


def show_minigame_status_board(room):
    """미니게임 진행 중 진행자와 관전자에게 참가자들의 정오답 현황을 보여줍니다."""
    st.markdown("#### 🎲 참가자 미니게임 풀이 현황")
    rows = []
    for p in room["players"].values():
        q = p["quiz"]
        if not q:
            st_text = "참여 안 함"
        elif q["solved"] is None:
            st_text = "⏳ 풀이 중..."
        elif q["solved"]:
            st_text = "⭕ 정답 맞힘!"
        else:
            st_text = "❌ 오답"
        rows.append({"참가 팀": p["name"], "퀴즈 상태": st_text})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def show_player_holdings(room, player):
    st.markdown("#### 📦 내 보유 주식")
    owned = [(key, qty) for key, qty in player["holdings"].items() if qty > 0]
    if not owned:
        st.caption("현재 보유 중인 주식이 없습니다.")
        return
    rows = []
    for key, qty in owned:
        price = room["prices"][key]
        rows.append({
            "종목": f"{STOCKS[key]['icon']} {STOCKS[key]['name']}",
            "보유 수량": f"{qty}주",
            "현재 주가": fmt(price),
            "평가 금액": fmt(qty * price),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def show_result(room):
    changed = {r["key"]: r for r in room["result"]}
    rows = []
    for k, info in STOCKS.items():
        r = changed.get(k)
        if r and r["new"] != r["old"]:
            diff = r["new"] - r["old"]
            rows.append({
                "종목": f"{info['icon']} {info['name']}",
                "이전 가격": fmt(r["old"]),
                "현재 가격": fmt(r["new"]),
                "가격 변동": fmt_delta(diff),
                "이유": r["reason"],
            })
        else:
            rows.append({
                "종목": f"{info['icon']} {info['name']}",
                "이전 가격": fmt(room["prices"][k]),
                "현재 가격": fmt(room["prices"][k]),
                "가격 변동": "-",
                "이유": "변동 없음",
            })
    st.markdown("#### 📊 이번 라운드 결과")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def market(room, pid, tradable):
    p = room["players"][pid]
    buy_tab, sell_tab = st.tabs(["📈 매수", "📉 매도"])

    def render_stock_trade(side):
        for k, info in STOCKS.items():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2.0, 1.4, 1.6], vertical_alignment="center")
                c1.markdown(f"{info['icon']} **{info['name']}**")
                price = room["prices"][k]
                h = room["history"][k]
                delta = price - h[-2] if len(h) > 1 else 0
                tag = f" :red[(▲ {delta:,}원)]" if delta > 0 else (
                    f" :blue[(▼ {abs(delta):,}원)]" if delta < 0 else ""
                )
                c2.markdown(f"현재가 **{price:,}원**{tag}")
                if side == "buy":
                    c3.caption(f"보유 {p['holdings'][k]}주")
                else:
                    c3.caption(f"매도 가능 {p['holdings'][k]}주")

                q_cols = st.columns([2, 1, 1])
                q_cols[0].number_input(
                    "수량", min_value=1, value=1, step=1,
                    key=f"qty_{side}_{k}", label_visibility="collapsed"
                )
                
                if side == "buy":
                    # 최대 매수 가능 수량 계산 (보유 현금 / 현재 주가)
                    max_buy_qty = p["cash"] // price if price > 0 else 0
                    q_cols[1].button(
                        "매수하기", key=f"btn_buy_{k}",
                        on_click=cb_trade, args=(room, pid, k, "buy", None),
                        disabled=not tradable, use_container_width=True
                    )
                    q_cols[2].button(
                        "최대 매수", key=f"max_buy_{k}",
                        on_click=cb_trade, args=(room, pid, k, "buy", int(max_buy_qty)),
                        disabled=(not tradable or max_buy_qty <= 0), use_container_width=True,
                        help=f"최대 {max_buy_qty}주 매수 가능"
                    )
                else:
                    max_sell_qty = p["holdings"][k]
                    q_cols[1].button(
                        "매도하기", key=f"btn_sell_{k}",
                        on_click=cb_trade, args=(room, pid, k, "sell", None),
                        disabled=(not tradable or p["holdings"][k] == 0), use_container_width=True
                    )
                    q_cols[2].button(
                        "모두 매도", key=f"max_sell_{k}",
                        on_click=cb_trade, args=(room, pid, k, "sell", int(max_sell_qty)),
                        disabled=(not tradable or max_sell_qty <= 0), use_container_width=True,
                        help=f"보유한 {max_sell_qty}주 전량 매도"
                    )

    with buy_tab:
        st.caption("보유 현금 범위 안에서 주식을 매수할 수 있어요.")
        render_stock_trade("buy")
    with sell_tab:
        st.caption("현재 보유하고 있는 주식만 매도할 수 있어요.")
        render_stock_trade("sell")


def show_hints(room, p):
    if room["status"] != "trading":
        return
    hints = [h["text"] for h in p["hints"] if h["round"] == room["round"]]
    if hints:
        with st.container(border=True):
            st.markdown("**🔎 이번 라운드 힌트**")
            for hint in hints:
                st.write("💡 " + hint)


def show_host_round_preview(room):
    current = room.get("current") or {}
    changes = current.get("changes", {})
    if not changes:
        return
    st.markdown("#### 🔐 진행자 전용 · 이번 라운드 주가 변동 미리보기")
    rows = []
    for key, change in changes.items():
        delta_amount, reason = change
        old_price = room["prices"][key]
        expected_new = max(MIN_PRICE, min(MAX_PRICE, old_price + int(delta_amount)))
        actual_diff = expected_new - old_price
        rows.append({
            "변동 종목": f"{STOCKS[key]['icon']} {STOCKS[key]['name']}",
            "예상 방향": "📈 상승" if actual_diff > 0 else ("📉 하락" if actual_diff < 0 else "➖ 보합"),
            "예상 변동 금액": f"{actual_diff:+,}원 (예상가 {expected_new:,}원)",
            "변동 근거": reason,
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("이 정보는 진행자 화면에만 표시되며 참가자와 관전자에게는 공개되지 않습니다.")


def host_panel(room):
    status = room["status"]
    st.divider()
    st.markdown("#### 🎛️ 진행자 패널")
    if status == "lobby":
        st.button("▶️ 게임 시작", on_click=cb_start, args=(room,), type="primary",
                  disabled=not room["players"])
        if not room["players"]:
            st.caption("참가자가 한 명 이상 들어와야 시작할 수 있어요.")
    elif status == "result":
        c1, c2 = st.columns(2)
        c1.button("⏭️ 다음 라운드 진행", on_click=cb_next, args=(room,), type="primary")
        c2.button("🎲 미니게임 실시", on_click=cb_minigame, args=(room,))
    elif status == "minigame":
        st.button("⏭️ 미니게임 종료 · 다음 라운드 시작", on_click=cb_end_minigame, args=(room,), type="primary")
    if status in ("result", "minigame") and room["players"]:
        c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
        c1.selectbox("힌트권을 줄 팀", list(room["players"].keys()), key="grant_pid",
                     format_func=lambda x: room["players"][x]["name"])
        c2.button("🎟️ 힌트권 주기", on_click=cb_grant, args=(room,))
    if status in ("trading", "result", "minigame"):
        st.button("🏁 게임 종료 (전량 매도 후 순위 발표)", on_click=cb_end_game, args=(room,))


def landing():
    st.title("📈 주식 투자 게임")
    st.caption("뉴스·찌라시·SNS를 보고 오를 주식과 내릴 주식을 맞혀 보세요!")
    c1, c2 = st.columns(2)
    c1.button("🏠 방 만들기", on_click=cb_create, type="primary")
    c2.button("🚪 방 참가하기", on_click=cb_join_mode)
    if st.session_state.get("mode") == "join":
        with st.container(border=True):
            st.text_input("방 초대 코드 (알파벳 5자리)", key="join_code", max_chars=5)
            st.radio("참여 방식", ["참가자", "관전자"], key="join_role", horizontal=True)
            if st.session_state.get("join_role", "참가자") == "참가자":
                st.text_input("팀 이름", key="join_name", max_chars=12)
            st.button("게임 참여", on_click=cb_join, type="primary")
            if st.session_state.get("join_error"):
                st.error(st.session_state.join_error)


def restore():
    if "pid" in st.session_state:
        return
    code = st.query_params.get("room")
    pid = st.query_params.get("pid")
    room = ROOMS.get(code) if code else None
    if not room or not pid:
        return
    if pid == room["host_id"]:
        role = "host"
    elif pid in room["players"]:
        role = "player"
    elif pid in room["spectators"]:
        role = "spectator"
    else:
        return
    st.session_state.update(code=code, pid=pid, role=role)


# ─────────────────────────────────────────────
# 실시간 화면
# ─────────────────────────────────────────────
@st.fragment(run_every=POLL_SECONDS)
def live():
    room = ROOMS.get(st.session_state.code)
    if room is None:
        st.error("방을 찾을 수 없어요 (서버가 다시 시작됐을 수 있어요). 나가기를 누르고 다시 시작해 주세요.")
        return
    tick(room)
    role, pid, status = st.session_state.role, st.session_state.pid, room["status"]
    me = room["players"].get(pid)

    if room["round"] > 0 and status != "final":
        st.subheader(f"라운드 {room['round']}")
    if status == "trading":
        remain = max(0, int(room["timer_end"] - time.time()))
        st.progress(remain / ROUND_SECONDS, text=f"⏱️ 남은 시간 {remain // 60:02d}:{remain % 60:02d}")

    # ── 대기방 ──
    if status == "lobby":
        st.subheader("🕐 대기방")
        if role == "host":
            st.info(f"초대 코드: **{room['code']}** — 참가자들에게 알려 주세요!")
        names = [p["name"] for p in room["players"].values()]
        st.write(f"현재 참가자 **{len(names)}명**, 관전자 {len(room['spectators'])}명")
        if names:
            st.write(" · ".join(f"🙋 {n}" for n in names))
        if role != "host":
            st.caption("진행자가 게임을 시작할 때까지 기다려 주세요...")

    # ── 최종 결과 ──
    elif status == "final":
        st.subheader("🏆 최종 결과")
        ranking = sorted(room["players"].values(), key=lambda p: p["cash"], reverse=True)
        medals = ["🥇", "🥈", "🥉"]
        rows = [{"순위": medals[i] if i < 3 else str(i + 1), "팀": p["name"], "최종 현금": fmt(p["cash"])}
                for i, p in enumerate(ranking)]
        if ranking:
            st.success(f"우승: {ranking[0]['name']} 팀!")
        st.dataframe(pd.DataFrame(rows), hide_index=True)

    # ── 진행 중(매매 / 결과 / 미니게임) ──
    else:
        # 신문은 진행자(host)와 관전자(spectator)만 볼 수 있음
        if role in ("host", "spectator"):
            if status == "trading":
                st.markdown("#### 이번 라운드 신문")
                current = room.get("current") or {}
                newspaper(current.get("articles") or current.get("sc") or [])
                if role == "host":
                    done = sum(p["done"] for p in room["players"].values())
                    st.caption(f"거래 완료: {done} / {len(room['players'])}팀")
                    show_host_round_preview(room)
            if status in ("result", "minigame"):
                show_result(room)
                if status == "minigame":
                    show_minigame_status_board(room)
            if role == "spectator" and status == "trading":
                st.markdown("#### 👥 거래 진행 현황")
                st.dataframe(spectator_progress_df(room), hide_index=True)
            elif role == "host" or status in ("result", "final"):
                st.markdown("#### 👥 참가자 현황")
                st.dataframe(
                    players_df(room, status, spectator_view=(role == "spectator")),
                    hide_index=True
                )

        # 참가자(player) 화면
        elif me:
            st.metric("보유 현금", fmt(me["cash"]))
            show_player_holdings(room, me)
            st.metric("총 자산", fmt(total_value(room, me)))
            show_hints(room, me)
            if status == "trading":
                if me["done"]:
                    st.success("거래를 완료했어요. 다른 팀을 기다리는 중...")
                market(room, pid, tradable=not me["done"])
                st.button("✅ 주식 사고 팔기 완료", on_click=cb_done, args=(room, pid),
                          type="primary", disabled=me["done"])
            else:
                show_result(room)
                if status == "minigame":
                    st.markdown("#### 🎲 미니게임")
                    q = me["quiz"]
                    if q is None:
                        st.info("이번 미니게임에는 참여하지 않았어요.")
                    elif q["solved"] is None:
                        st.markdown(f"### {q['q']}")
                        st.number_input("정답 입력", step=1, value=0, key="quiz_ans")
                        st.button("제출", on_click=cb_answer, args=(room, pid), type="primary")
                    elif q["solved"]:
                        st.success("정답! 다음 라운드가 시작되면 힌트가 공개돼요.")
                    else:
                        st.error("아쉽게도 오답이에요.")
                else:
                    st.caption("진행자가 다음 라운드를 시작할 때까지 기다려 주세요...")
        if role == "host":
            host_panel(room)

    if status == "lobby" and role == "host":
        host_panel(room)


# ─────────────────────────────────────────────
# 앱 시작점
# ─────────────────────────────────────────────
st.set_page_config(page_title="주식 투자 게임", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
restore()

if "role" not in st.session_state:
    landing()
else:
    if "room_menu_open" not in st.session_state:
        st.session_state.room_menu_open = True

    if st.session_state.room_menu_open:
        menu_cols = st.columns([0.08, 0.92], vertical_alignment="center")
        if menu_cols[0].button("−", key="room_menu_hide", help="방 정보 접기"):
            st.session_state.room_menu_open = False
            st.rerun()
        with st.container(border=True):
            info_cols = st.columns([1.2, 2, 1.2, 1])
            info_cols[0].caption("방 초대 코드")
            info_cols[0].markdown(f"**`{st.session_state.code}`**")
            info_cols[1].caption("접속 역할")
            info_cols[1].write({"host": "🎛️ 진행자", "player": "🙋 참가자", "spectator": "👀 관전자"}[st.session_state.role])
            info_cols[3].button("나가기", on_click=cb_leave, use_container_width=True)
    else:
        if st.button("＋", key="room_menu_show", help="방 정보 펼치기"):
            st.session_state.room_menu_open = True
            st.rerun()

    st.title("📈 주식 투자 게임")
    live()
