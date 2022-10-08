# -*- coding: utf-8 -*-

"""Masks information in CloudFront access logs files.

You have to specify the following environment variables,
* SOURCE_BUCKET_NAME: name of the S3 bucket containing CloudFront access logs
  files to be masked.
* DESTINATION_BUCKET_NAME: name of the S3 bucket where masked CloudFront access
  logs files are to be written.
* DESTINATION_KEY_PREFIX: prefix to be prepended to the keys of objects in the
  destination bucket.
"""

import array
import csv
import gzip
import io
import ipaddress
import json
import logging
import os
import time
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, Sequence, TextIO
import boto3
from botocore.exceptions import ClientError


SOURCE_BUCKET_NAME = os.environ['SOURCE_BUCKET_NAME']
DESTINATION_BUCKET_NAME = os.environ['DESTINATION_BUCKET_NAME']
DESTINATION_KEY_PREFIX = os.environ['DESTINATION_KEY_PREFIX']

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

s3 = boto3.resource('s3')
source_bucket = s3.Bucket(SOURCE_BUCKET_NAME)
destination_bucket = s3.Bucket(DESTINATION_BUCKET_NAME)


def translate_logs(logs_in: Iterable[str]) -> Iterator[str]:
    """Translates CloudFront access logs read from a given iterator and returns
    a new iterator of translated lines.

    CloudFront access logs starts with the following lines,

    .. code-block::

        #Version: 1.0
        #Fields: date time ...

    Column names follows the prefix "#Fields:" in the second line.
    To parse CloudFront access logs as valid TSV data with a header line, we
    have to skip the first line, drop ``#Fields:`` from the second line and
    replace space characters with tabs in the second line.
    """
    for line in logs_in:
        if line.startswith('#Version:'):
            continue
        if line.startswith('#Fields:'):
            columns = line.split(' ')[1:]
            yield '\t'.join(columns)
        yield line


def mask_row(row: Dict[str, str]) -> Dict[str, str]:
    """Masks a given row in CloudFront access logs.
    """
    addr = row['c-ip']
    if addr != '-':
        row['c-ip'] = mask_ip_address(addr)
    addr = row['x-forwarded-for']
    if addr != '-':
        row['x-forwarded-for'] = mask_ip_address(addr)
    return row


def mask_ip_address(addr: str) -> str:
    """Masks a given IP address.

    Leaves 8 MSBs of an IPv4 address.
    Leaves 32 MSBs of an IPv6 address.
    Reference: https://cloudonaut.io/anonymize-cloudfront-access-logs/
    """
    ip_addr = ipaddress.ip_address(addr)
    if ip_addr.version == 4:
        return mask_ip_address_v4(addr)
    if ip_addr.version == 6:
        return mask_ip_address_v6(addr)
    # invalid IP address
    raise ValueError(f'invalid IP address: {addr}')


def mask_ip_address_v4(addr: str) -> str:
    """Masks a given IPv4 address.

    Leaves 8 MSBs.
    """
    # makes strict=False to ignore host bits
    net = ipaddress.ip_network(f'{addr}/8', strict=False)
    return str(net.network_address)


def mask_ip_address_v6(addr: str) -> str:
    """Masks a given IPv6 address.

    Leaves 32 MSBs.
    """
    # makes strict=False to ignore host bits
    net = ipaddress.ip_network(f'{addr}/32', strict=False)
    return str(net.network_address)


def process_logs(src_key: str, logs_in: Iterator[str]):
    """Processes given CloudFront logs and outputs to given stream.
    """
    tsv_in = csv.DictReader(translate_logs(logs_in), delimiter='\t')
    # drops the first row as it contains column names
    next(tsv_in)
    column_names = tsv_in.fieldnames
    if column_names is None:
        raise ValueError('no field names are specified in the input')
    with LogDispatcher(src_key, column_names) as dispatcher:
        for row in tsv_in:
            row = mask_row(row)
            dispatcher.writerow(row)


