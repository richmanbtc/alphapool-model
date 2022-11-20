# for bigquery upload

import os
import pandas as pd


def get_kraken_data(symbol):
    filename = 'notebooks/Kraken_OHLCVT/{}USD_1.csv'.format(symbol.replace('BTC', 'XBT'))
    if not os.path.exists(filename):
        return pd.DataFrame()
    df = pd.read_csv(
        filename,
        names=['timestamp', 'op', 'hi', 'lo', 'cl', 'volume', 'trades']
    )
    print(df.dtypes)

    df['timestamp_5m'] = (df['timestamp'] // 300) * 300
    df['timestamp_1h'] = (df['timestamp'] // 3600) * 3600

    df_5m = pd.concat([
        df.groupby('timestamp_5m')['cl'].nth(-1),
    ], axis=1)
    df_5m = df_5m.reset_index()
    df_5m['timestamp_1h'] = (df_5m['timestamp_5m'] // 3600) * 3600

    df = pd.concat([
        df.groupby('timestamp_1h')['op'].nth(0),
        df.groupby('timestamp_1h')['hi'].max(),
        df.groupby('timestamp_1h')['lo'].min(),
        df.groupby('timestamp_1h')['cl'].nth(-1),
        df.groupby('timestamp_1h')['volume'].sum(),
        df.groupby('timestamp_1h')['trades'].sum(),
        df_5m.groupby('timestamp_1h')['cl'].mean().rename('twap_5m'),
    ], axis=1)

    df.index.rename('timestamp', inplace=True)

    df['symbol'] = symbol
    df = df.reset_index()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
    df = df.set_index(['timestamp', 'symbol'])
    return df


symbols = 'BTC,ETH,XRP,LINK,ATOM,DOT,SOL,BNB,MATIC,ADA'.split(',')
dfs = list(map(get_kraken_data, symbols))
df = pd.concat(dfs)
df = df.sort_index()
df.to_parquet('data/kraken_historical_ohlcvt.parquet')
