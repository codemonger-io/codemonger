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
    timeout: float = 300.0,
    cancel_at_timeout: bool = True,
) -> Tuple[Optional[str], Dict]:
    """Waits for a given statement to finish.

    :param RedshiftDataAPIService.Client client: Redshift Data API client.

    :param float polling_interval: interval in seconds between two consecutive
    pollings.

    :param float timeout: timeout in seconds.

    :param bool cancel_at_timeout: whether cancels the statement when it times
    out.
    """
    start_time = time.time()
    while True:
        res = client.describe_statement(Id=statement_id)
        status = res['Status']
        if status not in RUNNING_STATUSES:
            return status, res
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            if cancel_at_timeout:
                client.cancel_statement(Id=statement_id)
            return None, res
        time.sleep(polling_interval)
