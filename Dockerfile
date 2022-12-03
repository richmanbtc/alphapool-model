FROM alphapool/alphapool-model:image-v0.0.2

RUN pip uninstall -y alphapool \
    && pip install --no-cache-dir \
      "git+https://github.com/richmanbtc/alphapool.git@v0.1.1#egg=alphapool"

ADD . /app
ENV ALPHAPOOL_MODEL_ID example-model-rank
ENV ALPHAPOOL_MODEL_PATH /app/data/example_model_rank.xz
ENV ALPHAPOOL_LOG_LEVEL debug
WORKDIR /app
CMD python -m src.main
