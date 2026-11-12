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
START_PRICE = 50_000        # 주식 초기 가격
MAX_PRICE = 300_000         # 주가 상한
MIN_PRICE = 10_000          # 주가 하한
ROUND_SECONDS = 300         # 매매 시간(5분)
MINIGAME_CHANCE = 0.3       # 라운드 사이 미니게임 확률
MINIGAME_FORCE_AFTER = 4    # 4번 연속 안 나오면 5번째에는 반드시 발생
FALSE_HINT_RATE = 0.1       # 힌트가 거짓일 확률
POLL_SECONDS = 2            # 화면 자동 새로고침 주기

# 종목 이름은 여기서만 바꾸면 됩니다 (나중에 이름을 정하면 name만 수정!)
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
MAGNITUDE = {"headline": (0.08, 0.18), "special": (0.10, 0.25), "sns": (0.25, 0.50)}


def sc(kind, title, body, effects, true_reason, fake_reason):
    return dict(kind=kind, title=title, body=body, effects=effects,
                true_reason=true_reason, fake_reason=fake_reason)


# 16개의 상황: effects = 기사가 암시하는 방향(+1 상승 / -1 하락)
SCENARIOS = [
    sc("headline", "정부, 대규모 선박 수주 확정 발표",
       "국내 조선사들이 해외 해운사와 20조 원 규모의 선박 건조 계약을 체결했다고 정부가 밝혔다.",
       {"ship": +1}, "대규모 수주 확정으로 조선업 실적 기대감이 커졌습니다.",
       "발표와 달리 실제 수주 규모가 크게 줄어 실망 매물이 나왔습니다."),
    sc("headline", "글로벌 AI 기업, 국내 반도체 업체에 HBM 대량 주문",
       "AI 서버 수요가 폭증하면서 국내 반도체 업체에 대규모 주문이 들어왔다.",
       {"chip": +1}, "AI 수요 폭증으로 반도체 주문이 늘었습니다.",
       "주문이 갑자기 취소되며 기대감이 꺼졌습니다."),
    sc("headline", "주요 수출국, 자동차 관세 대폭 인상 확정",
       "가장 큰 수출 시장에서 수입 자동차에 대한 관세를 크게 올리기로 했다.",
       {"car": -1}, "관세 부담으로 자동차 수출 전망이 어두워졌습니다.",
       "관세 시행이 연기되면서 안도 매수가 몰렸습니다."),
    sc("headline", "중앙은행 기준금리 인상… 은행 예대마진 확대 전망",
       "금리 인상으로 은행이 대출 이자로 얻는 수익이 늘어날 것으로 보인다.",
       {"fin": +1}, "금리 인상으로 금융권 수익성 개선 기대가 커졌습니다.",
       "대출 연체율 급증 소식이 겹치며 금융주가 약세를 보였습니다."),
    sc("headline", "원자재 가격 폭락… 철강·화학 업계 비상",
       "국제 원자재 가격이 한 달 새 급락하며 관련 업계의 수익성이 크게 나빠질 전망이다.",
       {"mat": -1}, "원자재 가격 급락으로 재료 기업의 수익성이 악화됐습니다.",
       "예상과 달리 원자재 가격이 반등하며 주가가 올랐습니다."),
    sc("headline", "국내 아이돌 그룹, 빌보드 1위 달성",
       "국내 아이돌 그룹이 미국 빌보드 메인 차트에서 1위를 차지했다.",
       {"ent": +1}, "빌보드 1위 소식에 엔터 기업 가치가 올랐습니다.",
       "집계 오류가 확인되어 호재가 사라졌습니다."),
    sc("special", "[특보] 반도체 공장 대규모 정전 사고",
       "한 반도체 공장에서 대규모 정전이 발생해 생산 라인이 멈췄다는 소식이 전해졌다.",
       {"chip": -1}, "생산 차질 우려로 반도체주가 하락했습니다.",
       "정전은 곧 복구되어 생산에 영향이 없었고 오히려 주가가 올랐습니다."),
    sc("special", "[특보] 조선소 노조 총파업 예고",
       "조선소 노조가 임금 협상 결렬을 이유로 총파업에 들어갈 수 있다는 소식이다.",
       {"ship": -1}, "파업 우려로 납기 지연 걱정이 커졌습니다.",
       "노사가 극적으로 합의해 파업이 철회되며 주가가 올랐습니다."),
    sc("special", "[찌라시] 전기차 신모델, 사전계약 폭주 중?",
       "한 자동차 회사의 신형 전기차가 예상 밖의 인기를 끌고 있다는 얘기가 돈다.",
       {"car": +1}, "신모델 사전계약이 몰리며 자동차주가 올랐습니다.",
       "사전계약 부진이 알려지며 기대가 꺾였습니다."),
    sc("special", "[특보] 대형 소속사 대표 횡령 의혹",
       "엔터 대형 소속사 대표가 회삿돈을 빼돌렸다는 의혹이 제기됐다.",
       {"ent": -1}, "경영 불확실성에 엔터주가 하락했습니다.",
       "의혹이 사실무근으로 밝혀지며 오히려 주가가 반등했습니다."),
    sc("special", "[찌라시] 대형 은행 해외 투자 손실 확대설",
       "한 대형 은행이 해외 부동산 투자에서 큰 손실을 봤다는 소문이다.",
       {"fin": -1}, "투자 손실 우려로 금융주가 흔들렸습니다.",
       "손실이 미미한 것으로 확인되어 안도감이 퍼졌습니다."),
    sc("special", "[특보] 신소재 특허 확보… 재료 기업 주목",
       "국내 재료 기업이 차세대 배터리용 신소재 특허를 확보했다는 소식이다.",
       {"mat": +1}, "신소재 기대감에 재료주가 올랐습니다.",
       "특허 분쟁 소식이 나오며 기대가 사라졌습니다."),
    sc("sns", "@주식고수: 이번에 조선이랑 자동차 둘 다 간다ㅋㅋ",
       "\"내가 아는 사람이 직접 들은 얘기임. 지금 안 사면 후회함 ㅋㅋ\" (좋아요 8천)",
       {"ship": +1, "car": +1}, "소문대로 조선·자동차가 함께 급등했습니다.",
       "소문과 정반대로 조선·자동차가 함께 급락했습니다."),
    sc("sns", "익명 게시판: 반도체 회사 CEO 사임한다던데?",
       "\"곧 공식 발표 나온대. 내부자가 알려줌. 이건 진짜임\" (댓글 2천 개)",
       {"chip": -1}, "CEO 사임 발표로 반도체주가 급락했습니다.",
       "사임설은 가짜 뉴스로 밝혀지며 주가가 급등했습니다."),
    sc("sns", "커뮤니티: 엔터 대박 신인 데뷔한다, 금융주는 곧 폭락각",
       "\"신인 그룹 티저 영상 조회수 미쳤다. 반대로 은행주는 끝났다고 봄\" (공유 1만)",
       {"ent": +1, "fin": -1}, "소문대로 엔터주는 오르고 금융주는 내렸습니다.",
       "소문과 반대로 엔터주는 내리고 금융주는 올랐습니다."),
    sc("sns", "인플루언서: 재료산업 곧 정부 지원금 받는대! 지금이 기회",
       "\"정부 관계자한테 들었음. 영끌각ㅋㅋ 이번엔 진짜\" (팔로워 50만)",
       {"mat": +1}, "정부 지원 소식이 사실로 확인되어 급등했습니다.",
       "지원 소식은 헛소문이었고 실망 매물이 쏟아졌습니다."),
]

