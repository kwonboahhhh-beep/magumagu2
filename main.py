import random
import string
import threading
import time
import uuid

import pandas as pd
import streamlit as st

# ─────────────────────────────────────────────
# 1. 스트림릿 페이지 설정 (반드시 파일 맨 처음에 와야 합니다)
# ─────────────────────────────────────────────
st.set_page_config(page_title="주식 투자 게임", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

# ─────────────────────────────────────────────
# 게임 설정 (여기 숫자만 바꾸면 규칙이 바뀝니다)
# ─────────────────────────────────────────────
START_CASH = 1_000_000      # 시작 예산
START_PRICE = 50_000        # 주식 초기 가격 (최소 5만 원 시작)
MIN_PRICE = 10_000          # 주가 하한 (상한선은 무제한)
PRICE_UP_MIN = 30_000       # 한 라운드 최소 상승 금액
PRICE_UP_MAX = 200_000      # 한 라운드 최대 상승 금액
PRICE_DOWN_MIN = 30_000     # 한 라운드 최소 하락 금액
PRICE_DOWN_MAX = 100_000    # 한 라운드 최대 하락 금액
PRICE_STEP = 1_000          # 가격 변동 단위
MIN_RISING_STOCKS = 2       # 한 라운드에 오르는 종목 최소 개수
MIN_FALLING_STOCKS = 2      # 한 라운드에 내리는 종목 최소 개수
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

KIND_LABEL = {"headline": "📰 헤드라인 기사", "special": "📢 긴급 특보", "sns": "💬 SNS 누리꾼 대화"}
ACCURACY = {"headline": 0.9, "special": 0.6, "sns": 0.40}  # SNS 확률 40%

# 소식 종류별 변동 금액 범위 (전체 범위: 상승 3만~20만 / 하락 3만~10만)
PRICE_DELTA_UP = {
    "headline": (30_000, 120_000),
    "special": (50_000, 160_000),
    "sns": (80_000, 200_000),
}
PRICE_DELTA_DOWN = {
    "headline": (30_000, 70_000),
    "special": (40_000, 90_000),
    "sns": (60_000, 100_000),
}


def sc(kind, title, body, effects, true_reason, fake_reason):
    return dict(kind=kind, title=title, body=body, effects=effects,
                true_reason=true_reason, fake_reason=fake_reason)


def sns(platform, title, body, effects, true_reason, fake_reason, replies):
    """SNS 소식: 플랫폼마다 말투와 반응이 다르고, 댓글은 매번 새로 섞여서 나옵니다.
    replies = [(입장, 댓글)] / 입장: pro(동의) con(반박) joke(드립) ask(질문) info(정정·제보)"""
    s = sc("sns", title, body, effects, true_reason, fake_reason)
    s["platform"] = platform
    s["replies"] = replies
    return s


# 시나리오 (헤드라인 10 / 특보 6 / SNS 12)
SCENARIOS = [
    # ── [헤드라인: 단일 산업 6종] ──
    sc("headline", "정부, 대규모 선박 수주 확정 발표… 조선업계 3년 치 일감 확보",
       "국내 주요 조선사들이 해외 대형 해운사와 총 20조 원 규모의 선박 건조 계약을 체결한 것으로 공식 확인됐다. 업계에 따르면 이번 계약에는 국제해사기구(IMO)의 환경 규제 강화에 발맞춘 친환경 액화천연가스(LNG) 추진선과 초대형 컨테이너선 등이 대거 포함됐으며, 향후 수년에 걸쳐 순차적으로 건조와 인도가 진행될 예정이다.\n\n"
       "조선업계는 이번 대규모 수주가 장기적인 도크 일감 확보는 물론 생산시설 가동률 극대화와 선가 상승으로 이어질 수 있다는 점에서 의미가 매우 크다고 평가하고 있다. 특히 고부가가치 선박 위주의 선별 수주 전략이 본격적으로 결실을 맺으면서 하반기 이후 영업이익률이 뚜렷한 개선세를 보일 것이라는 전망이 우세하다.\n\n"
       "다만 선박 건조에 필수적으로 투입되는 후판 등 철강 원자재 가격의 추이와 숙련 인력 확보 문제, 그리고 글로벌 환율 변동성이 실제 수익성에 영향을 미칠 수 있어 계약 규모만으로 실적 개선을 100% 단정하기는 어렵다는 신중론도 함께 제기된다. 증권가에서는 이번 수주가 향후 추가 발주 기대감과 업종 전반의 주가 흐름에 어떤 영향을 미칠지 예의주시하고 있다.",
       {"ship": +1}, "대규모 수주 확정으로 조선업 실적 기대감이 커졌습니다.",
       "발표와 달리 실제 수주 규모가 크게 줄어 실망 매물이 나왔습니다."),
    sc("headline", "글로벌 AI 기업, 국내 반도체 업체에 차세대 HBM 대량 주문",
       "글로벌 인공지능(AI) 산업의 폭발적인 성장세가 이어지는 가운데 국내 주요 반도체 기업들이 차세대 고대역폭메모리(HBM) 제품의 대규모 공급 주문을 확보한 것으로 전해졌다. AI 데이터센터와 고성능 서버에는 방대한 데이터를 지연 없이 빠르게 처리할 수 있는 고성능 메모리가 필수적으로 탑재되기 때문에 관련 제품의 수요가 공급을 크게 웃돌고 있다.\n\n"
       "업계에서는 이번 주문이 실제 장기 공급 계약과 본격적인 매출 인식으로 이어질 경우 반도체 기업들의 실적 턴어라운드 속도가 한층 빨라질 것으로 보고 있다. 기존 범용 메모리 시장의 재고 조정이 마무리 단계에 접어든 상황에서 고수익 제품군인 HBM의 비중 확대는 전체 영업이익을 견인하는 핵심 동력이 될 전망이다.\n\n"
       "다만 생산능력 확대에 필요한 천문학적인 설비 투자 부담과 해외 경쟁사들의 거센 기술 추격, 글로벌 빅테크 기업들의 데이터센터 투자 속도 조절 가능성은 여전히 변수로 꼽힌다. 시장에서는 단순 주문 규모뿐 아니라 실제 납품 일정과 공정 수율, 평균판매단가 유지 여부를 면밀히 확인해야 한다는 분석이 나온다.",
       {"chip": +1}, "AI 수요 폭증으로 반도체 주문이 늘었습니다.",
       "주문이 갑자기 취소되며 기대감이 꺼졌습니다."),
    sc("headline", "주요 수출국, 수입 자동차 관세 대폭 인상 확정… 완성차 업계 비상",
       "국내 완성차 업계의 핵심 수출 시장 가운데 한 국가가 자국 산업 보호를 명분으로 수입 자동차에 적용하는 관세를 대폭 인상하기로 최종 결정하면서 업계 전반에 긴장감이 고조되고 있다. 관세가 예정대로 시행될 경우 현지 판매 가격이 큰 폭으로 상승하거나 제조사가 관세 비용의 상당 부분을 직접 부담해야 해 가격 경쟁력과 수익성이 동시에 약화될 수 있다는 우려가 나온다.\n\n"
       "특히 해당 수출 시장의 판매 비중이 높은 완성차 기업일수록 영업이익 감소 타격이 클 것으로 예상된다. 완성차 업체들은 현지 공장 생산 물량을 최대한 늘리고 차종별 판매 전략과 프로모션 비용을 전면 재조정하는 등 다각적인 비상 대응 방안을 검토하고 있는 것으로 알려졌다. 부품을 납품하는 협력업체들 역시 수출 물량 감소 여파를 피하기 어려울 전망이다.\n\n"
       "다만 관세의 구체적인 발효 시기와 예외 조항 적용 기준, 향후 양국 간 통상 협상 진행 과정에 따라 실제 기업들이 떠안게 될 부담 수준은 달라질 수 있다. 증권가에서는 당분간 자동차 업종의 투자 심리가 위축될 가능성이 높다며 향후 정부와 업계의 대응책을 지켜봐야 한다고 진단했다.",
       {"car": -1}, "관세 부담으로 자동차 수출 전망이 어두워졌습니다.",
       "관세 시행이 연기되면서 안도 매수가 몰렸습니다."),
    sc("headline", "중앙은행 기준금리 전격 인상… 은행권 예대마진 확대 전망",
       "중앙은행이 물가 안정과 금융 불균형 해소를 위해 기준금리 인상을 최종 결정하면서 국내 은행 및 금융권의 수익 구조에도 큰 변화가 예상된다. 일반적으로 시장 금리가 상승하면 은행이 대출에 적용하는 금리가 예금에 지급하는 금리보다 빠르게 오르면서 이른바 예대마진이 확대되어 단기적으로 이자이익이 크게 증가하는 경향을 보인다.\n\n"
       "이에 따라 주요 시중은행과 금융지주사들의 분기 실적 전망치가 일제히 상향 조정되고 있으며, 배당 확대 등 주주환원 여력 역시 커질 것이라는 긍정적인 분석이 힘을 얻고 있다. 보험사와 증권사 등 여타 금융업권 역시 운용 자산 수익률 개선 효과를 기대할 수 있다는 평가가 나온다.\n\n"
       "그러나 급격한 금리 상승은 가계와 한계 기업의 원리금 상환 부담을 가중시켜 대출 연체율 상승과 부실채권 증가 위험을 키울 수 있다는 점에서 양날의 검으로 작용한다. 금융시장에서는 단기적인 예대마진 확대 효과와 중장기적인 대손충당금 적립 비용 증가 가능성을 균형 있게 따져봐야 한다는 지적이 제기된다.",
       {"fin": +1}, "금리 인상으로 금융권 수익성 개선 기대가 커졌습니다.",
       "대출 연체율 급증 소식이 겹치며 금융주가 약세를 보였습니다."),
    sc("headline", "국제 원자재 가격 폭락… 철강·화학 등 소재 업계 수익성 비상",
       "글로벌 경기 둔화 우려와 주요 소비국의 수요 부진이 겹치면서 국제 원자재 가격이 단기간에 큰 폭으로 하락해 철강·화학 등 국내 재료 및 소재 산업의 경영 환경에 비상이 걸렸다. 통상 원자재 가격이 급락하면 최종 제품 판매 단가 역시 동반 하락 압력을 받게 되며, 기업이 과거 높은 가격에 미리 확보해 둔 원재료 재고를 다량 보유하고 있을 경우 대규모 재고 평가 손실이 발생할 가능성이 크다.\n\n"
       "특히 원료 구매 시점과 제품 출하 시점 사이의 시차가 긴 중후장대 소재 기업일수록 단기적인 실적 변동성과 마진 축소 폭이 확대될 수 있다. 업계에서는 공장 가동률 조절과 고부가가치 특화 소재 비중 확대를 통해 위기를 돌파하려 하고 있으나 단기간에 수익성을 방어하기는 쉽지 않은 상황이다.\n\n"
       "반면 기존 재고 부담이 적고 하락한 가격으로 원료를 새롭게 매입해 가공하는 일부 정밀화학·신소재 기업에는 오히려 원가 절감 요인이 될 수도 있어 같은 업종 내에서도 명암이 엇갈릴 수 있다. 시장에서는 원자재 가격 하락세의 지속 여부와 기업별 재고 관리 수준을 면밀히 살펴야 한다는 의견이 나온다.",
       {"mat": -1}, "원자재 가격 급락으로 재료 기업의 수익성이 악화됐습니다.",
       "예상과 달리 원자재 가격이 반등하며 주가가 올랐습니다."),
    sc("headline", "국내 간판 아이돌 그룹, 미국 빌보드 메인 차트 1위 달성 쾌거",
       "국내 대형 기획사 소속 아이돌 그룹이 세계 최대 음악 시장인 미국 빌보드 메인 싱글 및 앨범 차트에서 동시에 1위를 기록하며 글로벌 대중음악 시장의 역사를 새로 썼다. 이번 성과는 단순한 해외 팬덤의 화제성을 넘어 전 세계 스트리밍 음원 소비와 실물 음반 판매량의 폭발적인 증가로 직결되고 있다는 점에서 엔터테인먼트 업계 전반의 이목을 집중시키고 있다.\n\n"
       "소속사는 이번 빌보드 1위 달성을 계기로 북미와 유럽을 아우르는 대규모 스타디움 월드투어 일정을 추가 편성하고, 글로벌 브랜드 광고 계약 및 IP 기반 굿즈·콘텐츠 유통 사업을 대폭 확대할 계획이다. 업계에서는 핵심 아티스트의 글로벌 위상이 높아질수록 소속사의 연간 매출과 영업이익이 한 단계 도약할 것으로 전망하고 있다.\n\n"
       "다만 차트 흥행 성적이 일회성 이벤트에 그치지 않고 장기적인 기업 가치 상승으로 이어지기 위해서는 후속 앨범의 완성도와 차세대 신인 그룹의 안정적인 세대교체가 뒷받침되어야 한다. 시장에서는 이번 글로벌 성과가 실제 분기 실적과 해외 투어 수익으로 얼마나 빠르게 반영될지 주목하고 있다.",
       {"ent": +1}, "빌보드 1위 소식에 엔터 기업 가치가 올랐습니다.",
       "집계 오류가 확인되어 호재가 사라졌습니다."),

    # ── [헤드라인: 복합 산업 4종] ──
    sc("headline", "친환경 선박 특수에 특수강판·소재 주문까지 동반 급증… 낙수효과 본격화",
       "전 세계 주요 해운사들의 친환경 선박 교체 수요가 본격화되면서 국내 조선업계의 도크가 이미 3년 치 이상의 일감으로 가득 찼다. 이에 따라 선박 건조에 필수적으로 투입되는 고강도 후판과 친환경 연료 탱크용 극저온 특수 소재를 공급하는 국내 철강·화학 재료 기업들의 공장 가동률 역시 덩달아 역대 최고치를 기록하고 있다.\n\n"
       "업계에서는 조선업의 대규모 수주 호황이 후방 소재 산업의 장기 단가 계약과 출하량 증가로 이어지는 전형적인 산업 간 낙수효과가 뚜렷하게 나타나고 있다고 분석한다. 원자재 가격 안정세 속에서 제품 판매 단가 협상까지 유리하게 마무리되면서 조선사와 소재 기업 모두 수익성이 크게 개선될 전망이다.\n\n"
       "증권가에서도 두 산업의 동반 실적 개선 가능성이 매우 높다고 평가하며 관련 종목들을 하반기 최선호주로 꼽고 있다. 다만 향후 공정 지연 여부와 글로벌 해상 물동량 추이가 두 업종의 주가 상승 탄력을 결정지을 핵심 변수가 될 것으로 보인다.",
       {"ship": +1, "mat": +1}, "친환경 선박 수주 호황으로 조선업과 재료산업이 동반 상승했습니다.",
       "원자재 가격 협상 결렬로 두 업종 모두 수익성 우려가 번졌습니다."),
    sc("headline", "차세대 자율주행 전기차 양산 본격화… 차량용 반도체 수요 동반 폭발",
       "국내 대표 완성차 기업들이 레벨3 이상의 고도화된 자율주행 기능을 기본 탑재한 차세대 전기차 신모델 양산에 본격 돌입하면서 자동차와 IT반도체 산업이 동시에 강력한 성장 탄력을 받고 있다. 최신 스마트 전기차 한 대에는 기존 내연기관차보다 수배 이상 많은 고성능 시스템 반도체와 전력 관리 칩, 이미지 센서가 탑재되기 때문이다.\n\n"
       "이에 따라 국내 반도체 설계 및 파운드리 기업들의 차량용 반도체 수주 잔고 역시 가파르게 늘어나며 새로운 캐시카우로 자리 잡고 있다. 완성차 업체와 반도체 기업 간 전략적 기술 제휴가 확대되면서 부품 국산화율 상승과 안정적인 공급망 구축이라는 두 마리 토끼를 모두 잡았다는 평가다.\n\n"
       "전문가들은 완성차 신모델 판매 호조가 곧바로 차량용 반도체 실적 성장으로 직결되는 선순환 구조가 형성되었다고 진단하며, 두 산업 간의 시너지 효과가 향후 증시 전반의 상승 흐름을 주도할 것으로 내다봤다.",
       {"car": +1, "chip": +1}, "자율주행 전기차 양산 호재로 자동차와 반도체 주가가 함께 올랐습니다.",
       "부품 수급 차질로 신차 출고가 지연되며 두 업종 모두 하락했습니다."),
    sc("headline", "당국 가계대출 규제 대폭 강화… 소비 위축으로 문화·엔터 산업까지 직격탄",
       "금융당국이 시중 은행권의 가계대출 총량 관리를 대폭 강화하면서 신규 대출 문턱이 급격히 높아지고 차주들의 이자 상환 부담이 커지고 있다. 이로 인해 은행 등 금융업권은 핵심 수익원인 신규 여신 성장세가 둔화되고 연체율 관리 비용이 늘어날 것이라는 이중고에 직면했다.\n\n"
       "더욱이 고금리와 대출 규제로 가계의 가처분 소득이 줄어들면서 공연 관람, 실물 음반 구매, 유료 팬 플랫폼 결제 등 문화·엔터테인먼트 분야의 소비 심리까지 급격히 얼어붙고 있다는 분석이 나온다. 실제로 일부 기획사의 콘서트 티켓 예매율과 MD 상품 매출 성장세가 둔화되는 조짐이 포착되고 있다.\n\n"
       "시장 전문가들은 강도 높은 금융 규제가 금융권의 수익성 둔화는 물론 소비재·엔터 업계 전반의 실적 압박으로 번지는 연쇄 충격을 유발할 수 있다며 보수적인 접근을 권고했다.",
       {"fin": -1, "ent": -1}, "대출 규제와 소비 위축 여파로 금융업과 엔터업이 동반 하락했습니다.",
       "규제 완화 조짐과 소비 회복세에 두 업종 모두 반등에 성공했습니다."),
    sc("headline", "글로벌 지정학 리스크 고조… 해운·조선 차질 속 국산 대체 소재 반사이익",
       "주요 해상 물류 거점의 지정학적 갈등이 격화되면서 글로벌 선박 발주 일정이 잇따라 연기되고 해상 운임과 선박 보험료가 치솟아 국내 조선업계의 신규 수주 협상에 제동이 걸렸다. 선주사들이 대외 불확실성 해소를 기다리며 발주 결정을 보류하면서 조선업 전반에 단기적인 수주 공백 우려가 커지고 있다.\n\n"
       "반면 각국 정부가 공급망 안보 차원에서 핵심 광물과 산업용 기초 소재의 자국 내 비축량을 대폭 늘리기로 결정하면서 철강·화학·신소재를 생산하는 국내 재료산업에는 대규모 긴급 주문이 쏟아지고 있다. 해외 수입산 소재의 조달이 어려워지자 국내 소재 기업들이 대체 공급처로 급부상하며 반사이익을 톡톡히 누리는 모습이다.\n\n"
       "전문가들은 대외 지정학적 불확실성이 커질수록 수주 지연 우려가 큰 조선업은 위축되는 반면, 공급망 재편 수혜를 입는 소재·재료 업종은 강세를 보이는 뚜렷한 업종별 차별화 장세가 나타날 것이라고 전망했다.",
       {"ship": -1, "mat": +1}, "물류 불안에 조선주는 내리고 공급망 수혜로 재료주는 올랐습니다.",
       "협상 타결 소식에 조선주는 반등하고 재료주는 차익 매물이 나왔습니다."),

    # ── [특보: 1~2줄의 짧고 긴급한 속보 6종] ──
    sc("special", "[특보] 반도체 공장 대규모 정전 사고 발생… 생산 라인 긴급 중단",
       "국내 핵심 반도체 생산 단지에서 정전 사고가 발생해 주요 웨이퍼 공정 라인 가동이 전면 중단됐습니다. 복구 지연 시 출하 차질이 불가피할 전망입니다.",
       {"chip": -1}, "생산 차질 우려로 반도체주가 하락했습니다.",
       "정전은 곧 복구되어 생산에 영향이 없었고 오히려 주가가 올랐습니다."),
    sc("special", "[특보] 대형 조선소 노조, 임금 협상 결렬로 내일 총파업 돌입 선언",
       "국내 대형 조선소 노조가 사측과의 교섭 결렬을 선언하며 전면 총파업에 돌입합니다. 선박 인도 지연에 따른 거액의 배상금 우려가 커지고 있습니다.",
       {"ship": -1}, "파업 우려로 납기 지연 걱정이 커졌습니다.",
       "노사가 극적으로 합의해 파업이 철회되며 주가가 올랐습니다."),
    sc("special", "[찌라시] 신형 플래그십 전기차, 출시 전부터 사전계약 역대 최다 돌파?",
       "국내 완성차 업체의 신형 전기차 사전계약 물량이 예상을 훨씬 뛰어넘어 영업점마다 문의가 폭주하고 있다는 소식입니다.",
       {"car": +1}, "신모델 사전계약이 몰리며 자동차주가 올랐습니다.",
       "사전계약 부진이 알려지며 기대가 꺾였습니다."),
    sc("special", "[특보] 대형 엔터 기획사 대표, 수백억 원대 회삿돈 횡령 혐의 포착",
       "유명 아이돌 소속사 총괄 대표가 회사 자금을 빼돌린 혐의로 검찰 수사를 받고 있다는 소식이 전해지며 오너 리스크가 불거졌습니다.",
       {"ent": -1}, "경영 불확실성에 엔터주가 하락했습니다.",
       "의혹이 사실무근으로 밝혀지며 오히려 주가가 반등했습니다."),
    sc("special", "[찌라시] 시중 대형 은행, 해외 부동산 투자서 수천억 손실 확정설",
       "국내 한 대형 은행이 해외 상업용 부동산 투자 부실로 대규모 손실 처리를 앞두고 있다는 미확인 소문이 증권가에 빠르게 퍼지고 있습니다.",
       {"fin": -1}, "투자 손실 우려로 금융주가 흔들렸습니다.",
       "손실이 미미한 것으로 확인되어 안도감이 퍼졌습니다."),
    sc("special", "[특보] 국내 소재 기업, 전고체 배터리 핵심 신소재 특허 세계 최초 취득",
       "국내 재료 전문 기업이 전고체 배터리의 화재 위험을 없앤 차세대 핵심 소재 원천 특허를 세계 최초로 취득했다고 긴급 공시했습니다.",
       {"mat": +1}, "신소재 기대감에 재료주가 올랐습니다.",
       "특허 분쟁 소식이 나오며 기대가 사라졌습니다."),

    # ── [SNS 12종: 플랫폼·말투·댓글 분위기가 전부 다릅니다] ──
    sns("주식 오픈채팅방", "[캡처] 조선소 다니는 친구가 단톡방에 올린 사진",
        "도크가 꽉 차서 야간 근무까지 늘렸다는데... 이거 수주 터진 거 아니냐?",
        {"ship": +1}, "수주 호조설이 사실로 확인되며 조선주가 올랐습니다.",
        "야간 근무는 단순 수리 물량 때문이었다는 해명이 나와 조선주가 내렸습니다.",
        [("pro", "야간 근무까지 늘었으면 일감이 넘친다는 뜻이지. 이건 신호임"),
         ("pro", "우리 삼촌도 조선소인데 요즘 잔업 엄청 시킨다더라"),
         ("con", "수리 물량 때문에 바쁜 걸 수도 있잖아 ㅋㅋ"),
         ("con", "사진 한 장으로 수주 확정이라니 너무 나갔다"),
         ("joke", "조선소 직원 퇴근 못 하는 게 호재인 세상 ㄷㄷ"),
         ("ask", "혹시 어느 조선소인지 아는 사람?"),
         ("info", "작년에도 비슷한 사진 돌았는데 그땐 별일 없었음")]),
    sns("직장인 익명 앱", "반도체 연구원인데 이번 신공정 결과가 심상치 않다",
        "이번 분기 시험 생산 결과 보고 팀 전체가 술렁였다. 더는 말 못 함. 곧 알게 될 거다.",
        {"chip": +1}, "신공정 수율 개선이 확인되며 반도체주가 올랐습니다.",
        "시험 생산 결과가 기대에 못 미친 것으로 알려져 반도체주가 내렸습니다.",
        [("pro", "'술렁였다'가 좋은 쪽이면 대박인데?"),
         ("pro", "연구원이 이 정도로 흘리면 보통 좋은 소식이더라"),
         ("con", "나쁜 결과였어도 술렁였겠지 ㅋㅋ 방향이 없네"),
         ("con", "인증도 없는 익명글을 왜 믿냐"),
         ("joke", "'더는 말 못 함'이 제일 말 많은 사람 말투임"),
         ("ask", "좋은 쪽 맞음? 나쁜 쪽 맞음? 말을 하다 말아?"),
         ("info", "저 글쓴이 지난번에도 비슷한 글 썼다가 삭제함")]),
    sns("영상 플랫폼 댓글창", "신차 시승 영상 댓글 분위기 미쳤다",
        "'이 가격에 이 성능이면 사야지'가 좋아요 1만 개. 대리점 문의가 폭주한다는 후기도 달리는 중.",
        {"car": +1}, "신차 호평이 실제 계약으로 이어져 자동차주가 올랐습니다.",
        "호평이 광고 효과였고 실제 계약이 부진해 자동차주가 내렸습니다.",
        [("pro", "나도 대리점 전화해 봤는데 대기 걸림"),
         ("pro", "시승 영상 보고 계약한 사람 여기 있음"),
         ("con", "광고 영상 아님? 협찬 티 너무 나는데"),
         ("con", "댓글 좋아요 조작 의심됨. 계정 다 비슷함"),
         ("joke", "영상 보다가 통장 잔고 보고 조용히 끔"),
         ("ask", "실제 계약 대수는 아직 모르는 거지?"),
         ("info", "이 영상 조회수 어제 갑자기 뛴 거 봄")]),
    sns("팬카페 공지 게시판", "[긴급] 소속사 컴백 일정이 또 밀렸다",
        "공지 없이 앨범 발매가 두 번째로 연기됐다. 해외 투어 취소설까지 도는 중.",
        {"ent": -1}, "컴백 연기와 투어 불확실성에 엔터주가 내렸습니다.",
        "연기는 완성도를 높이기 위한 것이어서 오히려 기대감이 커져 엔터주가 올랐습니다.",
        [("pro", "두 번 연기는 진짜 이상하다. 뭔가 있음"),
         ("pro", "투어 취소설까지 돌면 광고 쪽도 흔들릴 듯"),
         ("con", "완성도 올리려고 미룬 거면 오히려 좋은 거 아님?"),
         ("con", "취소설 출처가 어디임? 팬카페 추측글이잖아"),
         ("joke", "컴백 기다리다 군대 다녀오겠다 ㅋㅋ"),
         ("ask", "공식 입장 나온 거 있어?"),
         ("info", "예전에도 연기했다가 더 크게 돌아온 적 있음")]),
    sns("커뮤니티 핫글", "은행 창구 직원인데 요즘 분위기가 이상함",
        "연체 상담이 눈에 띄게 늘었다. 지점장도 회의 때마다 표정이 안 좋다.",
        {"fin": -1}, "연체 증가 우려가 사실로 확인되며 금융주가 내렸습니다.",
        "연체 상담은 일시적이었고 실적이 양호해 금융주가 올랐습니다.",
        [("pro", "요즘 대출 이자 때문에 다들 힘들다던데 맞는 말 같다"),
         ("pro", "우리 지점도 비슷함. 상담 대기 줄 길어졌어"),
         ("con", "한 지점 얘기를 전체로 일반화하면 안 되지"),
         ("con", "은행은 원래 연말이면 상담 늘어남"),
         ("joke", "창구 직원 말이 제일 빠른 경제지표 ㅋㅋ"),
         ("ask", "연체율 통계는 언제 나옴?"),
         ("info", "작년에도 이런 글 올라왔는데 아무 일도 없었음")]),
    sns("주식 오픈채팅방", "철강 공장 쪽 지인 얘긴데 가격 반등 신호래",
        "가동률이 오르고 거래처 주문이 갑자기 늘었다고 함. 오늘 아침 공장 분위기가 달랐다는데.",
        {"mat": +1}, "원자재 수요 반등이 확인되어 재료주가 올랐습니다.",
        "주문 증가는 일시적 재고 확보였고 가격이 다시 약세를 보여 재료주가 내렸습니다.",
        [("pro", "원자재 바닥 찍고 올라오는 느낌 있긴 했음"),
         ("pro", "주문 늘면 단가도 같이 오르지. 논리는 맞네"),
         ("con", "일시적 재고 확보일 수도 있음"),
         ("con", "지인 얘기는 근거가 아님 ㅋㅋ"),
         ("joke", "지인이 이렇게 많은 주식장은 처음 본다"),
         ("ask", "가동률이 정확히 몇 퍼센트 올랐다는 거임?"),
         ("info", "이런 반등설 지난달에도 한 번 돌다 사라짐")]),
    sns("숏폼 영상 댓글", "'차는 중고로 버티고 콘서트에 쓴다' 영상 대유행",
        "'요즘은 신차 대신 구독 서비스랑 콘서트 티켓에 돈 쓴다'는 영상이 조회수 300만을 넘겼다.",
        {"car": -1, "ent": +1}, "소비 트렌드 변화로 엔터주는 오르고 자동차주는 내렸습니다.",
        "유행은 일부 계층에 한정된 얘기여서 자동차주는 오르고 엔터주는 내렸습니다.",
        [("pro", "나도 차 바꿀 돈으로 콘서트 다녀옴. 공감 100%"),
         ("pro", "주변 20대는 차 안 사고 공연 보러 다니던데"),
         ("con", "그건 일부 사람들 얘기고 차 수요가 줄겠냐"),
         ("con", "영상 만든 사람 직업이 뭔데? 콘텐츠 장사하는 사람 같은데"),
         ("joke", "내 통장은 신차도 콘서트도 못 가는 중 ㅋㅋ"),
         ("ask", "이게 실제 판매량에도 나타남?"),
         ("info", "유행어일 뿐이라는 분석도 있음")]),
    sns("경제 유튜버 라이브 채팅", "'금리 오르면 은행은 웃고 반도체는 식는다' 해설 확산",
        "라이브 채팅창에서 금리 인상 → 은행 수익 개선, 성장주 투자 심리 위축이라는 해설이 퍼지는 중.",
        {"fin": +1, "chip": -1}, "금리 기대로 금융주는 오르고 반도체주는 내렸습니다.",
        "금리 인상 기대가 꺾이며 금융주는 내리고 반도체주는 올랐습니다.",
        [("pro", "금리 오르면 은행이 돈 버는 건 교과서임"),
         ("pro", "성장주는 금리에 약하다는 건 맞는 말이지"),
         ("con", "반도체는 금리보다 수요가 더 중요하지 않나?"),
         ("con", "한 유튜버 의견 가지고 포트 짜지 마라"),
         ("joke", "채팅창이 오늘 다 증권사 애널리스트네"),
         ("ask", "금리 인상이 확정된 건 아니지?"),
         ("info", "금리 얘기 나올 때마다 이런 해설 나오긴 함")]),
    sns("물류 단체 대화방", "[캡처] 해운 불안 속에서 철강 공급사만 바쁘다는 얘기",
        "선박 발주 취소 얘기가 도는 와중에 철강 공급사는 긴급 주문을 받고 있다는 캡처가 올라왔다.",
        {"ship": -1, "mat": +1}, "수주 불안에 조선주는 내리고 소재 주문 증가에 재료주는 올랐습니다.",
        "수주 불안은 기우였고 조선주는 오르고 재료주는 차익 매물에 내렸습니다.",
        [("pro", "발주 줄면 조선은 힘들고 소재는 비축 수요로 바쁘지"),
         ("pro", "공급사 쪽 지인도 요즘 정신없다던데"),
         ("con", "조선이랑 철강이 반대로 움직인다는 근거가 약하다"),
         ("con", "캡처 속 대화 날짜가 안 보임"),
         ("joke", "이쪽이 울면 저쪽이 웃는 게 주식이지 뭐"),
         ("ask", "취소된 발주 규모가 실제로 얼마임?"),
         ("info", "과거에도 비슷한 캡처 돌았다가 반만 맞았음")]),
    sns("익명 제보 게시판", "반도체 대표가 해외 기업 인수 협상 중이라던데?",
        "비밀유지 계약 때문에 말 못 한다는데, 이번 주 안에 윤곽 나온대. 법무팀이 야근 중이라는 제보.",
        {"chip": +1}, "인수 협상이 사실로 알려지며 반도체주가 올랐습니다.",
        "인수설이 부인되며 반도체주가 내렸습니다.",
        [("pro", "법무팀 야근은 진짜 신호임. 인수 건 맞을 듯"),
         ("pro", "이번 주 안에 나온다는 게 구체적이라 믿음 간다"),
         ("con", "인수설은 늘 도는 루머잖아"),
         ("con", "해외 기업 이름도 없는 제보를 어떻게 믿냐"),
         ("joke", "인수설 돌 때마다 내 계좌만 인수당함"),
         ("ask", "공시 뜬 거 있으면 알려주세요"),
         ("info", "비슷한 인수설이 작년에도 한 번 있었고 아니었음")]),
    sns("중고차 커뮤니티", "신차 브레이크 결함 제보가 올라오고 있다",
        "같은 모델 차주 몇 명이 비슷한 현상을 올렸다. 아직 공식 발표나 리콜 공지는 없음.",
        {"car": -1}, "리콜 우려가 사실로 확인되며 자동차주가 내렸습니다.",
        "결함 제보는 오해로 밝혀져 자동차주가 올랐습니다.",
        [("pro", "나도 같은 증상 있었음. 센터에서는 정상이라는데"),
         ("pro", "결함 제보가 여러 건이면 리콜 수순 아님?"),
         ("con", "차주 몇 명 얘기로 리콜까지 가진 않음"),
         ("con", "정비 문제를 결함으로 착각하는 경우도 많음"),
         ("joke", "내 차는 브레이크보다 월급이 먼저 안 서더라"),
         ("ask", "공식 센터 답변 받은 사람 있어요?"),
         ("info", "작년에도 비슷한 제보가 있었는데 단순 소모품 문제였음")]),
    sns("재테크 카페", "증권사 직원이 전하는 요즘 계좌 개설 분위기",
        "신규 계좌 개설이 폭주하고 거래량도 평소의 두 배라고 한다. 수수료 수익이 최고일 것 같다는 얘기.",
        {"fin": +1}, "거래대금 급증이 확인되며 금융주가 올랐습니다.",
        "거래 열기가 빠르게 식으며 금융주가 내렸습니다.",
        [("pro", "우리 회사도 신규 고객 문의 폭발임"),
         ("pro", "거래량 늘면 증권사는 무조건 이득이지"),
         ("con", "개설만 많고 실제 거래는 별로일 수도 있음"),
         ("con", "직원이 자기 회사 좋게 말하는 건 당연한 거 아님?"),
         ("joke", "나도 계좌 개설해서 이 파도에 기여 중 ㅋㅋ"),
         ("ask", "이 분위기가 얼마나 갈까요?"),
         ("info", "거래대금은 결국 시장 분위기 따라 빠르게 식음")]),
]

# SNS 댓글 닉네임·공통 댓글 재료 (매번 다른 사람, 다른 말투가 나오도록)
NICK_A = ["존버", "떡상", "개미", "단타", "물린", "눈치", "익명", "새벽", "치킨", "라면", "커피", "야근", "월급", "소액"]
NICK_B = ["러", "왕", "장인", "요정", "지망생", "대장", "수집가", "연구소", "도사", "집사", "청년", "부장"]
GENERIC_REPLIES = {
    "pro": ["{n} 이거 느낌 온다. 나는 간다", "{n} 슬슬 움직일 타이밍 아님?", "{n} 얘기 나올 줄 알았음"],
    "con": ["{n}? 개미 꼬시는 글 냄새남", "출처가 어디임? 캡처만 보고는 못 믿겠는데", "이런 글 믿고 샀다가 물린 사람 한둘이 아님"],
    "joke": ["이 글 보고 사면 꼭 고점이더라 ㅋㅋ", "소문은 소문일 뿐 지갑은 소중하다", "나만 구경만 하다 막차 타는 거냐"],
    "ask": ["혹시 이거 공식 발표 난 거 있음?", "누가 정리 좀 해줘요 ㅠㅠ", "진짜면 지금 사야 하나요?"],
}
POST_TIMES = ["방금 전", "2분 전", "7분 전", "12분 전", "31분 전"]

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
        "timer_end": 0.0, "result": [], "mini_misses": 0, "deck": {},
    }


