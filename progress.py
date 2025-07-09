import pandas as pd
import numpy as np
from datetime import datetime

def kpi_dataframe(history):
    """
    Convert history (list of dicts) to DataFrame with KPIs.
    Expects keys: 'pace_wpm', 'phoneme_acc', 'syllable_var', 'overall_score', 'timestamp'.
    """
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    # Ensure timestamp is datetime
    if 'timestamp' in df:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df[['timestamp', 'pace_wpm', 'phoneme_acc', 'syllable_var', 'overall_score']].sort_values('timestamp')

def sparkline_data(df, kpi='phoneme_acc', window=10):
    """
    Return last N values for sparkline display.
    """
    if df.empty or kpi not in df:
        return []
    return df[kpi].tail(window).tolist()

def moving_average(df, kpi='phoneme_acc', window=7):
    """
    Compute moving average for a KPI (default: 7-day window).
    """
    if df.empty or kpi not in df:
        return []
    return df[kpi].rolling(window=window, min_periods=1).mean().tolist()

def month_over_month(df, kpi='phoneme_acc'):
    """
    Compute month-over-month improvement for a KPI.
    Returns percent change from previous month.
    """
    if df.empty or kpi not in df:
        return 0.0
    df = df.set_index('timestamp')
    monthly = df[kpi].resample('M').mean()
    if len(monthly) < 2:
        return 0.0
    return ((monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2]) * 100 