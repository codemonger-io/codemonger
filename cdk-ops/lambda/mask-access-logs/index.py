# -*- coding: utf-8 -*-

"""Masks information in CloudFront access logs.

You have to specify the following environment variables,
* SOURCE_BUCKET_NAME: name of the S3 bucket containing access logs files to be
  masked.
"""

import array
import csv
import gzip
import io
import ipaddress
import logging
import os
import sys
from contextlib import contextmanager
from typing import Dict, Iterable, Iterator, TextIO
import boto3


SOURCE_BUCKET_NAME = os.environ.get('SOURCE_BUCKET_NAME')
DESTINATION_BUCKET_NAME = os.environ.get('DESTINATION_BUCKET_NAME')

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
    if addr is not None:
        row['c-ip'] = mask_ip_address(addr)
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


def process_logs(logs_in: Iterator[str], logs_out: TextIO):
    """Processes given CloudFront logs and outputs to given stream.
    """
    tsv_in = csv.DictReader(translate_logs(logs_in), delimiter='\t')
    # drops the first row as it contains column names
    next(tsv_in)
    column_names = tsv_in.fieldnames
    if column_names is None:
        raise ValueError('no field names are specified in the input')
    tsv_out = csv.DictWriter(
        logs_out,
        fieldnames=column_names,
        delimiter='\t',
    )
    tsv_out.writeheader()
    for row in tsv_in:
        row = mask_row(row)
        tsv_out.writerow(row)


def lambda_handler(event, _):
    """Masks information in a given CloudFront access logs file on S3.
    """
    LOGGER.debug('masking access logs: %s', str(event))
    src = source_bucket.Object(event['key'])
    results = src.get()
    with open_body(results) as body:
        with gzip.open(body, mode='rt') as tsv_in:
            dest = destination_bucket.Object(event['key'])
            with S3OutputStream(dest) as masked_out:
                with gzip.open(masked_out, mode='wt') as tsv_out:
                    process_logs(tsv_in, tsv_out)
    return {}


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
            self.multipart_upload.abort()
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


@contextmanager
def open_body(s3_get_results):
    """Enables ``with`` statement for a body got from an S3 bucket.
    """
    body = s3_get_results['Body']
    try:
        yield body
    finally:
        body.close()


if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(
        description='Masks CloudFront access logs',
    )
    arg_parser.add_argument(
        'logs_path',
        metavar='LOGS',
        type=str,
        help='path to a gzipped TSV file containing CloudFront access logs',
    )
    arg_parser.add_argument(
        '--out',
        dest='out_path',
        metavar='OUT',
        type=str,
        help='path to a file where masked CloudFront access logs are to be'
             ' saved (gzipped)',
    )
    logging.basicConfig(level=logging.DEBUG)
    LOGGER.debug('filtering access logs')
    args = arg_parser.parse_args()
    if args.out_path is not None:
        results_out = gzip.open(args.out_path, mode='wt')
    else:
        results_out = sys.stdout
    with gzip.open(args.logs_path, mode='rt') as text_in:
        process_logs(text_in, results_out)
