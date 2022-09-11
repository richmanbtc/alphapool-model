FROM jupyter/datascience-notebook:python-3.10.6

USER root

# install required libraries

RUN apt-get update \
  && apt-get install -y \
    fonts-ipaexfont \
    libpq-dev

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
    ccxt==1.57.43 \
    "git+https://github.com/richmanbtc/ccxt_rate_limiter.git@v0.0.4#egg=ccxt_rate_limiter" \
    "git+https://github.com/richmanbtc/crypto_data_fetcher.git@v0.0.17#egg=crypto_data_fetcher" \
    cloudpickle==2.0.0 \
    coverage==6.2 \
    cvxpy==1.1.18 \
    lightgbm==3.2.1 \
    schedule==1.1.0 \
    TA-Lib==0.4.21 \
    "git+https://github.com/richmanbtc/alphapool.git@v0.0.7#egg=alphapool" \
    dataset==1.5.2 \
    psycopg2==2.9.3 \
    retry==0.9.2 \
    tensorflow \
    scikeras \
    keras-tcn \
    yfinance \
    pytorch-tabnet \
    quandl \
    faiss-cpu==1.7.2 \
    pandas-market-calendars \
    xgboost==1.6.2 \
    numba

# matplotlibで日本語を使えるようにする
#RUN sed -i '/font\.family/d' /opt/conda/lib/python3.9/site-packages/matplotlib/mpl-data/matplotlibrc
#RUN echo "font.family: IPAexGothic" >> /opt/conda/lib/python3.9/site-packages/matplotlib/mpl-data/matplotlibrc
#RUN rm -rf /home/jovyan/.cache

ADD . /app
ENV ALPHAPOOL_MODEL_ID example-model-rank
ENV ALPHAPOOL_MODEL_PATH /app/data/example_model_rank.xz
ENV ALPHAPOOL_LOG_LEVEL debug
WORKDIR /app
CMD python -m src.main
