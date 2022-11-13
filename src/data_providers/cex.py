import ccxt
from ccxt_rate_limiter import scale_limits, wrap_object
from ccxt_rate_limiter.ftx import ftx_limits, ftx_wrap_defs
from ccxt_rate_limiter.rate_limiter_group import RateLimiterGroup
from crypto_data_fetcher.ftx import FtxFetcher
import pandas as pd


def fetch(options=None, min_timestamp=None):
    df = _fetch_ohlcv(
        symbols=options['symbols'],
        interval_sec=options['interval_sec'],
        price_type=options['price_type'],
        start_time=min_timestamp,
    )
    if min_timestamp is not None:
        df = df.loc[df.index.get_level_values('timestamp') >= pd.to_datetime(min_timestamp, unit='s', utc=True)]
    return df

def _fetch_ohlcv(
        symbols=[],
        interval_sec=60 * 60,
        logger=None,
        price_type="index",
        start_time=None,
):
    dfs = []
    for symbol in symbols:
        fetcher = _create_data_fetcher(logger=logger)
        df = fetcher.fetch_ohlcv(
            df=None,
            start_time=start_time,
            interval_sec=interval_sec,
            market=symbol + "-PERP",
            price_type=price_type,
        )
        df = df.reset_index()

        df["symbol"] = symbol
        df = df.set_index(["timestamp", "symbol"])
        dfs.append(df)
    df = pd.concat(dfs)

    df = df.sort_index()
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
