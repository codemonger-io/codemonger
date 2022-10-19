# -*- coding: utf-8 -*-

"""Loads CloudFront access logs onto the data warehouse.

You have to specify the following environment variables,
* ``SOURCE_BUCKET_NAME``: name of the S3 bucket containing access logs to be
  loaded.
* ``SOURCE_OBJECT_KEY_PREFIX``: prefix of the S3 object keys to be loaded.
* ``REDSHIFT_WORKGROUP_NAME``: name of the Redshift Serverless workgroup.
* ``COPY_ROLE_ARN``: ARN of the IAM role to COPY data from the S3 object.
"""

import datetime
import json
import logging
import os
import boto3
from libdatawarehouse import ACCESS_LOGS_DATABASE_NAME, data_api, tables
from libdatawarehouse.exceptions import DataWarehouseException


SOURCE_BUCKET_NAME = os.environ['SOURCE_BUCKET_NAME']
SOURCE_KEY_PREFIX = os.environ['SOURCE_KEY_PREFIX']
REDSHIFT_WORKGROUP_NAME = os.environ['REDSHIFT_WORKGROUP_NAME']
COPY_ROLE_ARN = os.environ['COPY_ROLE_ARN']
VACUUM_WORKFLOW_ARN = os.environ['VACUUM_WORKFLOW_ARN']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

s3 = boto3.client('s3')

redshift = boto3.client('redshift-serverless')
redshift_data = boto3.client('redshift-data')
stepfunctions = boto3.client('stepfunctions')


def has_access_logs(date: datetime.datetime) -> bool:
    """Returns whether there are access logs on a given date.
    """
    access_logs_prefix = get_access_logs_prefix(date)
    res = s3.list_objects_v2(
        Bucket=SOURCE_BUCKET_NAME,
        Prefix=access_logs_prefix,
        MaxKeys=1,
    )
    return len(res.get('Contents', [])) > 0


def execute_load_script(date: datetime.datetime):
    """Executes the script to load CloudFront access logs.

    :param datetime.datetime date: date on which CloudFront access logs are to
    be loaded.
    """
    batch_res = redshift_data.batch_execute_statement(
        WorkgroupName=REDSHIFT_WORKGROUP_NAME,
        Database=ACCESS_LOGS_DATABASE_NAME,
        Sqls=[
            # drops remaining temporary tables just in case
            get_drop_raw_access_log_table_statement(),
            get_drop_referer_stage_table_statement(),
            get_drop_page_stage_table_statement(),
            get_drop_edge_location_stage_table_statement(),
            get_drop_user_agent_stage_table_statement(),
            get_drop_access_log_stage_2_table_statement(),
            get_drop_access_log_stage_table_statement(),

            get_create_raw_access_log_table_statement(),
            get_load_access_logs_statement(date),
            get_create_access_log_stage_table_statement(),
            get_drop_raw_access_log_table_statement(),
            get_create_referer_stage_table_statement(),
            get_delete_existing_referers_statement(),
            get_insert_referers_statement(),
            get_drop_referer_stage_table_statement(),
            get_create_page_stage_table_statement(),
            get_delete_existing_pages_statement(),
            get_insert_pages_statement(),
            get_drop_page_stage_table_statement(),
            get_create_edge_location_stage_table_statement(),
            get_delete_existing_edge_locations_statement(),
            get_insert_edge_locations_statement(),
            get_drop_edge_location_stage_table_statement(),
            get_create_user_agent_stage_table_statement(),
            get_delete_existing_user_agents_statement(),
            get_insert_user_agents_statement(),
            get_drop_user_agent_stage_table_statement(),
            get_create_result_type_stage_table_statement(),
            get_delete_existing_result_types_statement(),
            get_insert_result_types_statement(),
            get_drop_result_type_stage_table_statement(),
            get_encode_foreign_keys_statement(),
            get_insert_access_logs_statement(),
            get_drop_access_log_stage_2_table_statement(),
            get_drop_access_log_stage_table_statement(),
        ],
    )
    statement_id = batch_res['Id']
    status, res = data_api.wait_for_results(redshift_data, statement_id)
    if status != 'FINISHED':
        if status is not None:
            if status == 'FAILED':
                LOGGER.error('failed to load access logs: %s', str(res))
            raise DataWarehouseException(
                f'failed to load access logs: {status}',
            )
        raise DataWarehouseException('loading access logs timed out')
    LOGGER.debug(
        'loaded access logs in %.3f ms',
        res.get('Duration', 0) * 0.001 * 0.001, # ns → ms
    )


