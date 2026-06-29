import time
import datetime
import os
import sys
import requests
import threading
import queue
import logging
import math
from collections import deque
from logging.handlers import RotatingFileHandler
import pyupbit
from dotenv import load_dotenv
import warnings

# 불필요한 시스템 경고 메시지 숨김
warnings.filterwarnings('ignore')

# ==========================================
# ⚙️ [환경 변수 및 API 설정]
# ==========================================
load_dotenv('000_key_code.env')
ACCESS_KEY = os.getenv("access_key")
SECRET_KEY = os.getenv("secret_key")
DISCORD_URL = os.getenv("discode")
# ==========================================
# 🤖 [퀀트 봇 클래스] QuantBot
# ==========================================
class QuantBot:
    def __init__(self):
        # --------------------------------------------------
        # 📊 1. 자산 및 포트폴리오 관리
        # --------------------------------------------------
        self.INITIAL_CAPITAL = 10000000               # 초기 자본금 (1,000만 원)
        self.MAX_SLOTS = 10                           # 최대 동시 보유 종목 수
        self.UNIT_AMOUNT = self.INITIAL_CAPITAL / self.MAX_SLOTS # 1슬롯당 진입 금액 (50만 원)

        # --------------------------------------------------
        # ⏱️ 2. 시스템 타이머 및 큐(Queue) 동적 설정
        # --------------------------------------------------
        self.C_WARMUP_SEC = 60                        # 엔진 웜업 및 데이터 축적 시간 (60초)
        self.C_MAX_HOLD_SEC = 300                     # 최대 보유 시간 (타임아웃 5분)
        self.CUL_TIME = 0.5                           # 심장 스레드 연산 주기 (0.5초)
        self.Q_MAX_LEN = int(self.C_WARMUP_SEC / self.CUL_TIME) # 큐 최대 길이 (120개)

        # --------------------------------------------------
        # 🎯 3. 매수/매도 모멘텀 파라미터
        # --------------------------------------------------
        self.C_STOP_LOSS = -0.015                     # 칼손절 라인 (-1.5%)
        self.C_TRAIL_START = 0.015                    # 트레일링 스탑 가동 시작점 (+1.5%)
        self.C_TRAIL_GAP = 0.010                      # 고점 대비 하락 시 익절폭 (-1.0%)
        
        self.VOL_MULTIPLIER = 2.0                     # [매수조건1] 1초 순간 폭발력 배수
        self.TICK_POWER = 3                           # [매수조건4] 평균가 대비 상승 틱 수 (3틱)
        self.UP_RATIO = 1.01                          # [매수조건4] 평균가 대비 상승 비율 (+1%)

        self.MIN_PRICE = 10                           # 감시 최소 코인 가격
        self.MAX_PRICE = 100000                       # 감시 최대 코인 가격

        # --------------------------------------------------
        # 💾 4. 상태 관리 및 스레드 동기화(Lock) 변수
        # --------------------------------------------------
        self.virtual_balance = self.INITIAL_CAPITAL   # 현재 가상 잔고
        self.virtual_coins = {}                       # 현재 보유 중인 종목 데이터
        self.current_used_slots = 0                   # 현재 사용 중인 슬롯 개수

        self.ticker_db = {}                           # 실시간 코인 틱 데이터베이스
        self.ticker_locks = {}                        # 코인별 개별 Lock (웹소켓 병목 방지용)
        self.trade_lock = threading.Lock()            # 매매 실행 시 계좌 보호용 Lock

        # --------------------------------------------------
        # 🛠️ 5. 비동기 알림(Discord) 및 로깅 시스템 초기화
        # --------------------------------------------------
        self.msg_queue = queue.Queue()                # 비동기 메시지 큐
        self.setup_logging()                          # 로거 세팅
        
        # 큐에 쌓인 작업을 처리할 단일 워커 스레드 백그라운드 가동
        threading.Thread(target=self.async_worker, daemon=True).start()

    # ==========================================
    # 📝 [유틸리티] 로깅 및 알림 함수
    # ==========================================
    def setup_logging(self):
        """CSV 파일 로깅 설정 (파일 용량 초과 시 자동 백업 로테이션)"""
        self.logger = logging.getLogger("QuantBot")
        self.logger.setLevel(logging.INFO)

        handler = RotatingFileHandler("V2_2_trade_log.csv", maxBytes=5*1024*1024, backupCount=5, encoding="utf-8-sig")
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # 파일이 없거나 비어있으면 헤더 작성
        if not os.path.exists("V2_2_trade_log.csv") or os.path.getsize("V2_2_trade_log.csv") == 0:
            self.logger.info("종목,매수시점,매수가격,매도시점,매도가격,이익률,실제손익,구매사유,판매사유")

    def async_worker(self):
        """큐(Queue)에 쌓인 디스코드 발송 및 로그 기록을 순차적으로 처리하는 워커"""
        while True:
            task = self.msg_queue.get()
            if task is None: break

            task_type, data = task
            if task_type == 'discord':
                try:
                    if DISCORD_URL:
                        requests.post(DISCORD_URL, json={'content': data}, timeout=5.0)
                except Exception as e:
                    print(f"⚠️ 디스코드 전송 실패: {e}")
            elif task_type == 'log':
                self.logger.info(data)
            
            self.msg_queue.task_done()

    def send_discord(self, msg):
        """디스코드 메시지를 큐에 삽입"""
        print(msg) # 터미널에도 동시 출력
        self.msg_queue.put(('discord', msg))

    def write_log(self, ticker, b_time, b_price, s_time, s_price, p_rate, p_amt, b_reason, s_reason):
        """매매 결과를 CSV 형식으로 큐에 삽입"""
        log_str = f"{ticker},{b_time},{b_price},{s_time},{s_price},{p_rate:.2f}%,{p_amt:.0f},{b_reason},{s_reason}"
        self.msg_queue.put(('log', log_str))

    def get_tick_size(self, price):
        """업비트 원화 마켓 호가 단위 계산"""
        if price >= 10000: return 10.0
        if price >= 5000: return 5.0
        if price >= 100: return 1.0  # 100원 이상은 1호가 = 1원
        return 0.1

    def initialize_database(self, target_tickers, current_prices):
        """과거 데이터 로딩을 시도하고, 실패하거나 데이터가 부족한 코인은 제외합니다."""
        print("⏳ 초기 거시 추세 데이터(60m) 로딩 중... (약 10초 소요)")
        valid_tickers = []  # 🌟 정상적으로 살아남은 코인만 담을 리스트

        for t in target_tickers:
            initial_macro_q = deque(maxlen=60)
            is_valid = False

            try:
                # 과거 60분 데이터 호출
                df = pyupbit.get_ohlcv(t, interval="minute1", count=60)
                
                # 🌟 [수정됨] 데이터가 정상이고 정확히 60개일 때만 통과
                if df is not None and len(df) == 60:
                    for close_price in df['close']:
                        initial_macro_q.append(close_price)
                    is_valid = True
                else:
                    print(f"⚠️ [{t}] 과거 데이터 부족 (신규 상장 등)으로 감시에서 제외합니다.")
            except Exception as e:
                print(f"⚠️ [{t}] API 호출 에러로 감시에서 제외합니다.")
            
            time.sleep(0.1) # API Rate Limit 보호

            # 🌟 유효한 코인만 데이터베이스에 세팅
            if is_valid:
                self.ticker_db[t] = {
                    'sec_bid': 0.0,
                    'sec_ask': 0.0,
                    'q_bid': deque(maxlen=self.Q_MAX_LEN),
                    'q_ask': deque(maxlen=self.Q_MAX_LEN),
                    'q_price': deque(maxlen=self.Q_MAX_LEN),
                    'prev_vol_speed': 0.0,
                    'last_price': current_prices[t],
                    'has_trade': False,
                    'macro_q': initial_macro_q, 
                    'last_macro_update': time.time()
                }
                self.ticker_locks[t] = threading.Lock()
                valid_tickers.append(t) # 생존자 명단에 추가

        print(f"✅ 총 {len(target_tickers)}개 중 {len(valid_tickers)}개 코인 데이터베이스 세팅 완료")
        return valid_tickers # 🌟 최종 생존 코인 리스트 반환

    # ==========================================
    # 💰 [주문 로직] 매수, 매도, 일괄 청산
    # ==========================================
    def execute_buy(self, ticker, price, reason):
        """가상 매수 실행 및 계좌 업데이트"""
        buy_time = time.time()
        buy_str = datetime.datetime.now().strftime('%H:%M:%S')

        # 🌟 실거래 대비: 수수료 차감 후 업비트 허용 자릿수(소수점 8자리)로 정확히 절사
        raw_vol = (self.UNIT_AMOUNT * 0.9995) / price
        vol = math.floor(raw_vol * 1e8) / 1e8
        
        self.virtual_balance -= self.UNIT_AMOUNT
        self.current_used_slots += 1

        self.virtual_coins[ticker] = {
            'avg': price, 'vol': vol, 'high': price,
            'b_time': buy_time, 'b_str': buy_str, 'reason': reason
        }
        self.send_discord(f"🔵 **[매수] [{buy_str}] {ticker}**\n• 가격: `{price:,.0f}원` | {reason}")

    def evaluate_sell(self, ticker, price):
        """현재 가격을 바탕으로 매도 조건(손절, 익절, 타임아웃) 검사 및 실행"""
        info = self.virtual_coins[ticker]

        # 최고가 갱신 (트레일링 스탑용)
        if price > info['high']:
            info['high'] = price

        profit_rate = (price - info['avg']) / info['avg']
        high_rate = (info['high'] - info['avg']) / info['avg']
        elapsed = time.time() - info['b_time']
        sell_reason = ""

        # 1. 타임아웃 (우선순위 1)
        if elapsed >= self.C_MAX_HOLD_SEC:
            sell_reason = "타임아웃(5m)"
        # 2. 트레일링 익절 (고점 달성 후 일정 폭 하락 시)
        elif high_rate >= self.C_TRAIL_START and price <= info['high'] * (1.0 - self.C_TRAIL_GAP):
            sell_reason = f"트레일링익절(고점:{high_rate*100:.1f}%)"
        # 3. 칼손절
        elif profit_rate <= self.C_STOP_LOSS:
            sell_reason = "칼손절"

        # 매도 사유가 발생했다면 청산 실행
        if sell_reason:
            sell_amt = (info['vol'] * price) * 0.9995 # 매도 수수료 차감
            p_amt = sell_amt - self.UNIT_AMOUNT
            p_rate = (p_amt / self.UNIT_AMOUNT) * 100

            self.virtual_balance += sell_amt
            self.current_used_slots -= 1

            icon = "🟢" if p_amt > 0 else "🔴"
            sell_str = datetime.datetime.now().strftime('%H:%M:%S')

            self.send_discord(f"{icon} **[매도] [{sell_str}] {ticker}**\n• 손익: `{p_amt:,.0f}원` ({p_rate:.2f}%) | {sell_reason}")
            self.write_log(ticker, info['b_str'], info['avg'], sell_str, price, p_rate, p_amt, info['reason'], sell_reason)
            
            del self.virtual_coins[ticker]

    def liquidate_all(self):
        """프로그램 종료 또는 패닉 상황 시 보유 중인 모든 종목을 시장가로 강제 청산"""
        self.send_discord("⚠️ **[시스템 종료] 보유 중인 모든 종목을 시장가로 강제 청산합니다.**")

        with self.trade_lock:
            held_tickers = list(self.virtual_coins.keys())

            if held_tickers:
                for ticker in held_tickers:
                    info = self.virtual_coins[ticker]

                    # 청산 시점의 최신 시장가를 안전하게 획득
                    with self.ticker_locks[ticker]:
                        current_price = self.ticker_db[ticker]['last_price']

                    if current_price == 0:
                        current_price = info['avg']

                    sell_amt = (info['vol'] * current_price) * 0.9995
                    p_amt = sell_amt - self.UNIT_AMOUNT
                    p_rate = (p_amt / self.UNIT_AMOUNT) * 100

                    self.virtual_balance += sell_amt
                    self.current_used_slots -= 1

                    icon = "🟢" if p_amt > 0 else "🔴"
                    sell_str = datetime.datetime.now().strftime('%H:%M:%S')
                    sell_reason = "프로그램 종료(강제청산)"

                    self.send_discord(f"{icon} **[강제청산] [{sell_str}] {ticker}**\n• 손익: `{p_amt:,.0f}원` ({p_rate:.2f}%) | {sell_reason}")
                    self.write_log(ticker, info['b_str'], info['avg'], sell_str, current_price, p_rate, p_amt, info['reason'], sell_reason)

                self.virtual_coins.clear()
            else:
                self.send_discord("ℹ️ 청산할 보유 종목이 없습니다.")
        
        # 일괄 청산 완료 후 최종 성적표 출력
        total_profit = self.virtual_balance - self.INITIAL_CAPITAL
        summary = f"\n📊 **최종 가상 계좌 결과**\n" \
                  f"• 초기 자산: `{self.INITIAL_CAPITAL:,.0f}원`\n" \
                  f"• 최종 자산: `{self.virtual_balance:,.0f}원`\n" \
                  f"• 실현 손익: `{total_profit:,.0f}원` (**{(total_profit/self.INITIAL_CAPITAL)*100:+.2f}%**)"
        
        self.send_discord(summary)


    # ==========================================
    # 💓 [핵심 두뇌] 심장 연산 스레드 (1초 주기)
    # ==========================================
    def heartbeat_engine(self):
        """매 1초마다 슬라이딩 윈도우 데이터를 바탕으로 매수/매도 타점을 계산"""
        engine_start_time = time.time()
        is_warmup_reported = False

        print(f"💓 V2.2 롤링 윈도우 엔진 가동 ({self.C_WARMUP_SEC}초 웜업 대기 시작)")
        tickers = list(self.ticker_db.keys())

        while True:
            start_time = time.time()
            elapsed_global = start_time - engine_start_time
            is_warmed_up = elapsed_global >= self.C_WARMUP_SEC

            if is_warmed_up and not is_warmup_reported:
                self.send_discord(f"✅ **웜업 완료 ({self.C_WARMUP_SEC}초 데이터 축적)**\n🚀 V2.2 실전 매매 감시를 시작합니다.")
                is_warmup_reported = True

            for ticker in tickers:
                
                # --------------------------------------------------
                # 🔒 [STEP 1] Lock 내부: 웹소켓 방해를 최소화하기 위한 빠른 데이터 얕은 복사(Snapshot)
                # --------------------------------------------------
                with self.ticker_locks[ticker]:
                    state = self.ticker_db[ticker]
                    sec_bid = state['sec_bid']
                    sec_ask = state['sec_ask']
                    price = state['last_price']

                    # 1초 동안 쌓인 데이터를 큐에 삽입 (오래된 데이터는 자동 밀어내기)
                    state['q_bid'].append(sec_bid)
                    state['q_ask'].append(sec_ask)
                    state['q_price'].append(price)

                    # 외부에서 무거운 연산을 하기 위해 큐의 스냅샷 복사
                    q_bid_snap = list(state['q_bid'])
                    q_ask_snap = list(state['q_ask'])
                    q_price_snap = list(state['q_price'])

                    snap_price = price
                    snap_q_len = len(state['q_price'])
                    snap_has_trade = state['has_trade']

                    recent_1s_vol = sec_bid + sec_ask
                    vol_accel = recent_1s_vol - state['prev_vol_speed']

                    # 다음 1초를 위한 바구니 초기화
                    state['prev_vol_speed'] = recent_1s_vol
                    state['sec_bid'] = 0.0
                    state['sec_ask'] = 0.0
                    state['has_trade'] = False

                # --------------------------------------------------
                # 🔓 [STEP 2] Lock 외부: 부동소수점 오차 없는 정밀한 합산 (math.fsum)
                # --------------------------------------------------
                snap_roll_bid = math.fsum(q_bid_snap)
                snap_roll_ask = math.fsum(q_ask_snap)
                snap_roll_price = math.fsum(q_price_snap)

                # --------------------------------------------------
                # 🎯 [STEP 3] 매수/매도 타점 평가
                # --------------------------------------------------
                with self.trade_lock:
                    # 보유 중인 코인이면 매도(청산) 조건 우선 검사
                    if ticker in self.virtual_coins:
                        self.evaluate_sell(ticker, snap_price)

                    # 웜업이 덜 되었거나 직전 1초간 거래가 없으면 연산 패스
                    if not snap_has_trade or snap_q_len < self.Q_MAX_LEN:
                        continue

                    # 60초 총 거래량 산출
                    rolling_1m_vol = snap_roll_bid + snap_roll_ask
                    if rolling_1m_vol <= 0:
                        continue

                    # 매수 슬롯 여유가 있을 때만 매수 조건 검사
                    if ticker not in self.virtual_coins and self.current_used_slots < self.MAX_SLOTS:
                        
                        # [매수 조건 1] 1초 순간 폭발 (현재 1초 거래량이 60초 평균치의 N배 초과)
                        cond1_surge = rolling_1m_vol > (recent_1s_vol * (60/self.VOL_MULTIPLIER))

                        # [매수 조건 2] 수급 가속도 (방금 1초 거래량이 직전 1초보다 증가)
                        cond2_accel_up = vol_accel > 0

                        # [매수 조건 3] 60초 체결 강도 (매수세가 전체의 50% 이상)
                        buy_ratio = (snap_roll_bid / rolling_1m_vol) * 100.0
                        cond3_buyer_win = buy_ratio >= 50.0

                        # [매수 조건 4] 가격 상승 돌파 (60초 평균선 대비 N틱 초과 또는 N% 상승)
                        avg_60s_price = snap_roll_price / float(self.Q_MAX_LEN)
                        tick_size = self.get_tick_size(avg_60s_price)
                        
                        cond4_tick = snap_price >= (avg_60s_price + (tick_size * self.TICK_POWER))
                        cond4_pct = snap_price >= (avg_60s_price * self.UP_RATIO)
                        cond4_price_action = cond4_tick and cond4_pct

                        if cond1_surge and cond2_accel_up and cond3_buyer_win and cond4_price_action and is_warmed_up:
                            
                            if self.virtual_balance >= self.UNIT_AMOUNT:
                                self.execute_buy(ticker, snap_price, f"롤링폭발({buy_ratio:.1f}%) & 평균가돌파")
                            else:
                                # 잔고 부족 시 매수 패스 (선택사항: 터미널에 로그만 살짝 띄움)
                                print(f"⚠️ [잔고 부족] {ticker} 매수 타점 포착되었으나 자금 부족으로 패스 (현재잔고: {self.virtual_balance:,.0f}원)")
            # 1초 주기를 정확히 맞추기 위한 휴식 타임
            wait_time = self.CUL_TIME - (time.time() - start_time)
            if wait_time > 0:
                time.sleep(wait_time)

    # ==========================================
    # 🚀 [메인 루프] 봇 가동 및 웹소켓 수신부
    # ==========================================
    def run(self):
        """웹소켓을 연결하고 데이터를 수신하며 예외 상황을 통제하는 메인 함수"""
        self.send_discord("🚀 V2.2 시작 준비 중... (최종 마스터본)")
        # 업비트 원화 마켓 전 종목 조회
        print(pyupbit)
        tickers = pyupbit.get_tickers("KRW")
        current_prices = pyupbit.get_current_price(tickers)

        # 타겟 가격대 필터링
        target_tickers = [t for t, p in current_prices.items() if p is not None and self.MIN_PRICE <= p < self.MAX_PRICE]
        
        # 데이터베이스 사전 세팅
        target_tickers = self.initialize_database(target_tickers, current_prices)

        # 심장 연산 스레드 백그라운드 가동
        threading.Thread(target=self.heartbeat_engine, daemon=True).start()

        # 웹소켓 연결
        wm = pyupbit.WebSocketManager("trade", target_tickers)
        self.send_discord(f"🚀 V2.2 롤링 엔진 가동 (데이터 수집 대기 모드)")

        try:
            while True:
                data = wm.get()
                if not data or 'code' not in data:
                    continue
                t = data['code']
                if t not in self.ticker_db:
                    continue

                # ⚡ 코인별 전용 Lock을 사용하여 웹소켓 병목을 완전히 제거
                with self.ticker_locks[t]:
                    db = self.ticker_db[t]
                    db['last_price'] = data['trade_price']
                    db['has_trade'] = True

                    if data['ask_bid'] == 'BID':
                        db['sec_bid'] += data['trade_volume']
                    else:
                        db['sec_ask'] += data['trade_volume']

        except KeyboardInterrupt:
            print("\n\n⚠️ 사용자 수동 종료 (Ctrl+C)")
        except Exception as e:
            print(f"❌ 시스템 크래시: {e}")
            self.logger.error(f"System Crash: {e}")
        finally:
            if 'wm' in locals() and wm:
                wm.terminate()  # 웹소켓 안전 종료
            self.liquidate_all() # 잔여 코인 강제 청산 및 결과 보고
            self.msg_queue.join() # 큐에 남은 로그 기록 대기
            print("✅ 프로그램이 안전하게 종료되었습니다.")
            sys.exit()

if __name__ == "__main__":
    bot = QuantBot()
    bot.run()
