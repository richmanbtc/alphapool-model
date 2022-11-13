from joblib import Parallel, delayed, Memory
from .data_providers.cex import fetch as cex_fetch
from .data_providers.cex_target import fetch as cex_target_fetch
from .data_providers.fear_greedy import fetch as fear_greedy_fetch
from .data_providers.bigquery import fetch as bigquery_fetch


class DataFetcher:
    def __init__(self, memory=None, sequential=False):
        self.memory = Memory(None, verbose=0) if memory is None else memory
        self.sequential = sequential

    def fetch(self, provider_configs, min_timestamp):
        def _do_fetch2(c):
            return self.memory.cache(_do_fetch)(c, min_timestamp)

        if self.sequential:
            dfs = map(_do_fetch2, provider_configs)
        else:
            dfs = Parallel(n_jobs=len(provider_configs), backend='threading')(
                delayed(_do_fetch2)(c) for c in provider_configs
            )

        return dfs


def _do_fetch(c, min_timestamp):
    if c['provider'] == 'cex':
        f = cex_fetch
    elif c['provider'] == 'cex_target':
        f = cex_target_fetch
    elif c['provider'] == 'fear_greedy':
        f = fear_greedy_fetch
    elif c['provider'] == 'bigquery':
        f = bigquery_fetch
    df = f(
        options=c['options'],
        min_timestamp=min_timestamp,
    )
    return df
