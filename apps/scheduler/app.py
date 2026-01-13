"""Scheduled execution of analytics jobs."""

import os

from apscheduler.schedulers.blocking import BlockingScheduler

from eap.logging import configure_logging

from jobs.anomaly.job import run as run_anomaly
from jobs.metrics.job import run as run_metrics
from jobs.dq.job import run as run_dq

logger = configure_logging(os.getenv("LOG_LEVEL", "INFO"))


def run_all() -> None:
    logger.info("job_start", job="dq")
    run_dq()
    logger.info("job_start", job="metrics")
    run_metrics()
    logger.info("job_start", job="anomaly")
    run_anomaly()
    logger.info("job_complete", job="all")


def main() -> None:
    logger.info("scheduler_start")
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_all, "interval", hours=1, id="hourly-jobs")
    run_all()
    scheduler.start()
