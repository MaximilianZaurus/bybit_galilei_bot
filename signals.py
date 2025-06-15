{\rtf1\ansi\ansicpg1251\cocoartf2822
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import pandas as pd\
import ta\
\
def analyze_signal(df: pd.DataFrame) -> dict:\
    """\
    \uc0\u1040 \u1085 \u1072 \u1083 \u1080 \u1079  \u1089 \u1080 \u1075 \u1085 \u1072 \u1083 \u1086 \u1074  \u1076 \u1083 \u1103  \u1074 \u1093 \u1086 \u1076 \u1072 /\u1074 \u1099 \u1093 \u1086 \u1076 \u1072  \u1080 \u1079  LONG \u1080  SHORT \u1087 \u1086 \u1079 \u1080 \u1094 \u1080 \u1081 .\
    \uc0\u1048 \u1089 \u1087 \u1086 \u1083 \u1100 \u1079 \u1091 \u1102 \u1090 \u1089 \u1103  RSI, CCI, MACD, Bollinger Bands, \u1086 \u1073 \u1098 \u1105 \u1084 .\
\
    \uc0\u1042 \u1086 \u1079 \u1074 \u1088 \u1072 \u1097 \u1072 \u1077 \u1090  \u1089 \u1083 \u1086 \u1074 \u1072 \u1088 \u1100  \u1089  \u1073 \u1091 \u1083 \u1077 \u1074 \u1099 \u1084 \u1080  \u1092 \u1083 \u1072 \u1075 \u1072 \u1084 \u1080  \u1080  \u1087 \u1086 \u1076 \u1088 \u1086 \u1073 \u1085 \u1086 \u1089 \u1090 \u1103 \u1084 \u1080  \u1076 \u1083 \u1103  \u1076 \u1077 \u1073 \u1072 \u1075 \u1072 .\
    """\
    close = df['close']\
    volume = df['volume']\
\
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()\
    cci = ta.trend.CCIIndicator(df['high'], df['low'], close, window=20).cci()\
\
    macd_ind = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)\
    macd_hist = macd_ind.macd_diff()\
\
    bb_ind = ta.volatility.BollingerBands(close, window=20, window_dev=2)\
    bb_upper = bb_ind.bollinger_hband()\
    bb_lower = bb_ind.bollinger_lband()\
\
    volume_ma = volume.rolling(window=20).mean()\
\
    rsi_curr = rsi.iloc[-1]\
    cci_curr = cci.iloc[-1]\
    macd_hist_curr = macd_hist.iloc[-1]\
    close_curr = close.iloc[-1]\
    bb_upper_curr = bb_upper.iloc[-1]\
    bb_lower_curr = bb_lower.iloc[-1]\
    volume_curr = volume.iloc[-1]\
    volume_ma_curr = volume_ma.iloc[-1]\
\
    macd_hist_trend = macd_hist.iloc[-3:].is_monotonic_increasing\
    macd_hist_fall = macd_hist.iloc[-3:].is_monotonic_decreasing\
\
    long_entry = (\
        (rsi_curr < 30) and\
        (cci_curr < -100) and\
        macd_hist_trend and\
        (close_curr <= bb_lower_curr) and\
        (volume_curr > volume_ma_curr)\
    )\
\
    long_exit = (\
        (rsi_curr > 70) and\
        (cci_curr > 100) and\
        macd_hist_fall and\
        (close_curr >= bb_upper_curr)\
    )\
\
    short_entry = (\
        (rsi_curr > 70) and\
        (cci_curr > 100) and\
        macd_hist_fall and\
        (close_curr >= bb_upper_curr) and\
        (volume_curr > volume_ma_curr)\
    )\
\
    short_exit = (\
        (rsi_curr < 30) and\
        (cci_curr < -100) and\
        macd_hist_trend and\
        (close_curr <= bb_lower_curr)\
    )\
\
    return \{\
        'long_entry': long_entry,\
        'long_exit': long_exit,\
        'short_entry': short_entry,\
        'short_exit': short_exit,\
        'details': \{\
            'rsi': rsi_curr,\
            'cci': cci_curr,\
            'macd_hist': macd_hist_curr,\
            'close': close_curr,\
            'bb_upper': bb_upper_curr,\
            'bb_lower': bb_lower_curr,\
            'volume': volume_curr,\
            'volume_ma': volume_ma_curr\
        \}\
    \}\
}