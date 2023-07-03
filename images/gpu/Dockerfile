FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

RUN apt-get update \
  && apt-get install -y \
    fonts-ipaexfont \
    libpq-dev \
    tmux \
    wget \
    build-essential \
    git

RUN cd /tmp \
  && wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
  && tar -xvf ta-lib-0.4.0-src.tar.gz \
  && cd ta-lib \
  && ./configure --prefix=/usr \
  && (make -j4 || make) \
  && make install \
  && rm -rf /tmp/*

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir \
    ccxt==1.57.1 \
    "git+https://github.com/richmanbtc/ccxt_rate_limiter.git@v0.0.4#egg=ccxt_rate_limiter" \
    "git+https://github.com/richmanbtc/crypto_data_fetcher.git@v0.0.17#egg=crypto_data_fetcher" \
    cloudpickle==2.0.0 \
    coverage==6.2 \
    cvxpy==1.1.18 \
    lightgbm==3.3.5 \
    schedule==1.1.0 \
    TA-Lib==0.4.21 \
    "git+https://github.com/richmanbtc/alphapool.git@v0.1.5#egg=alphapool" \
    dataset==1.5.2 \
    psycopg2==2.9.3 \
    retry==0.9.2 \
    "git+https://github.com/richmanbtc/scikeras.git@feature/sample_weight" \
    yfinance==0.1.87 \
    quandl==3.7.0 \
    faiss-cpu==1.7.2 \
    pandas-market-calendars==4.1.1 \
    xgboost==1.6.2 \
    rgf_python==3.12.0 \
    dcor==0.5.7 \
    tardis-dev==2.0.0a10 \
    pandas_ta==0.3.14b0 \
    fastparquet==2022.11.0 \
    'google-cloud-bigquery[bqstorage,pandas]==3.4.0' \
    web3==5.31.1 \
    catboost==1.1.1 \
    optuna==3.0.5 \
    scipy==1.8.1 \
    seaborn==0.12.2 \
    jupyterlab==4.0.2 \
    lightning==2.0.4 \
    adabelief-pytorch==0.2.0 \
    SQLAlchemy==1.4.45

ADD . /app
ENV ALPHAPOOL_MODEL_ID example-model-rank
ENV ALPHAPOOL_MODEL_PATH /app/data/example_model_rank.xz
ENV ALPHAPOOL_LOG_LEVEL debug
WORKDIR /app
CMD python -m src.main