def get_create_raw_access_log_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to load raw
    access logs from the S3 bucket.
    """
    return ''.join([
        'CREATE TABLE #raw_access_log (',
        '  seq_num INT,',
        '  date DATE,',
        '  time TIME,',
        '  edge_location VARCHAR,',
        '  sc_bytes BIGINT,',
        '  c_ip VARCHAR,',
        '  cs_method VARCHAR,',
        '  cs_host VARCHAR,',
        '  cs_uri_stem VARCHAR(2048),',
        '  status SMALLINT,',
        '  referer VARCHAR(2048),',
        '  user_agent VARCHAR(2048),',
        '  cs_uri_query VARCHAR,',
        '  cs_cookie VARCHAR,',
        '  edge_result_type VARCHAR,',
        '  edge_request_id VARCHAR,',
        '  host_header VARCHAR,',
        '  cs_protocol VARCHAR,',
        '  cs_bytes BIGINT,',
        '  time_taken FLOAT4,',
        '  forwarded_for VARCHAR,',
        '  ssl_protocol VARCHAR,',
        '  ssl_cipher VARCHAR,',
        '  edge_response_result_type VARCHAR,',
        '  cs_protocol_version VARCHAR,',
        '  fle_status VARCHAR,',
        '  fle_encrypted_fields VARCHAR,',
        '  c_port INT,',
        '  time_to_first_byte FLOAT4,',
        '  edge_detailed_result_type VARCHAR,',
        '  sc_content_type VARCHAR,',
        '  sc_content_len BIGINT,',
        '  sc_range_start BIGINT,',
        '  sc_range_end BIGINT',
        ')',
        'SORTKEY (date, time, seq_num)',
    ])


def get_load_access_logs_statement(date: datetime.datetime) -> str:
    """Returns an SQL statement that loads access logs from the S3 bucket.
    """
    access_logs_prefix = get_access_logs_prefix(date)
    return ''.join([
        'COPY #raw_access_log',
        f" FROM 's3://{SOURCE_BUCKET_NAME}/{access_logs_prefix}'",
        f" IAM_ROLE '{COPY_ROLE_ARN}'",
        '  GZIP',
        "  DELIMITER '\t'",
        '  IGNOREHEADER 1',
        "  NULL AS '-'",
    ])


def get_create_access_log_stage_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to select and
    format access log columns.
    """
    return ''.join([
        'CREATE TABLE #access_log_stage (',
        '  datetime,',
        '  seq_num,',
        '  edge_location,',
        '  sc_bytes,',
        '  cs_method,',
        '  cs_uri_stem,',
        '  status,',
        '  referer,',
        '  user_agent,',
        '  cs_protocol,',
        '  cs_bytes,',
        '  time_taken,',
        '  edge_response_result_type,',
        '  time_to_first_byte',
        ')',
        '  SORTKEY ("datetime", seq_num)',
        '  AS SELECT',
        '    ("date" || \' \' || "time")::TIMESTAMP,',
        '    seq_num,',
        '    edge_location,',
        '    sc_bytes,',
        '    cs_method,',
        '    cs_uri_stem,',
        '    status,',
        "    CASE WHEN referer IS NULL THEN '-' ELSE referer END,",
        "    CASE WHEN user_agent IS NULL THEN '-' ELSE user_agent END,",
        '    cs_protocol,',
        '    cs_bytes,',
        '    time_taken,',
        '    edge_response_result_type,',
        '    time_to_first_byte',
        '  FROM #raw_access_log',
    ])


