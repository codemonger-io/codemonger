# -*- coding: utf-8 -*-

"""Deletes the original CloudFront access logs file corresponding to a given
masked access logs file.

You have to specify the following environment variables,
* ``SOURCE_BUCKET_NAME``: bucket name of the original CloudFront access logs
  files
* ``DESTINATION_BUCKET_NAME``: bucket name of the masked CloudFront access logs
  files
"""

import json
import logging
import os
import boto3


SOURCE_BUCKET_NAME = os.environ['SOURCE_BUCKET_NAME']
DESTINATION_BUCKET_NAME = os.environ['DESTINATION_BUCKET_NAME']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

s3 = boto3.resource('s3')
source_bucket = s3.Bucket(SOURCE_BUCKET_NAME)


def lambda_handler(event, _):
    """Delete original CloudFront access logs files.

    ``event`` is supposed to be SQS events described at
    https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
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
    src = source_bucket.Object(key)
    res = src.delete()
    LOGGER.debug('deleted object "%s": %s', key, str(res))
