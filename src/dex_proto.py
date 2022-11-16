import os
import time
import joblib
import pandas as pd
import pandas_ta as ta # required to load models using df.ta.xxx
from functools import lru_cache
import requests
from retry import retry
from eth_account import Account
from web3 import Web3
from web3.middleware import construct_sign_and_send_raw_middleware
from .logger import create_logger
from .data_fetcher import DataFetcher


model_path = os.getenv("ALPHAPOOL_MODEL_PATH")
log_level = os.getenv("ALPHAPOOL_LOG_LEVEL")
dry_run = int(os.getenv("ALPHAPOOL_DRY_RUN", "0")) > 0
logger = create_logger(log_level)

weth_address = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
router2_address = '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D'


@retry(tries=3, delay=3, logger=logger)
def predict_job(dry_run=False):
    logger.info('dry_run {}'.format(dry_run))

    model = joblib.load(model_path)

    horizon = model.horizon if hasattr(model, 'horizon') else 24
    logger.info('horizon {}'.format(horizon))

    provider_configs = model.provider_configs
    logger.info('provider_configs {}'.format(provider_configs))

    # fetch data
    interval_sec = 60 * 60
    max_timestamp = (int(time.time()) // interval_sec) * interval_sec - interval_sec
    dfs = DataFetcher(sequential=True).fetch(
        provider_configs=provider_configs,
        min_timestamp=int(max_timestamp - model.max_data_sec),
    )
    df = model.merge_data(dfs)
    max_timestamp = pd.to_datetime(max_timestamp, unit='s', utc=True)

    total_eth = get_total_eth()
    logger.info('total_eth {}'.format(total_eth))

    # predict
    df["position"] = model.predict(df)
    # df["position"] = model.predict(df, total_eth=total_eth)

    target_symbols = set(df.loc[df['position'] != 0].index.get_level_values('symbol'))
    # df = df.loc[df.index.get_level_values('timestamp') >= max_timestamp - pd.to_timedelta(48, unit='H')]

    # normalize_position(df)
    logger.debug(df)

    logger.info('target symbols {}'.format(len(target_symbols)))

    # submit
    timestamp_idx = df.index.get_level_values("timestamp")
    df_start = df.loc[
        (max_timestamp - pd.to_timedelta(horizon + 1, unit="H") < timestamp_idx)
        & (timestamp_idx <= max_timestamp - pd.to_timedelta(1, unit="H"))
        ]
    df_end = df.loc[
        (max_timestamp - pd.to_timedelta(horizon, unit="H") < timestamp_idx)
        & (timestamp_idx <= max_timestamp)
        ]

    df_start = df_start.groupby("symbol")["position"].sum() / horizon
    df_end = df_end.groupby("symbol")["position"].sum() / horizon

    eps = 0.01
    for symbol in target_symbols:
        pos_start = df_start[symbol] if symbol in df_start.index else 0.0
        pos_end = df_end[symbol] if symbol in df_end.index else 0.0
        logger.info('symbol {} pos_start {} pos_end {}'.format(symbol, pos_start, pos_end))

        # trade if weight changed (larger than eps) or weight zero
        if abs(pos_start - pos_end) < eps and abs(pos_end) > 0:
            logger.info('position change too small skip')
            continue

        price = get_price(symbol)
        balance = get_balance(symbol)
        target_balance = int(total_eth * 10 ** 18 / price * pos_end)
        amount = target_balance - balance
        logger.info('price {} balance {} target_balance {} amount {}'.format(price, balance, target_balance, amount))

        if abs(amount) < total_eth * 10 ** 18 / price * eps:
            logger.info('amount too small skip')
            continue

        logger.info('symbol {} amount {}'.format(symbol, amount))

        execute_order(symbol, amount, dry_run)


def get_total_eth():
    # TODO:
    return 10


def get_price(symbol):
    w3 = get_w3()
    pair = w3.eth.contract(
        address=Web3.toChecksumAddress(symbol),
        abi=uniswap_v2_pair_abi()
    )
    res = pair.functions.getReserves().call()
    if get_token0(symbol) == Web3.toChecksumAddress(weth_address):
        return 1.0 * res[0] / res[1]
    else:
        return 1.0 * res[1] / res[0]


def get_balance(symbol):
    if get_token0(symbol) == Web3.toChecksumAddress(weth_address):
        return get_token_balance(get_token1(symbol))
    else:
        return get_token_balance(get_token0(symbol))


@lru_cache()
def get_token0(symbol):
    w3 = get_w3()
    pair = w3.eth.contract(
        address=Web3.toChecksumAddress(symbol),
        abi=uniswap_v2_pair_abi()
    )
    return pair.functions.token0().call()


@lru_cache()
def get_token1(symbol):
    w3 = get_w3()
    pair = w3.eth.contract(
        address=Web3.toChecksumAddress(symbol),
        abi=uniswap_v2_pair_abi()
    )
    return pair.functions.token1().call()


def get_token_balance(token):
    w3 = get_w3()
    contract = w3.eth.contract(
        address=Web3.toChecksumAddress(token),
        abi=erc20_abi()
    )
    return contract.functions.balanceOf(w3.eth.default_account).call()


def execute_order(symbol, amount, dry_run):
    w3 = get_w3()

    slippage = 0.005
    deadline = int(time.time()) + 5 * 60

    if get_token0(symbol) == Web3.toChecksumAddress(weth_address):
        token_address = get_token1(symbol)
    else:
        token_address = get_token0(symbol)

    logger.info('token_address {}'.format(token_address))

    pair = w3.eth.contract(
        address=Web3.toChecksumAddress(symbol),
        abi=uniswap_v2_pair_abi()
    )
    res = pair.functions.getReserves().call()
    if get_token0(symbol) == Web3.toChecksumAddress(weth_address):
        weth_reserve = res[0]
        token_reserve = res[1]
    else:
        weth_reserve = res[1]
        token_reserve = res[0]

    logger.info('weth_reserve {} token_reserve {}'.format(weth_reserve, token_reserve))

    router = w3.eth.contract(
        address=Web3.toChecksumAddress(router2_address),
        abi=uniswap_v2_router2_abi()
    )

    if amount > 0:
        opposite_am = router.functions.getAmountIn(abs(amount), weth_reserve, token_reserve).call()
        opposite_am_with_slippage = int(opposite_am * (1 + slippage))
        logger.info('opposite_am {} opposite_am_with_slippage {}'.format(opposite_am, opposite_am_with_slippage))

        call = router.functions.swapTokensForExactTokens(
            abs(amount),
            opposite_am_with_slippage,
            [weth_address, token_address],
            w3.eth.default_account,
            deadline,
        )
    else:
        opposite_am = router.functions.getAmountOut(abs(amount), token_reserve, weth_reserve).call()
        opposite_am_with_slippage = int(opposite_am * (1 - slippage))
        logger.info('opposite_am {} opposite_am_with_slippage {}'.format(opposite_am, opposite_am_with_slippage))

        call = router.functions.swapExactTokensForTokens(
            abs(amount),
            opposite_am_with_slippage,
            [token_address, weth_address],
            w3.eth.default_account,
            deadline,
        )

    if dry_run:
        logger.info('dry run skip')
        return

    tx_hash = call.transact({})
    logger.info('order submitted')
    w3.eth.wait_for_transaction_receipt(tx_hash)
    logger.info('order succeeded')


def get_w3():
    priv_key = os.getenv("ALPHAPOOL_DEX_PRIVATE_KEY", "")
    rpc_url = os.getenv("ALPHAPOOL_DEX_RPC_URL")

    provider = Web3.HTTPProvider(rpc_url)
    w3 = Web3(provider)

    if len(priv_key) > 0:
        account = Account().from_key(priv_key)
        w3.eth.default_account = account.address
        w3.middleware_onion.add(construct_sign_and_send_raw_middleware(account))

    return w3


@lru_cache()
def erc20_abi():
    return requests.get(os.getenv('ALPHAPOOL_DEX_ERC20_ABI')).json()['abi']


@lru_cache()
def uniswap_v2_pair_abi():
    return requests.get(os.getenv('ALPHAPOOL_DEX_UNISWAP_V2_PAIR_ABI')).json()['abi']


@lru_cache()
def uniswap_v2_router2_abi():
    return requests.get(os.getenv('ALPHAPOOL_DEX_UNISWAP_V2_ROUTER2_ABI')).json()['abi']


predict_job(dry_run=dry_run)

