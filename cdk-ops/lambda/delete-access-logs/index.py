# -*- coding: utf-8 -*-

"""Deletes the original CloudFront access logs file corresponding to a given
masked access logs file.

You have to specify the following environment variables,
* ``SOURCE_BUCKET_NAME``: name of the S3 bucket containing original CloudFront
  access logs files
* ``DESTINATION_BUCKET_NAME``: name of the S3 bucket containing transformed
  CloudFront access logs files
* ``DESTINATION_KEY_PREFIX``: prefix of S3 object keys, which corresponds to
  masked access logs
"""

import json
import logging
import os
import boto3
from botocore.exceptions import ClientError


SOURCE_BUCKET_NAME = os.environ['SOURCE_BUCKET_NAME']
DESTINATION_BUCKET_NAME = os.environ['DESTINATION_BUCKET_NAME']
DESTINATION_KEY_PREFIX = os.environ['DESTINATION_KEY_PREFIX']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

s3 = boto3.resource('s3')
source_bucket = s3.Bucket(SOURCE_BUCKET_NAME)


def lambda_handler(event, _):
    """Delete original CloudFront access logs files.

    ``event`` is supposed to be SQS events described at
    https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html

    Each SQS event is supposed to be an object-creation notification from the
    S3 bucket containing masked access logs.
    """
    for record in event['Records']:
        body = record.get('body')
        if body is None:
            LOGGER.error('invalid SQS record: %s', str(record))
            continue
        try:
            message = json.loads(body)
        except json.JSONDecodeError:
            LOGGER.error('invalid SQS record: %s', str(record))
            continue
        # may receive a test message "s3:TestEvent"
        # and a test message does not have "Records"
        entries = message.get('Records')
        if entries is None:
            LOGGER.debug('maybe a test message: %s', str(message))
            continue
        for entry in entries:
            event_name = entry.get('eventName', '?')
            if event_name.startswith('ObjectCreated:'):
                s3_object = entry.get('s3')
                if s3_object is None:
                    LOGGER.error('invalid S3 event: %s', str(entry))
                else:
                    process_s3_object(s3_object)
            else:
                LOGGER.error(
                    'event "%s" other than S3 object creation was notified.'
                    ' please check the event source configuration',
                    event_name,
                )
    return {}


def process_s3_object(s3_object):
    """Processes a given S3 object event.

    ``s3_object`` must conform to an S3 object creation event described at
    https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html
    """
    LOGGER.debug('processing S3 object event: %s', str(s3_object))
    # makes sure that the destination bucket matches
    bucket_name = s3_object.get('bucket', {}).get('name')
    if bucket_name is None:
        LOGGER.error('no bucket name in S3 object event: %s', str(s3_object))
        return
    if bucket_name != DESTINATION_BUCKET_NAME:
        LOGGER.warning(
            'bucket name must be "%s" but "%s" was given.'
            ' please check the event source configuration',
            DESTINATION_BUCKET_NAME,
            bucket_name,
        )
        return
    key = s3_object.get('object', {}).get('key')
    if key is None:
        LOGGER.error('no object key in S3 object event: %s', str(s3_object))
        return
    if not key.startswith(DESTINATION_KEY_PREFIX):
        LOGGER.warning(
            '"%s" does not have the preifx "%s".'
            ' please check the event source configuration',
            key,
            DESTINATION_KEY_PREFIX,
        )
        return
    # key should be like,
    #   {DESTINATION_KEY_PREFIX}{year}/{month}/{date}/{original_key}
    # so the last segment separated by a slash ('/') is the key for the
    # original access logs file.
    src_key = key.split('/')[-1]
    if len(src_key) > 0:
        src = source_bucket.Object(src_key)
        try:
            res = src.delete()
            LOGGER.debug('deleted object "%s": %s', src_key, str(res))
        except ClientError as exc:
            LOGGER.error('failed to delete object "%s": %s', src_key, str(exc))
    else:
        LOGGER.warning('ignoring invalid key: %s', key)