def new_player(name):
    return {"name": name, "cash": START_CASH, "holdings": {k: 0 for k in STOCKS},
            "done": False, "quiz": None, "hints": []}


def total_value(room, p):
    return p["cash"] + sum(n * room["prices"][k] for k, n in p["holdings"].items())


# ─────────────────────────────────────────────
# 게임 로직
# ─────────────────────────────────────────────
def _rand_step_amount(lo, hi, step=PRICE_STEP):
    return random.randrange(lo, hi + 1, step)


def _fix_delta(delta, fallback_sign):
    """합쳐진 변동 금액을 규칙(상승 3만~20만 / 하락 3만~10만, 1000원 단위)에 맞춘다."""
    if delta == 0:
        delta = fallback_sign * PRICE_UP_MIN
    if delta > 0:
        delta = max(PRICE_UP_MIN, min(PRICE_UP_MAX, delta))
    else:
        delta = -max(PRICE_DOWN_MIN, min(PRICE_DOWN_MAX, -delta))
    return int(round(delta / PRICE_STEP)) * PRICE_STEP


def build_outcome(scenarios):
    changes = {}
    verdicts = []

    for scn in scenarios:
        prob = ACCURACY[scn["kind"]]
        is_true = random.random() < prob
        sign = 1 if is_true else -1

        verdicts.append({
            "kind": scn["kind"],
            "label": KIND_LABEL.get(scn["kind"], scn["kind"]),
            "title": scn["title"],
            "prob": int(prob * 100),
            "is_true": is_true,
        })

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
                dominant = old_delta if abs(old_delta) >= abs(delta_amount) else delta_amount
                combined = _fix_delta(old_delta + delta_amount, 1 if dominant > 0 else -1)
                changes[k] = (combined, old_reason if abs(old_delta) >= abs(delta_amount) else reason)
            else:
                changes[k] = (_fix_delta(delta_amount, final_dir), reason)

    # 오르는 종목 / 내리는 종목이 각각 최소 개수가 되도록 부족한 쪽을 채운다
    others = [k for k in STOCKS if k not in changes]
    random.shuffle(others)

    def add_extra(up):
        k = others.pop()
        if up:
            amount = _rand_step_amount(PRICE_UP_MIN, 80_000)
        else:
            amount = -_rand_step_amount(PRICE_DOWN_MIN, 70_000)
        changes[k] = (amount, random.choice(UP_REASONS if up else DOWN_REASONS))

    ups = sum(1 for d, _ in changes.values() if d > 0)
    downs = sum(1 for d, _ in changes.values() if d < 0)
    while ups < MIN_RISING_STOCKS and others:
        add_extra(True)
        ups += 1
    while downs < MIN_FALLING_STOCKS and others:
        add_extra(False)
        downs += 1
    return changes, verdicts


