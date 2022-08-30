import os
import re
import joblib
import numpy as np
import pandas as pd
import traceback
from .logger import create_logger
from .ml_utils import fetch_ohlcv, normalize_position

model_id = os.getenv("ALPHAPOOL_MODEL_ID")
model_path = os.getenv("ALPHAPOOL_MODEL_PATH")
log_level = os.getenv("ALPHAPOOL_LOG_LEVEL")

if not re.match(r"^[a-z_][a-z0-9_]{3,30}$", model_id):
    raise Exception("model_id must be ^[a-z_][a-z0-9_]{3,30}$")


def predict_job(client, dry_run=False):
    logger = create_logger(log_level)
    model = joblib.load(model_path)

    # fetch data
    interval_sec = 60 * 60
    max_retry_count = 5
    for _ in range(max_retry_count):
        try:
            df = fetch_ohlcv(
                symbols=model.symbols, logger=logger, interval_sec=interval_sec
            )
            max_timestamp = df.index.get_level_values("timestamp").max()
            df = df.loc[
                max_timestamp - pd.to_timedelta(model.max_data_sec, unit="S")
                <= df.index.get_level_values("timestamp")
            ]
            break
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())
            logger.info("fetch_ohlcv error. retrying")

    # predict
    df["position"] = model.predict(df)
    normalize_position(df)

    # submit
    if dry_run:
        logger.info("dry run submit {}".format(df))
    else:
        timestamp_idx = df.index.get_level_values("timestamp")
        df_start = df.loc[
            (max_timestamp - pd.to_timedelta(25, unit="H") <= timestamp_idx)
            & (timestamp_idx <= max_timestamp - pd.to_timedelta(1, unit="H"))
        ]
        df_end = df.loc[
            (max_timestamp - pd.to_timedelta(24, unit="H") <= timestamp_idx)
            & (timestamp_idx <= max_timestamp)
        ]

        df_start = df_start.groupby("symbol")["position"].mean()
        df_end = df_end.groupby("symbol")["position"].mean()

        for i in range(1, 13):
            t = i / 12.0
            client.submit(
                tournament="crypto",
                model_id=model_id,
                timestamp=int(
                    (
                        max_timestamp
                        + pd.to_timedelta(1, unit="H")
                        + i * pd.to_timedelta(5, unit="minutes")
                    ).timestamp()
                ),
                positions=(df_start * (1.0 - t) + df_end * t).to_dict(),
            )
