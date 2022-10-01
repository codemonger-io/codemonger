# -*- coding: utf-8 -*-

"""Populates the data warehouse database and tables.

You have to configure the following environment variables,
- ``WORKGROUP_NAME``: name of the Redshift Serverless workgroup to connect to
- ``ADMIN_SECRET_ARN``: ARN of the admin secret
"""

import logging
import os
import time
from typing import Dict, Optional, Sequence, Tuple
import boto3


WORKGROUP_NAME = os.environ['WORKGROUP_NAME']
ADMIN_SECRET_ARN = os.environ['ADMIN_SECRET_ARN']
ADMIN_DATABASE_NAME = os.environ['ADMIN_DATABASE_NAME']
ACCESS_LOGS_DATABASE_NAME = os.environ['ACCESS_LOGS_DATABASE_NAME']
REFERER_TABLE_NAME = os.environ['REFERER_TABLE_NAME']
PAGE_TABLE_NAME = os.environ['PAGE_TABLE_NAME']
EDGE_LOCATION_TABLE_NAME = os.environ['EDGE_LOCATION_TABLE_NAME']
USER_AGENT_TABLE_NAME = os.environ['USER_AGENT_TABLE_NAME']
RESULT_TYPE_TABLE_NAME = os.environ['RESULT_TYPE_TABLE_NAME']
ACCESS_LOG_TABLE_NAME = os.environ['ACCESS_LOG_TABLE_NAME']

POLLING_INTERVAL_IN_S = 0.05
MAX_POLLING_COUNTER = round(60 / POLLING_INTERVAL_IN_S) # > 1 minute

RUNNING_STATUSES = ['SUBMITTED', 'PICKED', 'STARTED']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

redshift_data = boto3.client('redshift-data')


class DataWarehouseException(Exception):
    """Exception raised when a data warehouse operation fails.
    """

    message: str


    def __init__(self, message: str):
        """Initializes with a given message.
        """
        self.message = message


    def __str__(self):
        classname = type(self).__name__
        return f'{classname}({self.message})'


    def __repr__(self):
        classname = type(self).__name__
        return f'{classname}({repr(self.message)})'


def get_create_database_statement() -> str:
    """Returns an SQL statement to create the database.
    """
    return f'CREATE DATABASE {ACCESS_LOGS_DATABASE_NAME}'


def get_create_tables_script() -> Sequence[str]:
    """Returns SQL statements to create tables.
    """
    return [
        get_create_referer_table_statement(),
        get_create_page_table_statement(),
        get_create_edge_location_table_statement(),
        get_create_user_agent_table_statement(),
        get_create_result_type_table_statement(),
        get_create_access_log_table_statement(),
    ]