def _nick(used):
    for _ in range(30):
        n = random.choice(NICK_A) + random.choice(NICK_B) + str(random.randint(1, 99))
        if n not in used:
            used.add(n)
            return n
    return "누리꾼" + str(random.randint(100, 999))


def _reply_likes():
    return min(5000, int(random.expovariate(1 / 90)) + random.randint(0, 25))


def build_sns_thread(scn):
    """SNS 한 건을 '게시글 + 댓글 4~6개'로 만든다. 댓글 구성·순서·닉네임·좋아요가 매번 달라진다."""
    pool = list(scn["replies"])
    pros = [r for r in pool if r[0] == "pro"]
    cons = [r for r in pool if r[0] == "con"]
    picked = []
    if pros:
        picked.append(random.choice(pros))
    if cons:
        picked.append(random.choice(cons))
    rest = [r for r in pool if r not in picked]
    random.shuffle(rest)
    total = random.choice([4, 5, 6])
    picked += rest[:max(0, total - len(picked) - 1)]
    stance = random.choice(["pro", "con", "joke", "ask"])
    stock_name = STOCKS[random.choice(list(scn["effects"]))]["name"]
    picked.append((stance, random.choice(GENERIC_REPLIES[stance]).format(n=stock_name)))
    random.shuffle(picked)

    used = set()
    author = _nick(used)
    replies = [{"nick": _nick(used), "text": text, "likes": _reply_likes()} for _, text in picked]
    return {
        "platform": scn["platform"],
        "author": author,
        "time": random.choice(POST_TIMES),
        "likes": random.randint(300, 9999),
        "shares": random.randint(20, 900),
        "replies": replies,
    }


