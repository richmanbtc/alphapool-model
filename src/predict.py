import os
import re
import time
import joblib
import pandas as pd
import pandas_ta as ta # required to load models using df.ta.xxx
import traceback
import dataset
from retry import retry
import pandas_market_calendars as mcal
from alphapool import Client
from .logger import create_logger
from .data_fetcher import DataFetcher

model_id = os.getenv("ALPHAPOOL_MODEL_ID")
model_path = os.getenv("ALPHAPOOL_MODEL_PATH")
log_level = os.getenv("ALPHAPOOL_LOG_LEVEL")
logger = create_logger(log_level)

# if not re.match(r"^[a-z_][a-z0-9_]{3,30}$", model_id):
#     raise Exception("model_id must be ^[a-z_][a-z0-9_]{3,30}$")


@retry(tries=3, delay=3, logger=logger)
def predict_job(dry_run=False):
    model = joblib.load(model_path)

    horizon = model.horizon if hasattr(model, 'horizon') else 24
    logger.info('horizon {}'.format(horizon))

    provider_configs = model.provider_configs
    logger.info('provider_configs {}'.format(provider_configs))

    exchange = model.exchange if hasattr(model, 'exchange') else None
    logger.info('exchange {}'.format(exchange))

    mode = model.mode if hasattr(model, 'mode') else None
    logger.info('mode {}'.format(mode))

    database_url = os.getenv("ALPHAPOOL_DATABASE_URL")
    db = dataset.connect(database_url)
    client = Client(db)

    # fetch data
    interval_sec = 60 * 60
    max_timestamp = (int(time.time()) // interval_sec) * interval_sec - interval_sec
    dfs = DataFetcher(sequential=True).fetch(
        provider_configs=provider_configs,
        min_timestamp=int(max_timestamp - model.max_data_sec),
    )
    df = model.merge_data(dfs)
    max_timestamp = df.index.get_level_values("timestamp").max()
    logger.info('max_timestamp {}'.format(max_timestamp))

    # predict
    predict_result = model.predict(df)
    if len(predict_result.shape) == 1:
        df["position"] = predict_result
    else:
        for col in predict_result.columns:
            df[col] = predict_result[col]
    logger.debug(df)

    # submit
    if dry_run:
        logger.info("dry run submit {}".format(df))
        return

    if len(predict_result.shape) == 1:
        timestamp_idx = df.index.get_level_values("timestamp")
        df_start = df.loc[
            (max_timestamp - pd.to_timedelta(horizon + 1, unit="H") < timestamp_idx)
            & (timestamp_idx <= max_timestamp - pd.to_timedelta(1, unit="H"))
        ]
        df_end = df.loc[
            (max_timestamp - pd.to_timedelta(horizon, unit="H") < timestamp_idx)
            & (timestamp_idx <= max_timestamp)
        ]

        df_start = df_start.groupby("symbol")["position"].mean()
        df_end = df_end.groupby("symbol")["position"].mean()

        for i in range(1, 13):
            t = i / 12.0
            logger.debug('submit {}'.format(i))
            client.submit(
                model_id=model_id,
                exchange=exchange,
                timestamp=int(
                    (
                        max_timestamp
                        + pd.to_timedelta(1, unit="H")
                        + i * pd.to_timedelta(5, unit="minutes")
                    ).timestamp()
                ),
                positions=(df_start * (1.0 - t) + df_end * t).to_dict(),
            )
    elif mode == 'stock':
        jpx = mcal.get_calendar('JPX')
        start_date = (max_timestamp + pd.to_timedelta(1, unit='D'))
        next_schedule = jpx.schedule(
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=(start_date + pd.to_timedelta(30, unit='D')).strftime('%Y-%m-%d'),
        )
        next_op_timestamp = int(next_schedule.index[0].timestamp())

        df_last = df.loc[df.index.get_level_values('timestamp') == max_timestamp]

        x = df_last.groupby("symbol")["position_op"].mean()
        client.submit(
            model_id=model_id,
            exchange=exchange,
            timestamp=next_op_timestamp,
            positions=x.loc[x != 0].to_dict(),
        )
        x = df_last.groupby("symbol")["position_cl"].mean()
        client.submit(
            model_id=model_id,
            exchange=exchange,
            timestamp=next_op_timestamp + 6 * 60 * 60,
            positions=x.loc[x != 0].to_dict(),
        )
    else:
        orders = {}

        for symbol, df_symbol in df.groupby('symbol'):
            last_row = df_symbol.iloc[-1]
            order_list = []
            if last_row['buy_amount'] > 0:
                order_list.append({
                    "price": last_row['buy_price'],
                    "amount": last_row['buy_amount'],
                    "duration": 60 * 60,
                    "is_buy": True,
                })
            if last_row['sell_amount'] > 0:
                order_list.append({
                    "price": last_row['sell_price'],
                    "amount": last_row['sell_amount'],
                    "duration": 60 * 60,
                    "is_buy": False,
                })
            if len(order_list) > 0:
                orders[symbol] = order_list

        if len(orders) > 0:
            client.submit(
                model_id=model_id,
                exchange=exchange,
                timestamp=int(
                    (
                            max_timestamp
                            + pd.to_timedelta(1, unit="H")
                            + pd.to_timedelta(5, unit="minutes")
                    ).timestamp()
                ),
                orders=orders,
            )