def get_drop_raw_access_log_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to load raw
    access logs from the S3 bucket.
    """
    return get_drop_table_statement('#raw_access_log')


def get_create_referer_stage_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to aggregate
    referers.
    """
    return ''.join([
        'CREATE TABLE #referer_stage (url)',
        '  SORTKEY (url)',
        '  AS SELECT referer FROM #access_log_stage',
    ])


def get_delete_existing_referers_statement() -> str:
    """Returns an SQL statement that deletes existing referers from the
    temporary referer table.
    """
    return ''.join([
        'DELETE FROM #referer_stage',
        f' USING {tables.REFERER_TABLE_NAME}',
        '  WHERE',
        f'   #referer_stage.url = {tables.REFERER_TABLE_NAME}.url',
    ])


def get_insert_referers_statement() -> str:
    """Returns an SQL statement that inserts new referers in the temporary
    table into the referer table.
    """
    return ''.join([
        f'INSERT INTO {tables.REFERER_TABLE_NAME} (url)',
        '  SELECT url FROM #referer_stage GROUP BY url',
    ])


def get_drop_referer_stage_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to aggregate
    referers.
    """
    return get_drop_table_statement('#referer_stage')


def get_create_page_stage_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to aggregate
    pages.
    """
    return ''.join([
        'CREATE TABLE #page_stage (path)',
        '  SORTKEY (path)',
        '  AS SELECT cs_uri_stem FROM #access_log_stage',
    ])


def get_delete_existing_pages_statement() -> str:
    """Returns an SQL statement that deletes existing pages from the temporary
    page table.
    """
    return ''.join([
        'DELETE FROM #page_stage',
        f' USING {tables.PAGE_TABLE_NAME}',
        '  WHERE',
        f'   #page_stage.path = {tables.PAGE_TABLE_NAME}.path',
    ])


def get_insert_pages_statement() -> str:
    """Returns an SQL statement that inserts new pages in the temporary table
    into the stage table.
    """
    return ''.join([
        f'INSERT INTO {tables.PAGE_TABLE_NAME} (path)',
        '  SELECT path FROM #page_stage GROUP BY path',
    ])


def get_drop_page_stage_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to aggregate
    pages.
    """
    return get_drop_table_statement('#page_stage')


def get_create_edge_location_stage_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to aggregate edge
    locations.
    """
    return ''.join([
        'CREATE TABLE #edge_location_stage (code)',
        '  SORTKEY (code)',
        '  AS SELECT edge_location FROM #access_log_stage',
    ])


def get_delete_existing_edge_locations_statement() -> str:
    """Returns an SQL statement that deletes existing edge locations from the
    tempoary edge location table.
    """
    return ''.join([
        'DELETE FROM #edge_location_stage',
        f' USING {tables.EDGE_LOCATION_TABLE_NAME}',
        '  WHERE',
        f'   #edge_location_stage.code = {tables.EDGE_LOCATION_TABLE_NAME}.code',
    ])


def get_insert_edge_locations_statement() -> str:
    """Returns an SQL statement that inserts new edge locations in the temporary
    table into the edge location table.
    """
    return ''.join([
        f'INSERT INTO {tables.EDGE_LOCATION_TABLE_NAME} (code)',
        '  SELECT code FROM #edge_location_stage GROUP BY code',
    ])


def get_drop_edge_location_stage_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to aggregate edge
    locations.
    """
    return get_drop_table_statement('#edge_location_stage')


def get_create_user_agent_stage_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to aggregate user
    agents.
    """
    return ''.join([
        'CREATE TABLE #user_agent_stage (user_agent)',
        '  SORTKEY (user_agent)',
        '  AS SELECT user_agent FROM #access_log_stage',
    ])


