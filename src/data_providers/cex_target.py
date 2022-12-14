import ccxt
from ccxt_rate_limiter import scale_limits, wrap_object
from ccxt_rate_limiter.ftx import ftx_limits, ftx_wrap_defs
from ccxt_rate_limiter.rate_limiter_group import RateLimiterGroup
from crypto_data_fetcher.ftx import FtxFetcher
import pandas as pd


def fetch(options=None, min_timestamp=None):
    df = _fetch_targets(
        symbols=options['symbols'],
        horizon=options['horizon'],
        start_time=min_timestamp,
    )
    if min_timestamp is not None:
        df = df.loc[df.index.get_level_values('timestamp') >= pd.to_datetime(min_timestamp, unit='s', utc=True)]
    return df


def _fetch_targets(symbols, logger=None, horizon=24, start_time=None):
    dfs = []
    for symbol in symbols:
        fetcher = _create_data_fetcher(logger=logger)
        df = fetcher.fetch_ohlcv(
            df=None,
            start_time=start_time,
            interval_sec=300,
            market=symbol + "-PERP",
            price_type="index",
        )

        df = df.reset_index()

        df["timestamp"] = df["timestamp"].dt.floor("3600S")

        df = pd.concat(
            [
                df.groupby(["timestamp"])["cl"].mean().rename("twap"),
            ],
            axis=1,
        )

        df['ret'] = df["twap"].shift(-horizon - 1) / df["twap"].shift(-1) - 1

        df = df.drop(columns="twap")
        df = df.dropna()

        df = df.reset_index()
        df["symbol"] = symbol
        df = df.set_index(["timestamp", "symbol"])

        dfs.append(df)

    df = pd.concat(dfs)
    return df


def _create_data_fetcher(logger=None):
    ftx_rate_limiter = RateLimiterGroup(limits=scale_limits(ftx_limits(), 0.5))
    client = ccxt.ftx(
        {
            "enableRateLimit": False,
        }
    )
    wrap_object(client, rate_limiter_group=ftx_rate_limiter, wrap_defs=ftx_wrap_defs())
    return FtxFetcher(ccxt_client=client, logger=logger)
