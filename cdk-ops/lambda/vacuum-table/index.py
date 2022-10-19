# -*- coding: utf-8 -*-

"""Runs VACUUM over a given table.

You have to specify the following environment variables.
* ``WORKGROUP_NAME``: name of the Redshift Serverless workgroup.
* ``ADMIN_SECRET_ARN``: ARN of the secret containing the admin password.
"""

import logging
import os
import boto3
from libdatawarehouse import ACCESS_LOGS_DATABASE_NAME, data_api


WORKGROUP_NAME = os.environ['WORKGROUP_NAME']
ADMIN_SECRET_ARN = os.environ['ADMIN_SECRET_ARN']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

redshift_data = boto3.client('redshift-data')


def lambda_handler(event, _):
    """Runs VACUUM over a given table.

    ``event`` must be a ``dict`` similar to the following,

    .. code-block:: python

        {
            'tableName': '<table-name>',
            'mode': 'SORT ONLY'
        }
    """
    LOGGER.debug('running VACUUM: %s', str(event))
    table_name = event['tableName']
    # TODO: verify table_name
    mode = event['mode']
    # TODO: verify mode
    queue_res = redshift_data.execute_statement(
        WorkgroupName=WORKGROUP_NAME,
        SecretArn=ADMIN_SECRET_ARN,
        Database=ACCESS_LOGS_DATABASE_NAME,
        Sql=f'VACUUM {mode} {table_name}',
    )
    status, res = data_api.wait_for_results(redshift_data, queue_res['Id'])
    if status == 'FAILED':
        LOGGER.error('VACUUM over %s failed: %s', table_name, str(res))
    elif status is None:
        LOGGER.error('VACUUM over %s timed out', table_name)
        status = 'TIMEOUT'
    elif status == 'FINISHED':
        LOGGER.debug(
            'VACUUM over %s finished in %.3f ms',
            table_name,
            res.get('Duration', 0) * 0.001 * 0.001, # ns → ms
        )
    else:
        LOGGER.error('VACUUM over %s failed: %s', table_name, status)
    return {
        'status': status,
    }