def get_delete_existing_user_agents_statement() -> str:
    """Returns an SQL statement that deletes existing user agents from the
    temporary user agent table.
    """
    return ''.join([
        'DELETE FROM #user_agent_stage',
        f' USING {tables.USER_AGENT_TABLE_NAME}',
        '  WHERE',
        f'   #user_agent_stage.user_agent = {tables.USER_AGENT_TABLE_NAME}.user_agent',
    ])


def get_insert_user_agents_statement() -> str:
    """Returns an SQL statement that inserts user agents in the temporary table
    into the user agent table.
    """
    return ''.join([
        f'INSERT INTO {tables.USER_AGENT_TABLE_NAME} (user_agent)',
        '  SELECT user_agent FROM #user_agent_stage GROUP BY user_agent',
    ])


def get_drop_user_agent_stage_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to aggregate user
    agents.
    """
    return get_drop_table_statement('#user_agent_stage')


def get_create_result_type_stage_table_statement() -> str:
    """Returns an SQL statement that creates a temporary table to aggregate
    result types.
    """
    return ''.join([
        'CREATE TABLE #result_type_stage (result_type)',
        '  SORTKEY (result_type)',
        '  AS SELECT edge_response_result_type FROM #access_log_stage',
    ])


def get_delete_existing_result_types_statement() -> str:
    """Returns an SQL statement that deletes existing result types from the
    temporary result type table.
    """
    return ''.join([
        'DELETE FROM #result_type_stage',
        f' USING {tables.RESULT_TYPE_TABLE_NAME}',
        '  WHERE',
        f'   #result_type_stage.result_type = {tables.RESULT_TYPE_TABLE_NAME}.result_type',
    ])


def get_insert_result_types_statement() -> str:
    """Returns an SQL statement that inserts result types in the temporary table
    into the result type table.
    """
    return ''.join([
        f'INSERT INTO {tables.RESULT_TYPE_TABLE_NAME} (result_type)',
        '  SELECT result_type FROM #result_type_stage GROUP BY result_type',
    ])


def get_drop_result_type_stage_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to aggregate
    result types.
    """
    return get_drop_table_statement('#result_type_stage')


def get_encode_foreign_keys_statement() -> str:
    """Returns an SQL statement that decodes foreign keys in the temporary
    access log table and creates a temporary second staging table.
    """
    return ''.join([
        'CREATE TABLE #access_log_stage_2 (',
        '  datetime,',
        '  seq_num,',
        '  edge_location,',
        '  sc_bytes,',
        '  cs_method,',
        '  page,',
        '  status,',
        '  referer,',
        '  user_agent,',
        '  cs_protocol,',
        '  cs_bytes,',
        '  time_taken,',
        '  edge_response_result_type,',
        '  time_to_first_byte',
        ')',
        '  DISTKEY (referer)',
        '  SORTKEY ("datetime", seq_num)',
        '  AS SELECT',
        '    #access_log_stage.datetime,',
        '    #access_log_stage.seq_num,',
        f'   {tables.EDGE_LOCATION_TABLE_NAME}.id,',
        '    #access_log_stage.sc_bytes,',
        '    #access_log_stage.cs_method,',
        f'   {tables.PAGE_TABLE_NAME}.id,',
        '    #access_log_stage.status,',
        f'   {tables.REFERER_TABLE_NAME}.id,',
        f'   {tables.USER_AGENT_TABLE_NAME}.id,',
        '    #access_log_stage.cs_protocol,',
        '    #access_log_stage.cs_bytes,',
        '    #access_log_stage.time_taken,',
        f'   {tables.RESULT_TYPE_TABLE_NAME}.id,',
        '    #access_log_stage.time_to_first_byte',
        '  FROM',
        '    #access_log_stage,'
        f'   {tables.EDGE_LOCATION_TABLE_NAME},',
        f'   {tables.PAGE_TABLE_NAME},',
        f'   {tables.REFERER_TABLE_NAME},',
        f'   {tables.USER_AGENT_TABLE_NAME},',
        f'   {tables.RESULT_TYPE_TABLE_NAME}',
        '  WHERE',
        f'   (#access_log_stage.edge_location = {tables.EDGE_LOCATION_TABLE_NAME}.code)',
        f'   AND (#access_log_stage.cs_uri_stem = {tables.PAGE_TABLE_NAME}.path)',
        f'   AND (#access_log_stage.referer = {tables.REFERER_TABLE_NAME}.url)',
        f'   AND (#access_log_stage.user_agent = {tables.USER_AGENT_TABLE_NAME}.user_agent)',
        '    AND (#access_log_stage.edge_response_result_type =',
        f'     {tables.RESULT_TYPE_TABLE_NAME}.result_type)',
    ])