UP_REASONS = ["뚜렷한 이유 없이 매수세가 몰렸습니다.", "시장 분위기가 좋아지며 소폭 상승했습니다.",
              "큰 뉴스는 없었지만 투자자들의 기대감이 올랐습니다."]
DOWN_REASONS = ["뚜렷한 이유 없이 차익 실현 매물이 나왔습니다.", "시장 분위기가 가라앉으며 소폭 하락했습니다.",
                "큰 뉴스는 없었지만 투자자들이 불안해했습니다."]


# ─────────────────────────────────────────────
# 서버 공용 저장소 (모든 접속자가 같은 방을 공유)
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
def build_outcome(scn):
    """상황의 실제 결과를 미리 계산 (정보가 진짜일 확률은 종류별로 다름)"""
    is_true = random.random() < ACCURACY[scn["kind"]]
    sign = 1 if is_true else -1
    lo, hi = MAGNITUDE[scn["kind"]]
    changes = {}
    for k, d in scn["effects"].items():
        pct = random.uniform(lo, hi) * d * sign
        changes[k] = (pct, scn["true_reason"] if is_true else scn["fake_reason"])
    # 한 라운드에 변동하는 종목: 최소 2개 ~ 최대 4개 (보통 3개)
    target = min(4, max(len(changes), random.choice([2, 3, 3, 3, 3, 4])))
    others = [k for k in STOCKS if k not in changes]
    random.shuffle(others)
    while len(changes) < target and others:
        k = others.pop()
        up = random.random() < 0.5
        pct = random.uniform(0.03, 0.12) * (1 if up else -1)
        changes[k] = (pct, random.choice(UP_REASONS if up else DOWN_REASONS))
    return changes


