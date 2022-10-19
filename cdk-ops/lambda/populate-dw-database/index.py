# -*- coding: utf-8 -*-

"""Populates the data warehouse database and tables.

You have to configure the following environment variables,
- ``WORKGROUP_NAME``: name of the Redshift Serverless workgroup to connect to
- ``ADMIN_SECRET_ARN``: ARN of the admin secret
- ``ADMIN_DATABASE_NAME``: name of the admin database
"""

import logging
import os
from typing import Sequence
import boto3
from libdatawarehouse import ACCESS_LOGS_DATABASE_NAME, data_api, tables
from libdatawarehouse.exceptions import DataWarehouseException


WORKGROUP_NAME = os.environ['WORKGROUP_NAME']
ADMIN_SECRET_ARN = os.environ['ADMIN_SECRET_ARN']
ADMIN_DATABASE_NAME = os.environ['ADMIN_DATABASE_NAME']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

redshift_data = boto3.client('redshift-data')


def get_create_database_statement() -> str:
    """Returns an SQL statement to create the database for access logs.
    """
    return f'CREATE DATABASE {ACCESS_LOGS_DATABASE_NAME}'


def get_create_tables_script() -> Sequence[str]:
    """Returns SQL statements to create tables.
    """
    return [
        get_create_referer_table_statement(),
        get_grant_public_table_access_statement(tables.REFERER_TABLE_NAME),
        get_create_page_table_statement(),
        get_grant_public_table_access_statement(tables.PAGE_TABLE_NAME),
        get_create_edge_location_table_statement(),
        get_grant_public_table_access_statement(
            tables.EDGE_LOCATION_TABLE_NAME,
        ),
        get_create_user_agent_table_statement(),
        get_grant_public_table_access_statement(tables.USER_AGENT_TABLE_NAME),
        get_create_result_type_table_statement(),
        get_grant_public_table_access_statement(tables.RESULT_TYPE_TABLE_NAME),
        get_create_access_log_table_statement(),
        get_grant_public_table_access_statement(tables.ACCESS_LOG_TABLE_NAME),
    ]


def get_create_referer_table_statement() -> str:
    """Returns an SQL statement to create the table for referers.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {tables.REFERER_TABLE_NAME} (',
        '  id BIGINT IDENTITY(1, 1) DISTKEY,',
        '  url VARCHAR(2048) NOT NULL SORTKEY UNIQUE,',
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_page_table_statement() -> str:
    """Returns an SQL statement to create the table for pages.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {tables.PAGE_TABLE_NAME} (',
        '  id INT IDENTITY(1, 1),',
        '  path VARCHAR(2048) NOT NULL SORTKEY UNIQUE,'
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_edge_location_table_statement() -> str:
    """Returns an SQL statement to create the table for edge locations.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {tables.EDGE_LOCATION_TABLE_NAME} (',
        '  id INT IDENTITY(1, 1),',
        '  code VARCHAR NOT NULL SORTKEY UNIQUE,',
        '  PRIMARY KEY (id)',
        ')'
    ])


def get_create_user_agent_table_statement() -> str:
    """Returns an SQL statement to create the table for user agents.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {tables.USER_AGENT_TABLE_NAME} ('
        '  id BIGINT IDENTITY(1, 1),',
        '  user_agent VARCHAR(2048) NOT NULL SORTKEY UNIQUE,',
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_result_type_table_statement() -> str:
    """Returns an SQL statement to create the table for result types.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {tables.RESULT_TYPE_TABLE_NAME} ('
        '  id INT IDENTITY(1, 1),',
        '  result_type VARCHAR NOT NULL SORTKEY UNIQUE,',
        '  PRIMARY KEY (id)',
        ')',
    ])


def get_create_access_log_table_statement() -> str:
    """Returns an SQL statement to create the table for access logs.
    """
    return ''.join([
        f'CREATE TABLE IF NOT EXISTS {tables.ACCESS_LOG_TABLE_NAME} (',
        '  datetime TIMESTAMP NOT NULL,',
        '  seq_num INT NOT NULL,',
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
        f' FOREIGN KEY (edge_location) REFERENCES {tables.EDGE_LOCATION_TABLE_NAME},'
        f' FOREIGN KEY (page) REFERENCES {tables.PAGE_TABLE_NAME},'
        f' FOREIGN KEY (referer) REFERENCES {tables.REFERER_TABLE_NAME},'
        f' FOREIGN KEY (user_agent) REFERENCES {tables.USER_AGENT_TABLE_NAME},'
        f' FOREIGN KEY (edge_response_result_type) REFERENCES {tables.RESULT_TYPE_TABLE_NAME}'
        ') SORTKEY (datetime, seq_num)',
    ])


def get_grant_public_table_access_statement(table_name: str) -> str:
    """Returns an SQL statement to grant access on a given table to public.
    """
    return f'GRANT SELECT,INSERT,UPDATE,DELETE ON {table_name} TO PUBLIC'


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
    status, res = data_api.wait_for_results(redshift_data, res['Id'])
    if status != 'FINISHED':
        if status == 'FAILED':
            # just warns if the database already exists
            if res.get('Error', '').lower().endswith('already exists'):
                LOGGER.warning('database already exists')
            else:
                raise DataWarehouseException(
                    f'failed to create the database: {res.get("Error")}',
                )
        else:
            raise DataWarehouseException(
                f'failed to create the database: {status or "timeout"}',
            )
    LOGGER.debug(
        'populated database in %.3f ms',
        res.get('Duration', 0) * 0.001 * 0.001, # ns → ms
    )
    # populates the tables
    res = redshift_data.batch_execute_statement(
        WorkgroupName=WORKGROUP_NAME,
        SecretArn=ADMIN_SECRET_ARN,
        Database=ACCESS_LOGS_DATABASE_NAME,
        Sqls=get_create_tables_script(),
    )
    status, res = data_api.wait_for_results(redshift_data, res['Id'])
    if status != 'FINISHED':
        if status == 'FAILED':
            raise DataWarehouseException(
                f'failed to populate tables: {res.get("Error")}',
            )
        raise DataWarehouseException(
            f'failed to populate tables: {status or "timeout"}',
        )
    LOGGER.debug(
        'populated tables in %.3f ms',
        res.get('Duration') * 0.001 * 0.001, # ns → ms
    )
    return {
        'statusCode': 200,
    }
