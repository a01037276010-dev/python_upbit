import os
import time
import pandas as pd
import numpy as np
import pyupbit
from dotenv import load_dotenv

class UpbitVolatilityAnalyzer:
    def __init__(self):
        """초경량 1시간 봉 시스템 환경 변수 및 상태 저장소를 초기화합니다."""
        # 1. API 키 설정
        load_dotenv('000_key_code.env')
        self.ACCESS_KEY = os.getenv("access_key")
        self.SECRET_KEY = os.getenv("secret_key")
        self.upbit = pyupbit.Upbit(self.ACCESS_KEY, self.SECRET_KEY)
        
        # 2. 종목 필터링 설정
        self.MIN_PRICE = 10         # 감시 최소 가격 (10원 이상)
        self.MAX_PRICE = 100000     # 감시 최대 가격 (10만 원 이하)
        
        # 3. 데이터 및 변동성 지표 설정
        self.TOTAL_CANDLES = 2280   # 95일치 1시간 봉 (95 * 24 = 2,280)
        self.TRIM_CANDLES = 2160     # 잘라낼 앞쪽 5일치 (2280 - 120(5 * 24))
        self.QUANTILE_LIMIT = 0.975 # Upper Winsorize 상위 2.5% 이상치 제거
        self.WMA_WINDOW = 24        # WMA (가중이동평균) 기간 (24시간)

    def get_filtered_tickers(self):
        """설정한 가격 범위(MIN_PRICE ~ MAX_PRICE)를 만족하는 KRW 마켓 코인 리스트를 반환합니다."""
        print("🔍 업비트 KRW 마켓 종목 및 현재가 조회 중...")
        all_krw_tickers = pyupbit.get_tickers(fiat="KRW")
        
        if not all_krw_tickers:
            print("❌ 원화 마켓 티커 목록을 불러오지 못했습니다.")
            return []

        # 전체 종목 현재가 일괄 조회
        current_prices = pyupbit.get_current_price(all_krw_tickers)
        
        target_tickers = []
        if isinstance(current_prices, dict):
            for ticker, price in current_prices.items():
                if price is not None and self.MIN_PRICE <= price <= self.MAX_PRICE:
                    target_tickers.append(ticker)
        
        print(f"✅ 조건 만족 종목 ({self.MIN_PRICE:,}원 ~ {self.MAX_PRICE:,}원): 총 {len(target_tickers)}개 발견")
        return target_tickers

    def fetch_ohlcv_95days(self, ticker):
        """특정 코인의 95일치(2,280개) 1시간 봉 데이터를 페이징 조회합니다."""
        dfs = []
        to_time = None
        count_per_req = 200
        remaining_candles = self.TOTAL_CANDLES

        while remaining_candles > 0:
            fetch_count = min(remaining_candles, count_per_req)
            df_chunk = pyupbit.get_ohlcv(ticker, interval="minute60", count=fetch_count, to=to_time)
            
            if df_chunk is None or df_chunk.empty:
                break
                
            dfs.append(df_chunk)
            if to_time == df_chunk.index[0]:
                break  # 중복 조회 방지
            to_time = df_chunk.index[0]
            remaining_candles -= len(df_chunk)
            time.sleep(0.08)  # 업비트 REST API 호출 수 제한 방지 (초당 10회 제한 고려)
            print(f"⏳ {ticker}: {len(df_chunk)}개 봉 조회 완료, 남은 봉: {remaining_candles}/2280")

        if not dfs:
            return None

        full_df = pd.concat(dfs[::-1])
        full_df = full_df[~full_df.index.duplicated(keep='first')]
        return full_df

    def compute_volatility(self, df):
        """변동성 지표 계산 후, 워밍업 구간인 앞쪽 5일치(120개)를 제거합니다."""
        # 1) (고가 - 저가) / 종가 %
        raw_vol = (df['high'] - df['low']) / df['close'] * 100
        
        # 2) Upper Quantile Winsorization (이상치 상한선 캡핑)
        q_bound = raw_vol.quantile(self.QUANTILE_LIMIT)
        winsorized_vol = np.minimum(raw_vol, q_bound)
        
        # 3) WMA (가중이동평균) 산출
        weights = np.arange(1, self.WMA_WINDOW + 1)
        vol_wma = winsorized_vol.rolling(self.WMA_WINDOW).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
        
        res_df = df.copy()
        res_df['raw_vol'] = raw_vol
        res_df['winsorized_vol'] = winsorized_vol
        res_df['vol_wma'] = vol_wma
        
        # 4) 앞쪽 5일치(120시간) 제거 후 90일치 반환
        res_df_90days = res_df[-2160:].copy()
        return res_df_90days

    def run(self):
        """조건 만족 종목 전체에 대한 변동성 지표 산출을 진행합니다."""
        target_tickers = self.get_filtered_tickers()
        if not target_tickers:
            return None, None

        volatility_results = {}
        summary_list = []

        print("\n🚀 코인별 95일 캔들 수집 및 90일 변동성 지표 계산 시작...")
        for idx, ticker in enumerate(target_tickers, 1):
            print(f"[{idx}/{len(target_tickers)}] {ticker} 데이터 수집 중...")
            df = self.fetch_ohlcv_95days(ticker)
            
            if df is None or len(df) < 2160:
                print(f"⚠️ {ticker}: 데이터 부족으로 건너뜁니다.")
                continue

            # 변동성 계산 및 5일 잘라내기
            df_vol = self.compute_volatility(df)
            volatility_results[ticker] = df_vol
            
            # 요약 데이터 기록 (현재 가격, 최근 변동성 지표 등)
            latest = df_vol.iloc[-1]
            summary_list.append({
                'ticker': ticker,
                'close_price': latest['close'],
                'raw_vol_latest(%)': round(latest['raw_vol'], 2),
                'vol_wma_latest(%)': round(latest['vol_wma'], 2),
                'vol_wma_mean_90d(%)': round(df_vol['vol_wma'].mean(), 2)
            })

        summary_df = pd.DataFrame(summary_list).sort_values(by='vol_wma_latest(%)', ascending=False)
        return summary_df, volatility_results


# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    analyzer = UpbitVolatilityAnalyzer()
    summary_df, full_data_dict = analyzer.run()

    if summary_df is not None:
        print("\n=======================================================")
        print("📊 [조건 만족 코인 최근 변동성 지표 요약 (상위 10개)]")
        print("=======================================================")
        print(summary_df.head(10).to_string(index=False))import os
import time
import pandas as pd
import numpy as np
import pyupbit
from dotenv import load_dotenv

class UpbitVolatilityAnalyzer:
    def __init__(self):
        """초경량 1시간 봉 시스템 환경 변수 및 상태 저장소를 초기화합니다."""
        # 1. API 키 설정
        load_dotenv('000_key_code.env')
        self.ACCESS_KEY = os.getenv("access_key")
        self.SECRET_KEY = os.getenv("secret_key")
        self.upbit = pyupbit.Upbit(self.ACCESS_KEY, self.SECRET_KEY)
        
        # 2. 종목 필터링 설정
        self.MIN_PRICE = 10         # 감시 최소 가격 (10원 이상)
        self.MAX_PRICE = 100000     # 감시 최대 가격 (10만 원 이하)
        
        # 3. 데이터 및 변동성 지표 설정
        self.TOTAL_CANDLES = 2280   # 95일치 1시간 봉 (95 * 24 = 2,280)
        self.TRIM_CANDLES = 2160     # 잘라낼 앞쪽 5일치 (2280 - 120(5 * 24))
        self.QUANTILE_LIMIT = 0.975 # Upper Winsorize 상위 2.5% 이상치 제거
        self.WMA_WINDOW = 24        # WMA (가중이동평균) 기간 (24시간)

    def get_filtered_tickers(self):
        """설정한 가격 범위(MIN_PRICE ~ MAX_PRICE)를 만족하는 KRW 마켓 코인 리스트를 반환합니다."""
        print("🔍 업비트 KRW 마켓 종목 및 현재가 조회 중...")
        all_krw_tickers = pyupbit.get_tickers(fiat="KRW")
        
        if not all_krw_tickers:
            print("❌ 원화 마켓 티커 목록을 불러오지 못했습니다.")
            return []

        # 전체 종목 현재가 일괄 조회
        current_prices = pyupbit.get_current_price(all_krw_tickers)
        
        target_tickers = []
        if isinstance(current_prices, dict):
            for ticker, price in current_prices.items():
                if price is not None and self.MIN_PRICE <= price <= self.MAX_PRICE:
                    target_tickers.append(ticker)
        
        print(f"✅ 조건 만족 종목 ({self.MIN_PRICE:,}원 ~ {self.MAX_PRICE:,}원): 총 {len(target_tickers)}개 발견")
        return target_tickers

    def fetch_ohlcv_95days(self, ticker):
        """특정 코인의 95일치(2,280개) 1시간 봉 데이터를 페이징 조회합니다."""
        dfs = []
        to_time = None
        count_per_req = 200
        remaining_candles = self.TOTAL_CANDLES

        while remaining_candles > 0:
            fetch_count = min(remaining_candles, count_per_req)
            df_chunk = pyupbit.get_ohlcv(ticker, interval="minute60", count=fetch_count, to=to_time)
            
            if df_chunk is None or df_chunk.empty:
                break
                
            dfs.append(df_chunk)
            if to_time == df_chunk.index[0]:
                break  # 중복 조회 방지
            to_time = df_chunk.index[0]
            remaining_candles -= len(df_chunk)
            time.sleep(0.08)  # 업비트 REST API 호출 수 제한 방지 (초당 10회 제한 고려)
            print(f"⏳ {ticker}: {len(df_chunk)}개 봉 조회 완료, 남은 봉: {remaining_candles}/2280")

        if not dfs:
            return None

        full_df = pd.concat(dfs[::-1])
        full_df = full_df[~full_df.index.duplicated(keep='first')]
        return full_df

    def compute_volatility(self, df):
        """변동성 지표 계산 후, 워밍업 구간인 앞쪽 5일치(120개)를 제거합니다."""
        # 1) (고가 - 저가) / 종가 %
        raw_vol = (df['high'] - df['low']) / df['close'] * 100
        
        # 2) Upper Quantile Winsorization (이상치 상한선 캡핑)
        q_bound = raw_vol.quantile(self.QUANTILE_LIMIT)
        winsorized_vol = np.minimum(raw_vol, q_bound)
        
        # 3) WMA (가중이동평균) 산출
        weights = np.arange(1, self.WMA_WINDOW + 1)
        vol_wma = winsorized_vol.rolling(self.WMA_WINDOW).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
        
        res_df = df.copy()
        res_df['raw_vol'] = raw_vol
        res_df['winsorized_vol'] = winsorized_vol
        res_df['vol_wma'] = vol_wma
        
        # 4) 앞쪽 5일치(120시간) 제거 후 90일치 반환
        res_df_90days = res_df[-2160:].copy()
        return res_df_90days

    def run(self):
        """조건 만족 종목 전체에 대한 변동성 지표 산출을 진행합니다."""
        target_tickers = self.get_filtered_tickers()
        if not target_tickers:
            return None, None

        volatility_results = {}
        summary_list = []

        print("\n🚀 코인별 95일 캔들 수집 및 90일 변동성 지표 계산 시작...")
        for idx, ticker in enumerate(target_tickers, 1):
            print(f"[{idx}/{len(target_tickers)}] {ticker} 데이터 수집 중...")
            df = self.fetch_ohlcv_95days(ticker)
            
            if df is None or len(df) < 2160:
                print(f"⚠️ {ticker}: 데이터 부족으로 건너뜁니다.")
                continue

            # 변동성 계산 및 5일 잘라내기
            df_vol = self.compute_volatility(df)
            volatility_results[ticker] = df_vol
            
            # 요약 데이터 기록 (현재 가격, 최근 변동성 지표 등)
            latest = df_vol.iloc[-1]
            summary_list.append({
                'ticker': ticker,
                'close_price': latest['close'],
                'raw_vol_latest(%)': round(latest['raw_vol'], 2),
                'vol_wma_latest(%)': round(latest['vol_wma'], 2),
                'vol_wma_mean_90d(%)': round(df_vol['vol_wma'].mean(), 2)
            })

        summary_df = pd.DataFrame(summary_list).sort_values(by='vol_wma_latest(%)', ascending=False)
        return summary_df, volatility_results


# ==========================================
# 실행부
# ==========================================
if __name__ == "__main__":
    analyzer = UpbitVolatilityAnalyzer()
    summary_df, full_data_dict = analyzer.run()

    if summary_df is not None:
        print("\n=======================================================")
        print("📊 [조건 만족 코인 최근 변동성 지표 요약 (상위 10개)]")
        print("=======================================================")
        print(summary_df.head(10).to_string(index=False))