def draw(room):
    if not room["order"]:
        room["order"] = random.sample(range(len(SCENARIOS)), len(SCENARIOS))
    scn = SCENARIOS[room["order"].pop()]
    return {"sc": scn, "changes": build_outcome(scn)}


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
    for k, (pct, reason) in room["current"]["changes"].items():
        old = room["prices"][k]
        new = int(round(old * (1 + pct), -2))
        new = max(MIN_PRICE, min(MAX_PRICE, new))
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


def cb_trade(room, pid, k, side):
    qty = int(st.session_state.get(f"qty_{k}", 1))
    with LOCK:
        p = room["players"].get(pid)
        if room["status"] != "trading" or not p or p["done"]:
            st.toast("지금은 거래할 수 없어요.", icon="⛔")
            return
        price = room["prices"][k]
        if side == "buy":
            if price * qty > p["cash"]:
                st.toast("현금이 부족해요. 대출은 금지예요!", icon="🚫")
                return
            p["cash"] -= price * qty
            p["holdings"][k] += qty
            st.toast(f"{STOCKS[k]['name']} {qty}주 매수!", icon="🛒")
        else:
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


def newspaper(scn):
    with st.container(border=True):
        st.caption(KIND_LABEL[scn["kind"]])
        st.markdown(f"### {scn['title']}")
        st.write(scn["body"])


def players_df(room, status):
    rows = []
    for p in room["players"].values():
        hold = ", ".join(f"{STOCKS[k]['name']} {n}주" for k, n in p["holdings"].items() if n) or "-"
        row = {"팀": p["name"], "현금": fmt(p["cash"]), "보유 주식": hold, "총 자산": fmt(total_value(room, p))}
        if status == "trading":
            row["상태"] = "✅ 완료" if p["done"] else "⏳ 거래 중"
        if status == "minigame":
            q = p["quiz"]
            row["미니게임"] = "-" if not q or q["solved"] is None else ("⭕ 정답" if q["solved"] else "❌ 오답")
        rows.append(row)
    return pd.DataFrame(rows)


def show_result(room):
    changed = {r["key"]: r for r in room["result"]}
    rows = []
    for k, info in STOCKS.items():
        r = changed.get(k)
        if r and r["new"] != r["old"]:
            pct = (r["new"] / r["old"] - 1) * 100
            rows.append({"종목": f"{info['icon']} {info['name']}", "이전": fmt(r["old"]), "현재": fmt(r["new"]),
                         "등락": f"{'▲' if pct > 0 else '▼'} {abs(pct):.1f}%", "이유": r["reason"]})
        else:
            rows.append({"종목": f"{info['icon']} {info['name']}", "이전": fmt(room["prices"][k]),
                         "현재": fmt(room["prices"][k]), "등락": "-", "이유": "변동 없음"})
    st.markdown("#### 📊 이번 라운드 결과")
    st.dataframe(pd.DataFrame(rows), hide_index=True)