def get_create_referer_table_statement() -> str:
    """Returns an SQL statement to create the table for referers.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {REFERER_TABLE_NAME} (',
        '  id BIGINT IDENTITY(1, 1) DISTKEY,',
        '  url VARCHAR NOT NULL,',
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_page_table_statement() -> str:
    """Returns an SQL statement to create the table for pages.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {PAGE_TABLE_NAME} (',
        '  id INT IDENTITY(1, 1),',
        '  path VARCHAR NOT NULL,'
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_edge_location_table_statement() -> str:
    """Returns an SQL statement to create the table for edge locations.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {EDGE_LOCATION_TABLE_NAME} (',
        '  id INT IDENTITY(1, 1),',
        '  code VARCHAR NOT NULL,',
        '  PRIMARY KEY (id)',
        ')'
    ])


def get_create_user_agent_table_statement() -> str:
    """Returns an SQL statement to create the table for user agents.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {USER_AGENT_TABLE_NAME} ('
        '  id BIGINT IDENTITY(1, 1),',
        '  user_agent VARCHAR NOT NULL,',
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_result_type_table_statement() -> str:
    """Returns an SQL statement to create the table for result types.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {RESULT_TYPE_TABLE_NAME} ('
        '  id INT IDENTITY(1, 1),',
        '  result_type VARCHAR NOT NULL,',
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_access_log_table_statement() -> str:
    """Returns an SQL statement to create the table for access logs.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {ACCESS_LOG_TABLE_NAME} (',
        '  datetime TIMESTAMP SORTKEY NOT NULL,',
        '  edge_location INT NOT NULL,',
        '  sc_bytes BIGINT NOT NULL,',
        '  cs_method VARCHAR NOT NULL,',
        '  page INT NOT NULL,',
        '  status SMALLINT NOT NULL,',
        '  referer BIGINT DISTKEY,',
        '  user_agent BIGINT NOT NULL,',
        '  cs_protocol VARCHAR NOT NULL,',
        '  cs_bytes BIGINT NOT NULL,',
        '  time_taken FLOAT4 NOT NULL,',
        '  edge_response_result_type INT NOT NULL,',
        '  time_to_first_byte FLOAT4 NOT NULL,',
        f' FOREIGN KEY (edge_location) REFERENCES {EDGE_LOCATION_TABLE_NAME},'
        f' FOREIGN KEY (page) REFERENCES {PAGE_TABLE_NAME},'
        f' FOREIGN KEY (referer) REFERENCES {REFERER_TABLE_NAME},'
        f' FOREIGN KEY (user_agent) REFERENCES {USER_AGENT_TABLE_NAME},'
        f' FOREIGN KEY (edge_response_result_type) REFERENCES {RESULT_TYPE_TABLE_NAME}'
        ')',
    ])


def wait_for_statement(statement_id: str) -> Tuple[Optional[str], Dict]:
    """Waits for a given statement to finish.

    :returns: final status of the statement.
    ``None`` if polling has timed out.
    """
    counter = 0
    while counter < MAX_POLLING_COUNTER:
        res = redshift_data.describe_statement(Id=statement_id)
        if counter % 20 == 0:
            LOGGER.debug('polling statement status [%d]: %s', counter, str(res))
        if res['Status'] not in RUNNING_STATUSES:
            LOGGER.debug(
                'statement done in: %.3f ms',
                res.get('Duration', 0) * 0.001 * 0.001, # ns → ms
            )
            return res['Status'], res
        time.sleep(POLLING_INTERVAL_IN_S)
        counter += 1
    return None, res


def lambda_handler(event, _):
    """Populates the data warehouse database and tables.
    """
    LOGGER.debug(
        'populating data warehouse database and tables: %s',
        str(event),
    )
    # populates the database
    res = redshift_data.execute_statement(
        WorkgroupName=WORKGROUP_NAME,
        SecretArn=ADMIN_SECRET_ARN,
        Database=ADMIN_DATABASE_NAME,
        Sql=get_create_database_statement(),
    )
    status, res = wait_for_statement(res['Id'])
    if status != 'FINISHED':
        if status == 'FAILED':
            # ignores the error if the database already exists
            if not res.get('Error', '').lower().endswith('already exists'):
                raise DataWarehouseException(
                    f'failed to create the database: {res.get("Error")}',
                )
        else:
            raise DataWarehouseException(
                f'failed to create the database: {status or "timeout"}',
            )
    # populates the tables
    res = redshift_data.batch_execute_statement(
        WorkgroupName=WORKGROUP_NAME,
        SecretArn=ADMIN_SECRET_ARN,
        Database=ACCESS_LOGS_DATABASE_NAME,
        Sqls=get_create_tables_script(),
    )
    status, res = wait_for_statement(res['Id'])
    if status != 'FINISHED':
        if status == 'FAILED':
            raise DataWarehouseException(
                f'failed to populate tables: {res.get("Error")}',
            )
        raise DataWarehouseException(
            f'failed to populate tables: {status or "timeout"}',
        )
    return {
        'statusCode': 200,
    }
