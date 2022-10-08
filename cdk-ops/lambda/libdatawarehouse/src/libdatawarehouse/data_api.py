# -*- coding: utf-8 -*-

"""Provides utilities to access the Redshift Data API.
"""

import time
from typing import Dict, Optional, Tuple


RUNNING_STATUSES = ['SUBMITTED', 'PICKED', 'STARTED']


def wait_for_results(
    client,
    statement_id: str,
    polling_interval: float = 0.05,
    polling_timeout: int = round(300 / 0.05),
) -> Tuple[Optional[str], Dict]:
    """Waits for a given statement to finish.

    :param RedshiftDataAPIService.Client client: Redshift Data API client.

    :param float polling_interval: interval in seconds between two consecutive
    pollings.

    :param int polling_timeout: timeout represented as the number of pollings.
    """
    polling_counter = 0
    while True:
        res = client.describe_statement(Id=statement_id)
        status = res['Status']
        if status not in RUNNING_STATUSES:
            return status, res
        polling_counter += 1
        if polling_counter >= polling_timeout:
            return None, res
        time.sleep(polling_interval)
