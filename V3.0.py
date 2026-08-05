from __future__ import annotations

import warnings
warnings.filterwarnings('ignore')

import os
import sys
import time
import asyncio
from decimal import Decimal
from datetime import datetime, timezone, timedelta
import math

import requests
import websockets
import pyupbit
from dotenv import load_dotenv
from upbit import Upbit, AsyncUpbit

# =====================================================================
# [환경 설정] 보안 키 및 외부 연동
# =====================================================================
load_dotenv('000_key_code.env')
ACCESS_KEY = os.getenv("access_key")
SECRET_KEY = os.getenv("secret_key")
DISCORD_URL ="https://discord.com/api/webhooks/1533588335522484284/nC36_YWPjY3jZppcF3H8q_IA3FzvIqXnet23P3oLk7FJYvDtXp5eZ13SS4mYWgJna8qG"


class LightQuant1hEngine:
    def __init__(self):
        """초경량 1시간 봉 시스템 환경 변수 및 상태 저장소를 초기화합니다."""
        
        # 1. 종목 필터링 설정
        self.MIN_PRICE = 10         # 감시 최소 가격 (10원 이상)
        self.MAX_PRICE = 100000     # 감시 최대 가격 (10만 원 이하)
        self.NON_TARGET = []        # 감시 제외 코인 리스트
        self.NOT_SELL = ['KRW', 'APENFT'] # 절대 매도하지 않을 보유 자산
        
        # 2. 필수 데이터 저장소 (과거 캔들 Deque 제거)
        self.target_tickers = []    # 감시 코인 리스트
        self.market_data = {}       # 코인별 필수 실시간 변수 저장소
        self.portfolio = {}         # 보유 중인 매수 포트폴리오
        
        # 3. 자산 관리
        self.virtual_balance = 10_000_000                           # 초기 자본금 (1000만 원)
        self.MAX_SLOTS = 10                                         # 최대 동시 보유 종목 수
        self.UNIT_AMOUNT = self.virtual_balance / self.MAX_SLOTS   # 1슬롯당 금액 (100만 원)


    async def send_discord(self, msg: str):
        """비동기 디스코드 메시지 전송"""
        print(msg) 
        if DISCORD_URL:
            def post():
                try:
                    requests.post(DISCORD_URL, json={'content': msg})
                except Exception:
                    pass
            await asyncio.to_thread(post)


    def init_engine(self):
        """타겟 종목을 선정하고 현재 1시간 봉 시가 1개만 빠르게 세팅합니다."""
        print(f"🔍 [1초 초고속 초기화] 타겟 코인 스캔 및 현재 1시간 봉 시가 세팅 중...")
        
        prices = pyupbit.get_current_price(pyupbit.get_tickers("KRW"))
        
        self.target_tickers = [
            t for t, p in prices.items() 
            if p is not None and self.MIN_PRICE <= p <= self.MAX_PRICE and t not in self.NON_TARGET
        ]
        for ticker in self.target_tickers:
            self.market_data[ticker] = {
                "cur_1h_open": 0,       # 현재 1시간 봉 시가
                "cur_1h_high": 0,       # 현재 1시간 봉 고가
                "cur_1h_low": 0,        # 현재 1시간 봉 저가
                "tick_price": 0       # 현재 1시간 봉 체결가
            }
        print(f"✅ 총 {len(self.target_tickers)}개 코인 준비 완료! 1시간 봉 감시 시작.\n")

    def get_tick_size(self, price: float) -> float:
            """업비트 원화 마켓 호가 단위 계산"""
            if price >= 10000: return 10.0
            if price >= 5000: return 5.0
            if price >= 100: return 1.0  # 100원 이상은 1호가 = 1원
            return 0.1
    
    async def execute_buy(self, ticker: str, price: Decimal, reason: str):
        """가상 매수 실행"""
        if ticker in self.portfolio or ticker in self.NON_TARGET: return
        if self.virtual_balance < self.UNIT_AMOUNT: return 

        buy_amount = (self.UNIT_AMOUNT * 0.9995) / float(price)
        self.virtual_balance -= self.UNIT_AMOUNT
        
        self.portfolio[ticker] = {
            "buy_price": float(price),
            "amount": buy_amount,
            "buy_time": time.time(),
            "entry_1h_open": self.market_data[ticker]["cur_1h_open"],
            "high_after_buy": float(price),       # 매수 후 최고가
            "low_after_buy": float(price),         # 매수 후 최고가 기준 눌림목 최저가
            "trail_price": self.market_data[ticker]["cur_1h_open"],
            "phase": 1,
            "phase3_high": float(price)
        }
        
        msg = f"🔵 **[1시간 봉 매수] {ticker}**\n• 체결가: `{price:,.2f}원`\n• 손절기준(시가): `{self.portfolio[ticker]['entry_1h_open']:,.2f}원`\n• 잔고: `{self.virtual_balance:,.0f}원`\n• 사유: {reason}"
        await self.send_discord(msg)


    async def execute_sell(self, ticker: str, reason: str = "조건 달성"):
        """가상 매도 실행"""
        if ticker in self.NOT_SELL or ticker not in self.portfolio: return

        current_price = float(self.market_data[ticker]["tick_price"])

        amount = self.portfolio[ticker]["amount"]
        buy_price = self.portfolio[ticker]["buy_price"]

        #💡 손익 계산
        pnl = (current_price - buy_price) * amount
        pnl_rate = (pnl / (buy_price * amount)) * 100

        #💡 가상 매도 금액 정산 (수수료 0.05% 적용)
        sell_krw_amount = (current_price * amount) * 0.9995
        self.virtual_balance += sell_krw_amount
        del self.portfolio[ticker]

        icon = "🟢" if pnl > 0 else "🔴"
        msg = f"{icon} **[1시간 봉 매도] {ticker}**\n• 매수가: `{buy_price:,.2f}원`\n• 체결가: `{current_price:,.2f}원`\n• 손익: `{pnl:,.0f}원` ({pnl_rate:.2f}%)\n• 사유: {reason}"
        await self.send_discord(msg)


    async def check_buy_logic(self, ticker: str):
        """[매수 로직] 현재 1시간 봉 시가 대비 현재가가 3% 이상 상승했는가?"""
        if ticker in self.portfolio: return
        
        data = self.market_data[ticker]
        cur_open = data["cur_1h_open"]
        current_price = data["tick_price"]

        tick_size = self.get_tick_size(cur_open)
        cond_tick = (current_price - cur_open) >= (tick_size * 3)
        
        # 💡 현재 1시간 봉 시가 대비 3% 상승 감지
        if (current_price / cur_open) >= 1.03 and cond_tick:
            reason = f"1시간 봉 급등 (+3%↑ / 시가:{cur_open:,.2f}원)"
            await self.execute_buy(ticker, Decimal(str(current_price)), reason=reason)

    async def check_sell_logic(self, ticker: str):
        """[Phase 2 ↔ Phase 3 무한 왕복 유동형 동적 트레일링 스탑]
        Phase 1: 신규 전고점 갱신 시 선형 상승 (헌팅/미세하락 무시)
        Phase 2: 하락 눌림목 진행 시 역제곱(1/x^2) 감쇄 하락
        Phase 3: 바닥 탈출 반등 시 기하급수적(Exponential) 가속 상승
        * 전고점 미경신 파동 구간에서는 Phase 2 ↔ Phase 3를 무한 왕복하며 추적!
        """
        if ticker not in self.portfolio: return
        
        data = self.market_data[ticker]
        buy_info = self.portfolio[ticker]
        current_price = float(data["tick_price"])
        buy_price = buy_info["buy_price"]
        
        if current_price == 0: return

        # 1. 초기값 및 변수 안전 세팅
        stop_line = buy_info.get("entry_1h_open", buy_price * 0.97)
        if "trail_price" not in buy_info:
            buy_info["trail_price"] = stop_line
        if "phase" not in buy_info:
            buy_info["phase"] = 1
        if "phase3_high" not in buy_info:
            buy_info["phase3_high"] = current_price # 3페이즈 내 부분 고점 추적용

        # 2. 실시간 전고점(high) 및 눌림 저점(low) 갱신
        if current_price > buy_info["high_after_buy"]:
            buy_info["high_after_buy"] = current_price
            buy_info["low_after_buy"] = current_price
            buy_info["phase3_high"] = current_price
            buy_info["phase"] = 1  # 🌟 신규 전고점 갱신 시 Phase 1으로 복귀!
            
        if current_price < buy_info["low_after_buy"]:
            buy_info["low_after_buy"] = current_price

        high_price = buy_info["high_after_buy"]
        low_price = buy_info["low_after_buy"]
        current_phase = buy_info["phase"]

        # -----------------------------------------------------------------
        # 🚨 [최후 방어선] 시가 손절선 이탈 시 칼손절 (-3% 내외)
        # -----------------------------------------------------------------
        if current_price < stop_line and current_price <= buy_price:
            reason = f"시가 손절선 이탈 (현재가:{current_price:,.2f}원 < 시가:{stop_line:,.2f}원)"
            await self.execute_sell(ticker, reason=reason)
            return

        # -----------------------------------------------------------------
        # 🚀 [3페이즈 무한 왕복 동적 트레일링 익절] (+3% 이상 상승 시 작동)
        # -----------------------------------------------------------------
        # 🎛️ 하이퍼파라미터 세팅
        K1_LINEAR = 0.50        # Phase 1   : 상승 폭의 50%를 지지선으로 설정
        K2_LINEAR = 0.015       # Phase 2   : 눌림 폭의 1.5%를 지지선으로 설정
        HUNT_LIMIT = 0.02       # 공통       : 고점 대비 2% 초과 하락 시 Phase 2 진입
        K3_EXP_ACCEL = 1.2      # Phase 3: 반등 지수 가속도 계수

        dip_from_high = (high_price - current_price) / high_price
        dip_depth = high_price - low_price
        
        # -------------------------------------------------------------
        # 🔄 [Phase 2 ↔ Phase 3 무한 왕복 전환 판정]
        # -------------------------------------------------------------
        
        # A. Phase 1 ➔ Phase 2 (최초 고점 대비 헌팅 범위를 넘어서 밀릴 때)
        if current_phase == 1 and high_price*(1.0 - HUNT_LIMIT) > current_price:
            current_phase = 2
            buy_info["phase"] = current_phase

        # B. Phase 2 ➔ Phase 3 (하락 중 바닥 대비 반등에 성공할 때)
        if current_phase == 2 and low_price * (1.0 + HUNT_LIMIT) < current_price :
            current_phase = 3
            buy_info["phase"] = current_phase
            buy_info["phase3_high"] = current_price # 반등 고점 추적 시작

        # C. Phase 3 ➔ Phase 2 (반등하다가 전고점 못 뚫고 다시 재하락할 때) 🌟 핵심!
        if current_phase == 3:
            #3페이즈 반등 중 최고가 갱신 시; Phase 3 내 최고점 갱신
            if current_price > buy_info["phase3_high"]:
                buy_info["phase3_high"] = current_price

            # 최고가 갱신 시; Phase 1로 복귀
            if current_price >= high_price:
                current_phase = 1
                buy_info["phase"] = current_phase

            # 반등하다가 3페이즈 고점 대비 HUNT_LIMIT Phase 2로 재전환!
            if current_price < buy_info["phase3_high"] * (1.0 - HUNT_LIMIT):
                current_phase = 2
                buy_info["phase"] = current_phase

        # -------------------------------------------------------------
        # 🎯 [페이즈별 매도선 연산 수식]
        # -------------------------------------------------------------
        
        # 🔵 Phase 1: 신규 고점 갱신 구간 (선형 상승 & 헌팅 무시)
        if current_phase == 1:
            if current_price >= high_price:
                total_gain = high_price - buy_price
                candidate = buy_price + (total_gain * K1_LINEAR)

                # 선형 상승 매도선 설정
                buy_info["trail_price"] = candidate

        # 🔴 Phase 2: 눌림목 하락 구간 (역제곱 감쇄 하락)
        elif current_phase == 2:
            dip_ratio = dip_from_high * 100
            # 눌림이 커질수록 K2_LINEAR/(1 + dip_ratio^2)가 0으로 수렴하여 완만하게 하락
            decay_percent = K2_LINEAR / (dip_ratio ** 2)
            candidate = high_price * (1.0 - decay_percent)
            
            # 완만한 감쇄 매도선 설정
            buy_info["trail_price"] = candidate

        # 🟡 Phase 3: 바닥 다진 후 재반등 구간 (기하급수적 가속 상승)
        elif current_phase == 3:
            reb_ratio = (current_price - low_price) / dip_depth if dip_depth > 0 else 0
            reb_ratio = max(0.0, min(1.0, reb_ratio))
            
            # 지수함수 가속 연산
            exp_factor = math.expm1(reb_ratio * K3_EXP_ACCEL) / math.expm1(K3_EXP_ACCEL)
            candidate = low_price + (dip_depth * exp_factor * 0.60)
            
            # 반등 시 매도선을 위로 당겨 올림
            buy_info["trail_price"] = candidate

        # -----------------------------------------------------------------
        # 💥 [최종 매도 체결 검사]
        # -----------------------------------------------------------------
        if current_price <= buy_info["trail_price"]:
            locked_price = buy_info["trail_price"]
            pnl_rate = ((locked_price - buy_price) / buy_price) * 100
            
            reason = f"{buy_info['phase']}페이즈 동적 익절 (고점:{high_price:,.2f}원 | 매도선:{locked_price:,.2f}원 | 확정수익:+{pnl_rate:.2f}%)"
            await self.execute_sell(ticker, reason=reason)
            return

    async def live_data(self) -> None:
        """웹소켓 실시간 틱 수신 및 1시간 단위 경계 최신화"""

        async with AsyncUpbit() as client:
            await self.send_discord("🚀 **[초경량 1시간 봉 엔진] 실시간 감시 시작...**")
            
            async with client.ws_stream.candle(self.target_tickers, interval="60m") as stream:
                async for event in stream:
                    ticker = event.code
                    data = self.market_data[ticker]
                
                    data["cur_1h_open"] = float(event.opening_price)   # 새 1시간 봉 시가
                    data["cur_1h_high"] = float(event.high_price)   # 새 1시간 봉 고가
                    data["cur_1h_low"] = float(event.low_price)    # 새 1시간 봉 저가
                    data["tick_price"] = float(event.trade_price)  # 새 1시간 봉 체결가

                    # 매매 감시
                    await self.check_sell_logic(ticker) 
                    await self.check_buy_logic(ticker)
                    

    async def run(self):
        """엔진 라이프사이클 관리"""
        self.init_engine()
        
        while True:
            try:
                await self.live_data()
            except websockets.exceptions.ConnectionClosed:
                await asyncio.sleep(3)
            except (asyncio.CancelledError, KeyboardInterrupt):
                break 
            except Exception as e:
                print(f"⚠️ 에러 발생: {e}. 5초 후 재시도...")
                await asyncio.sleep(5)
                    
        # 비상 청산
        await self.send_discord("🚨 **[시스템 종료] 보유 종목 강제 청산**")
        held_tickers = list(self.portfolio.keys())
        for ticker in [t for t in held_tickers if t not in self.NOT_SELL]:
            await self.execute_sell(ticker, reason="종료 비상 매도")
        msg = f"💰 **[초기잔고] {10_000_000:,.0f}원**\n**[최종 잔고] {self.virtual_balance:,.0f}원**\n**[수익률] {(1-self.virtual_balance / 10_000_000) * 100:.2f}%**"
        await self.send_discord(msg)


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    engine = LightQuant1hEngine()
    
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(engine.send_discord("🛑 봇이 완전하게 종료되었습니다."))