def lambda_handler(event, _):
    """Masks information in given CloudFront access logs files on S3.

    ``event`` is supposed to be an SQS message event described at
    https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html

    Each SQS message event is supposed to be an object-creation notification
    from the S3 bucket specified by ``SOURCE_BUCKET_NAME``.

    This handler masks information in the given S3 objects and stores masked
    results into the S3 bucket specified by ``DESTINATION_BUCKET_NAME`` with
    the same object key but with ``DESTINATION_KEY_PREFIX``, year, month, and
    date prefixed.

    ``{DESTINATION_KEY_PREFIX}{year}/{month}/{date}/{key}``

    where ``year``, ``month``, and ``date`` are the timestamp of a log record.
    """
    for record in event['Records']:
        try:
            message = json.loads(record['body'])
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
                if s3_object is not None:
                    process_s3_object(s3_object)
                else:
                    LOGGER.error('invalid S3 event: %s', str(entry))
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
    # makes sure that the source bucket matches
    bucket_name = s3_object.get('bucket', {}).get('name')
    if bucket_name is None:
        LOGGER.error('no bucket name in S3 object event: %s', str(s3_object))
        return
    if bucket_name != SOURCE_BUCKET_NAME:
        LOGGER.warning(
            'bucket name must be "%s" but "%s" was given.'
            ' please check the event source configuration',
            SOURCE_BUCKET_NAME,
            bucket_name,
        )
        return
    key = s3_object.get('object', {}).get('key')
    if key is None:
        LOGGER.error('no object key in S3 object event: %s', str(s3_object))
        return
    src = source_bucket.Object(key)
    try:
        results = src.get()
    except s3.meta.client.exceptions.NoSuchKey:
        LOGGER.debug('object "%s" no longer exists', key)
        return
    with open_body(results) as body:
        with gzip.open(body, mode='rt') as tsv_in:
            process_logs(key, tsv_in)


class S3OutputStream(io.RawIOBase):
    """File object that can write an S3 object.
    """

    MIN_PART_SIZE_IN_BYTES = 5 * 1024 * 1024 # 5MB

    def __init__(self, dest_object):
        self.dest_object = dest_object
        # initiates the multipart upload
        self.multipart_upload = self.dest_object.initiate_multipart_upload(
            ServerSideEncryption='AES256',
        )
        self.uploaded_part_etags = []
        self.part_buffer = array.array('B')


    def writable(self):
        return True


    def write(self, b):
        # appends to the part buffer
        self.part_buffer.extend(b)
        if len(self.part_buffer) >= S3OutputStream.MIN_PART_SIZE_IN_BYTES:
            self.upload_part()
        return len(b)


    def upload_part(self):
        """Uploads the buffered part and flushes the buffer.
        """
        part_number = self.next_part_number
        LOGGER.debug(
            'multipart upload [%d]: size=%d',
            part_number,
            len(self.part_buffer),
        )
        # according to the boto3 documentation,
        # Part requires an str for its parameter, but actually an int.
        part = self.multipart_upload.Part(part_number)
        res = part.upload(Body=self.part_buffer.tobytes())
        self.uploaded_part_etags.append(res['ETag'])
        # resets the part buffer
        self.part_buffer = array.array('B')


    @property
    def next_part_number(self):
        """Next part number.
        """
        return len(self.uploaded_part_etags) + 1 # part number from 1


    def close(self):
        """Completes the multipart upload.
        """
        if self.multipart_upload is not None:
            LOGGER.debug('closing the multipart upload')
            try:
                # uploads the last part if it remains
                if len(self.part_buffer) > 0:
                    self.upload_part()
                # lists parts and completes
                part_list = [
                    {
                        'ETag': etag,
                        'PartNumber': i + 1,
                    } for (i, etag) in enumerate(self.uploaded_part_etags)
                ]
                self.multipart_upload.complete(
                    MultipartUpload={
                        'Parts': part_list,
                    },
                )
            except:
                LOGGER.warning(
                    'aborting the multipart upload (as close failed)',
                )
                self.multipart_upload.abort()
                raise
            finally:
                self.multipart_upload = None


    def abort(self):
        """Aborts the multipart upload.
        """
        if self.multipart_upload is not None:
            LOGGER.debug('aborting the multipart upload')
            try:
                self.multipart_upload.abort()
            finally:
                self.multipart_upload = None


    def __exit__(self, exc_type, exc_value, traceback):
        """Calls ``abort`` if an exception has occurred.
        """
        if exc_type is not None:
            self.abort()
            return False # propagates the exception
        return super().__exit__(exc_type, exc_value, traceback)


    def __del__(self):
        """Calls ``abort``.

        You have to use ``with`` statement or explicitly call ``close`` to
        complete the multipart upload.
        """
        self.abort()