def _pick_scenario(room, kind):
    """같은 종류의 소식이 한 바퀴 돌 때까지 겹치지 않게 뽑는다."""
    deck = room.setdefault("deck", {})
    if not deck.get(kind):
        pool = [i for i, s in enumerate(SCENARIOS) if s["kind"] == kind]
        random.shuffle(pool)
        deck[kind] = pool
    return SCENARIOS[deck[kind].pop()]


def draw(room):
    selected = []
    for kind in ("headline", "special", "sns"):
        scn = dict(_pick_scenario(room, kind))
        if kind == "sns":
            scn["thread"] = build_sns_thread(scn)
        selected.append(scn)
    changes, verdicts = build_outcome(selected)
    return {
        "sc": selected[0],
        "articles": selected,
        "changes": changes,
        "verdicts": verdicts,
    }


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
        new = max(MIN_PRICE, old + int(delta_amount))
        room["prices"][k] = new
        res.append({"key": k, "old": old, "new": new, "reason": reason})
    for k in STOCKS:
        room["history"][k].append(room["prices"][k])
    room["result"] = res
    room["last_verdicts"] = room["current"].get("verdicts", [])
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
                    st.caption("📢 긴급 특보")
                    st.markdown(f"**{special_scn.get('title', '')}**")
                    st.write(special_scn.get('body', ''))
            else:
                st.info("특보가 없습니다.")

            if sns_scn:
                thread = sns_scn.get("thread")
                with st.container(border=True):
                    platform = thread["platform"] if thread else "SNS"
                    st.caption(f"💬 SNS 누리꾼 대화 · {platform}")
                    st.markdown(f"**{sns_scn.get('title', '')}**")
                    st.write(sns_scn.get('body', ''))
                    if thread:
                        st.caption(f"👤 {thread['author']} · {thread['time']} · ❤️ {thread['likes']:,} · 🔁 {thread['shares']:,}")
                        st.markdown("---")
                        for r in thread["replies"]:
                            st.markdown(f"💬 **{r['nick']}** · ❤️ {r['likes']:,}  \n{r['text']}")
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


