import os
import time
from functools import partial
import schedule
import dataset
from alphapool import Client
from .predict import predict_job

database_url = os.getenv("ALPHAPOOL_DATABASE_URL")
db = dataset.connect(database_url)
client = Client(db)

# check at startup
predict_job(client, dry_run=True)

for hour in range(0, 24, 1):
    schedule.every().day.at("{:02}:01".format(hour)).do(partial(predict_job, client))

while True:
    schedule.run_pending()
    time.sleep(1)
