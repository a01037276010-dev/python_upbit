import os
import time
import pandas as pd
import numpy as np
import pyupbit
from dotenv import load_dotenv

# =====================================================================
# 🎛️ [전역 변수] 변동성 지표 백테스팅 & 파라미터 튜닝 설정
# =====================================================================
TOTAL_CANDLES = 2280       # 수집할 1시간 봉 캔들 수 (95일 * 24시간)
BACKTEST_CANDLES = 2160    # 백테스팅에 사용할 실제 데이터 수 (90일 * 24시간)

# 이상치 처리 방식 선택: "QUANTILE" 또는 "IQR"
OUTLIER_METHOD = "QUANTILE"  #"IQR"

# 1) Quantile 방식 설정
QUANTILE_LIMIT = 0.975     # 상위 2.5% 극단 이상치 캡핑 상한선

# 2) IQR 방식 설정 (Q3 + MULTIPLIER * IQR)
IQR_MULTIPLIER = 1.5       # IQR 이상치 계수 (보통 1.5 또는 2.0 사용)

# 3) WMA (가중이동평균) 기간
WMA_WINDOW = 24            # 24시간(1일) 가중이동평균

# 4) 2축 가중치 (신뢰도 x 변동도) 임계값 및 계수 설정
TICK_PCT_HIGH_TH = 0.5     # 1틱 비율이 0.5% 이상이면 저신뢰도로 판단
WEIGHT_LOW_RELIABILITY = 0.7  # 저신뢰도 구간 적용 가중치 계수

VOL_PCT_LOW_TH = 0.3       # 변동률이 0.3% 이하이면 저변동으로 판단
WEIGHT_LOW_VOLATILITY = 0.5   # 저변동 구간 적용 가중치 계수

# ---------------------------------------------------------------------
# 1. 호가 단위 계산 유틸리티 (10원 ~ 100,000원 범위 전용)
# ---------------------------------------------------------------------
def get_tick_size(price: float) -> float:
    """업비트 KRW 마켓 호가 단위 반환 (지정 가격 범위 전용)"""
    if price >= 10000: return 10.0
    if price >= 5000: return 5.0
    if price >= 100: return 1.0   # 100원 이상은 1호가 = 1원
    return 0.1

class VolatilityBacktestEngine:
    def __init__(self):
        load_dotenv('000_key_code.env')
        self.access_key = os.getenv("access_key")
        self.secret_key = os.getenv("secret_key")
        self.upbit = pyupbit.Upbit(self.access_key, self.secret_key)

    # ---------------------------------------------------------------------
    # 2. REST API 페이징을 통한 95일치(2,280개) 1시간 봉 수집 (Volume 포함)
    # ---------------------------------------------------------------------
    def fetch_ohlcv_95days(self, ticker: str) -> pd.DataFrame:
        """업비트 1시간 봉 2,280개(95일) 조회 및 Volume 데이터 동시 수집"""
        dfs = []
        to = None
        target_count = TOTAL_CANDLES
        
        while target_count > 0:
            fetch_cnt = min(target_count, 200)
            df = pyupbit.get_ohlcv(ticker, interval="minute60", count=fetch_cnt, to=to)
            if df is None or df.empty:
                break
            dfs.append(df)
            to = df.index[0]  # 가장 과거 시점으로 'to' 파라미터 갱신
            target_count -= len(df)
            time.sleep(0.08)  # API Rate Limit 보호

        if not dfs:
            return None

        full_df = pd.concat(dfs[::-1])
        full_df = full_df[~full_df.index.duplicated(keep='first')]
        return full_df

    # ---------------------------------------------------------------------
    # 3. 2축 가중치 및 이상치 제어 기반 변동성 지표 산출
    # ---------------------------------------------------------------------
    def compute_advanced_volatility(self, df: pd.DataFrame) -> pd.DataFrame:
        res_df = df.copy()

        # (요구사항 7) 고가 - 시가 데이터 기반 Raw 변동률 (%) 계산
        res_df['raw_vol'] = (res_df['high'] - res_df['open']) / res_df['open'] * 100.0

        # (요구사항 1) 틱 해상도 (Tick %) 계산: 1틱이 몇 %를 차지하는가?
        res_df['tick_size'] = res_df['open'].apply(get_tick_size)
        res_df['tick_pct'] = (res_df['tick_size'] / res_df['open']) * 100.0

        # (요구사항 2) 2축 가중치 산출 (신뢰도 축 x 변동도 축)
        # 축 1: 신뢰도 가중치 (틱 해상도가 낮으면/Tick %가 크면 가중치 감소)
        rel_weight = np.where(res_df['tick_pct'] >= TICK_PCT_HIGH_TH, WEIGHT_LOW_RELIABILITY, 1.0)
        
        # 축 2: 변동도 가중치 (변동률이 너무 낮으면 가중치 감소)
        vol_weight = np.where(res_df['raw_vol'] <= VOL_PCT_LOW_TH, WEIGHT_LOW_VOLATILITY, 1.0)

        # 2축 통합 가중치 적용 변동성
        res_df['weighted_vol'] = res_df['raw_vol'] * rel_weight * vol_weight

        # (요구사항 4 & 6) 이상치 제거 스위칭 (Quantile vs IQR)
        if OUTLIER_METHOD == "QUANTILE":
            # Quantile (Upper Winsorization)
            q_bound = res_df['weighted_vol'].quantile(QUANTILE_LIMIT)
            res_df['filtered_vol'] = np.minimum(res_df['weighted_vol'], q_bound)
            res_df['outlier_bound'] = q_bound

        elif OUTLIER_METHOD == "IQR":
            # IQR 방식 (Q3 + IQR * Multiplier)
            q1 = res_df['weighted_vol'].quantile(0.25)
            q3 = res_df['weighted_vol'].quantile(0.75)
            iqr = q3 - q1
            iqr_bound = q3 + (IQR_MULTIPLIER * iqr)
            res_df['filtered_vol'] = np.minimum(res_df['weighted_vol'], iqr_bound)
            res_df['outlier_bound'] = iqr_bound

        # (요구사항 4) 가중이동평균 (WMA) 계산
        weights = np.arange(1, WMA_WINDOW + 1)
        res_df['vol_wma'] = res_df['filtered_vol'].rolling(WMA_WINDOW).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

        # (요구사항 3) 앞쪽 5일(120개) 워밍업 데이터 제거 후 최근 90일(2,160개) 반환
        res_df_90days = res_df.iloc[-BACKTEST_CANDLES:].copy()
        return res_df_90days

# ---------------------------------------------------------------------
# 4. 실행 및 결과 검증 예시
# ---------------------------------------------------------------------
if __name__ == "__main__":
    engine = VolatilityBacktestEngine()
    test_ticker = "KRW-XRP"
    
    print(f"🚀 [{test_ticker}] 95일 1시간 봉 데이터 수집 시작...")
    raw_data = engine.fetch_ohlcv_95days(test_ticker)
    
    if raw_data is not None and len(raw_data) >= BACKTEST_CANDLES:
        result_df = engine.compute_advanced_volatility(raw_data)
        
        print("\n✅ 백테스트용 90일 변동성 데이터셋 완성!")
        print(f"• 이상치 제거 방식: {OUTLIER_METHOD}")
        print(f"• 최종 데이터 캔들 수: {len(result_df)}개 (정확히 90일치)")
        print(result_df[['open', 'high', 'volume', 'raw_vol', 'tick_pct', 'weighted_vol', 'vol_wma']].tail(10))