def show_result(room, show_verdicts=False):
    """show_verdicts=True 이면 소식 진위 판명 표를 함께 보여준다 (진행자 전용)."""
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
    st.markdown("#### 📊 이번 라운드 주가 결과")
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    verdicts = room.get("last_verdicts", [])
    if show_verdicts and verdicts:
        st.markdown("#### 🔐 진행자 전용 · 이번 라운드 소식 진위 판명 결과")
        v_rows = []
        for v in verdicts:
            v_rows.append({
                "구분": v["label"],
                "소식 제목": v["title"],
                "사실일 확률": f"{v['prob']}%",
                "실제 진위 여부": "⭕ 사실 (진짜 뉴스)" if v["is_true"] else "❌ 거짓 (가짜/루머)",
            })
        st.dataframe(pd.DataFrame(v_rows), hide_index=True, use_container_width=True)
        st.caption("진위 판명 결과는 진행자 화면에만 표시됩니다.")


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
    verdicts = current.get("verdicts", [])
    changes = current.get("changes", {})

    if verdicts:
        st.markdown("#### 🔐 진행자 전용 · 이번 라운드 소식 확률 및 실제 진위 여부")
        v_rows = []
        for v in verdicts:
            v_rows.append({
                "매체 구분": v["label"],
                "소식 제목": v["title"],
                "사실일 확률": f"{v['prob']}%",
                "실제 결과 (진위)": "⭕ 사실 (진짜)" if v["is_true"] else "❌ 거짓 (가짜)",
            })
        st.dataframe(pd.DataFrame(v_rows), hide_index=True, use_container_width=True)

    if changes:
        st.markdown("#### 🔐 진행자 전용 · 이번 라운드 주가 변동 미리보기")
        rows = []
        for key, change in changes.items():
            delta_amount, reason = change
            old_price = room["prices"][key]
            expected_new = max(MIN_PRICE, old_price + int(delta_amount))
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
                show_result(room, show_verdicts=(role == "host"))
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
                show_result(room, show_verdicts=False)
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