def stock_info(room, k):
    info = STOCKS[k]
    with st.popover("ⓘ"):
        st.markdown(f"### {info['icon']} {info['name']}")
        st.write(info["desc"])
        h = room["history"][k]
        df = pd.DataFrame({"라운드": range(len(h)), "가격": h}).set_index("라운드")
        st.caption("가격 변동 (0 = 게임 시작)")
        st.line_chart(df)


def market(room, pid, tradable):
    widths = [2.2, 0.8, 1.6, 1.0, 1.3, 0.9, 0.9]
    head = st.columns(widths)
    for c, label in zip(head, ["종목", "정보", "현재가", "보유", "수량", "", ""]):
        c.caption(label)
    p = room["players"][pid]
    for k, info in STOCKS.items():
        c = st.columns(widths, vertical_alignment="center")
        c[0].markdown(f"{info['icon']} **{info['name']}**")
        with c[1]:
            stock_info(room, k)
        price = room["prices"][k]
        h = room["history"][k]
        delta = price - h[-2] if len(h) > 1 else 0
        tag = f" :red[▲{delta:,}]" if delta > 0 else (f" :blue[▼{-delta:,}]" if delta < 0 else "")
        c[2].markdown(f"{price:,}원{tag}")
        c[3].markdown(f"{p['holdings'][k]}주")
        c[4].number_input("수량", min_value=1, value=1, step=1, key=f"qty_{k}", label_visibility="collapsed")
        c[5].button("매수", key=f"buy_{k}", on_click=cb_trade, args=(room, pid, k, "buy"), disabled=not tradable)
        c[6].button("매도", key=f"sell_{k}", on_click=cb_trade, args=(room, pid, k, "sell"), disabled=not tradable)


def show_hints(room, p):
    target = room["round"] if room["status"] == "trading" else room["round"] + 1
    hints = [h["text"] for h in p["hints"] if h["round"] == target]
    if hints:
        title = "이번 라운드 힌트" if room["status"] == "trading" else "다음 라운드 힌트"
        with st.container(border=True):
            st.markdown(f"**🔎 {title}**")
            for t in hints:
                st.write("💡 " + t)


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
# 실시간 화면 (자동 새로고침)
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
        if role in ("host", "spectator"):
            if status == "trading":
                st.markdown("#### 이번 라운드 신문")
                newspaper(room["current"]["sc"])
                done = sum(p["done"] for p in room["players"].values())
                st.caption(f"거래 완료: {done} / {len(room['players'])}팀")
            if status in ("result", "minigame"):
                show_result(room)
            st.markdown("#### 👥 참가자 현황")
            st.dataframe(players_df(room, status), hide_index=True)
        elif me:
            c1, c2 = st.columns(2)
            c1.metric("보유 현금", fmt(me["cash"]))
            c2.metric("총 자산", fmt(total_value(room, me)))
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
                        st.success("정답! 위에 힌트가 도착했어요.")
                    else:
                        st.error("아쉽게도 오답이에요.")
                else:
                    st.caption("진행자가 다음 라운드를 시작할 때까지 기다려 주세요...")
                with st.expander("주식 가격·정보 보기"):
                    market(room, pid, tradable=False)
        if role == "host":
            host_panel(room)

    if status == "lobby" and role == "host":
        host_panel(room)


# ─────────────────────────────────────────────
# 앱 시작점
# ─────────────────────────────────────────────
st.set_page_config(page_title="주식 투자 게임", page_icon="📈", layout="wide")
restore()

if "role" not in st.session_state:
    landing()
else:
    with st.sidebar:
        st.markdown("### 방 초대 코드")
        st.markdown(f"## `{st.session_state.code}`")
        st.write({"host": "🎛️ 진행자", "player": "🙋 참가자", "spectator": "👀 관전자"}[st.session_state.role])
        st.button("나가기", on_click=cb_leave)
    st.title("📈 주식 투자 게임")
    live()
