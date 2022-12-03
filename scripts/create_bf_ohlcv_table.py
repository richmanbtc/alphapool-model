# for bigquery upload

import glob
import numpy as np
import pandas as pd
from joblib import Parallel, delayed


def load_trades(filename):
    df = pd.read_csv(filename)

    df = df.rename(columns={
        'amount': 'size',
    })

    for col in ['price', 'size']:
        df[col] = df[col].astype('float')

    df['timestamp'] = df['timestamp'] // 10 ** 6
    df['timestamp_5m'] = (df['timestamp'] // 300) * 300
    df['timestamp_1m'] = (df['timestamp'] // 60) * 60

    df_1m = pd.concat([
        df.groupby('timestamp_1m')['price'].nth(-1).rename('cl'),
    ], axis=1)
    df_1m = df_1m.reset_index()
    df_1m['timestamp_5m'] = (df_1m['timestamp_1m'] // 300) * 300

    df['amount'] = df['price'] * df['size']
    df['buy_volume'] = np.where(df['side'] == 'buy', df['size'], 0)
    df['buy_amount'] = np.where(df['side'] == 'buy', df['amount'], 0)

    df = pd.concat([
        df.groupby('timestamp_5m')['price'].nth(0).rename('op'),
        df.groupby('timestamp_5m')['price'].max().rename('hi'),
        df.groupby('timestamp_5m')['price'].min().rename('lo'),
        df.groupby('timestamp_5m')['price'].nth(-1).rename('cl'),
        df.groupby('timestamp_5m')['size'].sum().rename('volume'),
        df.groupby('timestamp_5m')['amount'].sum(),
        df.groupby('timestamp_5m')['price'].count().rename('trades'),
        df.groupby('timestamp_5m')['buy_volume'].sum(),
        df.groupby('timestamp_5m')['buy_amount'].sum(),
        df_1m.groupby('timestamp_5m')['cl'].mean().rename('twap'),
    ], axis=1)

    df.index.rename('timestamp', inplace=True)
    df['symbol'] = 'FX_BTC_JPY'
    df = df.reset_index().set_index(['timestamp', 'symbol'])
    return df


filenames = list(glob.glob('notebooks/datasets/bitflyer_trades*.gz'))
dfs = [delayed(load_trades)(x) for x in filenames]
dfs = Parallel(n_jobs=-1)(dfs)
df = pd.concat(dfs).sort_index()
df.to_parquet('data/bf_ohlcv.parquet')