def get_insert_access_logs_statement() -> str:
    """Returns an SQL statement that inserts access logs in the temporary second
    staging table into the access log table.
    """
    return ''.join([
        f'INSERT INTO {tables.ACCESS_LOG_TABLE_NAME}',
        '  SELECT * FROM #access_log_stage_2',
    ])

def get_drop_access_log_stage_2_table_statement() -> str:
    """Returns an SQL statement that drops the temporary second staging table
    for access logs.
    """
    return get_drop_table_statement('#access_log_stage_2')


def get_drop_access_log_stage_table_statement() -> str:
    """Returns an SQL statement that drops the temporary table to select and
    format access log columns.
    """
    return get_drop_table_statement('#access_log_stage')


def get_drop_table_statement(table_name: str) -> str:
    """Returns an SQL statement that drops a given table.
    """
    return f'DROP TABLE IF EXISTS {table_name}'


def parse_time(time_str: str) -> datetime.datetime:
    """Parses a given "time" string.
    """
    return datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S%z')


def get_access_logs_prefix(date: datetime.datetime) -> str:
    """Returns the S3 object key prefix of access log files on a given date.

    A returned string contains a trailing slash (/).
    """
    return f'{SOURCE_KEY_PREFIX}{format_date_part(date)}'


def format_date_part(date: datetime.datetime) -> str:
    """Converts a given date into the date part of an S3 object path.

    A returned string contains a trailing slash (/).
    """
    return f'{date.year:04d}/{date.month:02d}/{date.day:02d}/'


def start_vacuum():
    """Starts VACUUM over the updated tables.
    """
    res = stepfunctions.start_execution(
        stateMachineArn=VACUUM_WORKFLOW_ARN,
        input=json.dumps({
            # "SORT ONLY" is sufficient because no deletes have been performed
            'mode': 'SORT ONLY',
        }),
    )
    LOGGER.debug('started VACUUM: %s', str(res))


def lambda_handler(event, _):
    """Loads CloudFront access logs onto the data warehouse.

    This function is indented to be invoked by Amazon EventBridge.
    So ``event`` must be an object with ``time`` field.

    .. code-block:: python

        {
            'time': '2020-04-28T07:20:20Z'
        }

    Loads CloudFront access logs on the day before the date specified to
    ``time``.
    """
    LOGGER.debug('loading access logs: %s', str(event))
    invocation_date = parse_time(event['time'])
    target_date = invocation_date - datetime.timedelta(days=1)
    if has_access_logs(target_date):
        LOGGER.debug('loading access logs on %s', str(target_date))
        res = redshift.get_credentials(
            workgroupName=REDSHIFT_WORKGROUP_NAME,
            dbName=ACCESS_LOGS_DATABASE_NAME,
        )
        LOGGER.debug('accessing database as %s', res['dbUser'])
        execute_load_script(target_date)
        # we need VACUUM to sort the updated tables.
        # runs VACUUM in a different session (e.g., Step Functions) because,
        # - VACUUM needs an owner or superuser privilege
        # - VACUUM is time consuming
        # - only one VACUUM can run at the same time
        start_vacuum()
    else:
        LOGGER.debug('no access logs on %s', str(target_date))
    return {}
