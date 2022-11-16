import os
import pandas as pd
from google.cloud import bigquery


def fetch(options=None, min_timestamp=None):
    project_id = os.getenv('GC_PROJECT_ID')
    client = bigquery.Client(project=project_id)

    conds = []
    if min_timestamp is not None and not options.get('ignore_min_timestamp', False):
        conds.append('timestamp >= {}'.format(min_timestamp))
    if options.get('symbols') is not None:
        conds.append('symbol IN ({})'.format(','.join(map(_quote_str, options.get('symbols')))))

    sql = """
        SELECT *
        FROM `{}.{}`
        {}
    """.format(
        os.getenv('ALPHAPOOL_DATASET'),
        options['table'],
        '' if len(conds) == 0 else 'WHERE {}'.format(' AND '.join(conds)),
    )

    df = client.query(sql).to_dataframe()
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)

    return df


def _quote_str(x):
    return "'{}'".format(x)
