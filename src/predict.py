import os
import re
import time
import joblib
import pandas as pd
import pandas_ta as ta # required to load models using df.ta.xxx
import traceback
import dataset
from retry import retry
from alphapool import Client
from .logger import create_logger
from .ml_utils import normalize_position
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

    # predict
    df["position"] = model.predict(df)
    normalize_position(df)
    logger.debug(df)

    # submit
    if dry_run:
        logger.info("dry run submit {}".format(df))
    else:
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