class GzippedTsvOnS3:
    """Gzipped TSV file in an S3 bucket.
    """

    underlying: S3OutputStream
    gzipped: TextIO
    tsv_writer: csv.DictWriter
    _next_row_number: int


    def __init__(
        self,
        underlying: S3OutputStream,
        gzipped: TextIO,
        tsv_writer: csv.DictWriter,
    ):
        self.underlying = underlying
        self.gzipped = gzipped
        self.tsv_writer = tsv_writer
        self._next_row_number = 1


    def next_row_number(self) -> int:
        """Returns the next row number.

        Every call of this method increments the row number.
        """
        row_number = self._next_row_number
        self._next_row_number += 1
        return row_number


    def close(self):
        """Completes the upload of the CSV file.
        """
        try:
            self.gzipped.close()
        except IOError as exc:
            LOGGER.error('failed to close a gzip stream: %s', str(exc))
            self.underlying.abort()
        else:
            try:
                self.underlying.close()
            except ClientError as exc:
                LOGGER.error(
                    'failed to finish an S3 object upload: %s',
                    str(exc),
                )


    def abort(self):
        """Aborts the upload of the CSV file.
        """
        try:
            self.gzipped.close()
        except IOError as exc:
            LOGGER.error('failed to close a gzip stream: %s', str(exc))
        try:
            self.underlying.abort()
        except ClientError as exc:
            # TODO: possible exceptions?
            LOGGER.error(
                'failed to abort an S3 object upload: %s',
                str(exc),
            )


class LogDispatcher:
    """Distributes access log records to S3 objects corresponding to their
    dates.

    You should wrap this object in a ``with`` statement.
    """

    LOG_DATE_FORMAT = '%Y-%m-%d'

    ROW_NUMBER_COLUMN = 'row_num'

    dest_map: Dict[time.struct_time, GzippedTsvOnS3]


    def __init__(self, src_key: str, column_names: Sequence[str]):
        """Initializes with the column names.

        Prepends a column for row numbers to ``column_names``.
        """
        self.src_key = src_key
        self.column_names = [LogDispatcher.ROW_NUMBER_COLUMN] + column_names
        self.dest_map = {}


    def writerow(self, row: Dict[str, str]):
        """Writes a given row into a matching S3 object.

        Ignores an invalid row.

        Prepends a row number column to ``row``.
        """
        try:
            date = time.strptime(row['date'], LogDispatcher.LOG_DATE_FORMAT)
        except KeyError:
            LOGGER.warning('log record must have date: %s', str(row))
        except ValueError:
            LOGGER.warning('invalid date format: %s', row['date'])
        else:
            dest = self.get_destination(date)
            ext_row = row.copy()
            ext_row.update({
                LogDispatcher.ROW_NUMBER_COLUMN: f'{dest.next_row_number():d}',
            })
            dest.tsv_writer.writerow(ext_row)


    def get_destination(self, date: time.struct_time) -> GzippedTsvOnS3:
        """Obtains the output stream corresponding to a given date.

        Opens a new ``S3OutputStream`` if none has been opened yet.
        """
        if date in self.dest_map:
            return self.dest_map[date]
        year = f'{date.tm_year:04d}'
        month = f'{date.tm_mon:02d}'
        mday = f'{date.tm_mday:02d}'
        key = f'{DESTINATION_KEY_PREFIX}{year}/{month}/{mday}/{self.src_key}'
        dest_stream = S3OutputStream(destination_bucket.Object(key))
        dest_gzip = gzip.open(dest_stream, mode='wt')
        dest_tsv = csv.DictWriter(
            dest_gzip,
            fieldnames=self.column_names,
            delimiter='\t',
        )
        dest = GzippedTsvOnS3(dest_stream, dest_gzip, dest_tsv)
        self.dest_map[date] = dest
        dest_tsv.writeheader()
        return dest


    def close(self):
        """Completes log dispatch and S3 object uploads.
        """
        for dest in self.dest_map.values():
            dest.close()


    def abort(self):
        """Aborts log dispatch and S3 object uploads.
        """
        for dest in self.dest_map.values():
            dest.abort()


    def __enter__(self):
        return self


    def __exit__(self, exc_type, _exc_val, _exc_tb):
        if exc_type is None:
            self.close()
        else:
            self.abort()
        return False


@contextmanager
def open_body(s3_get_results):
    """Enables ``with`` statement for a body got from an S3 bucket.
    """
    body = s3_get_results['Body']
    try:
        yield body
    finally:
        body.close()
