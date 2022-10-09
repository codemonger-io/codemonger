import * as path from 'path';

import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import {
  Duration,
  RemovalPolicy,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_lambda_event_sources as lambda_event,
  aws_s3 as s3,
  aws_s3_notifications as s3n,
  aws_sqs as sqs,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

import type { DeploymentStage } from 'cdk-common';

import { DataWarehouse } from './data-warehouse';
import { LatestBoto3Layer } from './latest-boto3-layer';
import { LibdatawarehouseLayer } from './libdatawarehouse-layer';

export interface Props {
  /** S3 bucket that stores CloudFront access logs. */
  accessLogsBucket: s3.IBucket;
  /** Data warehouse. */
  dataWarehouse: DataWarehouse;
  /** Lambda layer containing the latest boto3. */
  latestBoto3: LatestBoto3Layer;
  /** Lambda layer of the data warehouse library. */
  libdatawarehouse: LibdatawarehouseLayer;
  /** Deployment stage. */
  deploymentStage: DeploymentStage;
}

/**
 * CDK construct that provisions resources to process CloudFront access logs.
 *
 * @remarks
 *
 * Defines extract, transform, and load (ETL) operations.
 */
export class AccessLogsETL extends Construct {
  /** S3 bucket for masked access logs. */
  readonly outputAccessLogsBucket: s3.IBucket;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const {
      accessLogsBucket,
      dataWarehouse,
      latestBoto3,
      libdatawarehouse,
    } = props;

    // S3 bucket for processed access logs.
    this.outputAccessLogsBucket = new s3.Bucket(
      this,
      'MaskedAccessLogsBucket',
      {
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        encryption: s3.BucketEncryption.S3_MANAGED,
        enforceSSL: true,
        lifecycleRules: [
          {
            // safeguard for incomplete multipart uploads.
            // minimum resoluation is one day.
            abortIncompleteMultipartUploadAfter: Duration.days(1),
          },
        ],
        removalPolicy: RemovalPolicy.RETAIN,
      },
    );
    // allows the data warehouse to read the bucket
    // so that it can COPY objects from the bucket.
    this.outputAccessLogsBucket.grantRead(dataWarehouse.namespaceRole);

    // masks newly created CloudFront access logs
    // - Lambda function
    const maskedAccessLogsKeyPrefix = 'masked/';
    const maskAccessLogsLambdaTimeout = Duration.seconds(30);
    const maskAccessLogsLambda = new PythonFunction(
      this,
      'MaskAccessLogsLambda',
      {
        description: 'Masks information in a given CloudFront access logs file',
        runtime: lambda.Runtime.PYTHON_3_8,
        entry: path.join('lambda', 'mask-access-logs'),
        index: 'index.py',
        handler: 'lambda_handler',
        environment: {
          SOURCE_BUCKET_NAME: accessLogsBucket.bucketName,
          DESTINATION_BUCKET_NAME: this.outputAccessLogsBucket.bucketName,
          DESTINATION_KEY_PREFIX: maskedAccessLogsKeyPrefix,
        },
        timeout: maskAccessLogsLambdaTimeout,
      },
    );
    accessLogsBucket.grantRead(maskAccessLogsLambda);
    this.outputAccessLogsBucket.grantPut(maskAccessLogsLambda);
    // - SQS queue to capture creation of access logs files, which triggers
    //   the above Lambda function
    const maxBatchingWindow = Duration.minutes(5); // least frequency
    const newLogsQueue = new sqs.Queue(this, 'NewLogsQueue', {
      retentionPeriod: Duration.days(1),
      // at least (6 * Lambda timeout) + (maximum batch window)
      // https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#events-sqs-eventsource
      visibilityTimeout: maxBatchingWindow.plus(
        Duration.seconds(6 * maskAccessLogsLambdaTimeout.toSeconds()),
      ),
    });
    accessLogsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.SqsDestination(newLogsQueue),
    );
    maskAccessLogsLambda.addEventSource(
      new lambda_event.SqsEventSource(newLogsQueue, {
        enabled: true,
        batchSize: 10,
        maxBatchingWindow,
        // the following filter did not work as I intended, and I gave up.
        /*
        filters: [
          // SQS queue may receive a test message "s3:TestEvent".
          // non-test message must contain the "Records" field.
          lambda.FilterCriteria.filter({
            body: {
              Records: lambda.FilterRule.exists(),
            },
          }),
        ], */
      }),
    );

    // deletes original CloudFront access logs.
    // - Lambda function
    const deleteAccessLogsLambdaTimeout = Duration.seconds(10);
    const deleteAccessLogsLambda = new PythonFunction(
      this,
      'DeleteAccessLogsLambda',
      {
        description: 'Deletes the original CloudFront access logs file',
        runtime: lambda.Runtime.PYTHON_3_8,
        entry: path.join('lambda', 'delete-access-logs'),
        index: 'index.py',
        handler: 'lambda_handler',
        environment: {
          SOURCE_BUCKET_NAME: accessLogsBucket.bucketName,
          // bucket name for masked logs is necessary to verify input events.
          DESTINATION_BUCKET_NAME: this.outputAccessLogsBucket.bucketName,
          DESTINATION_KEY_PREFIX: maskedAccessLogsKeyPrefix,
        },
        timeout: deleteAccessLogsLambdaTimeout,
      },
    );
    accessLogsBucket.grantDelete(deleteAccessLogsLambda);
    // - SQS queue to capture creation of masked access logs files, which
    //   triggers the above Lambda function
    const maskedLogsQueue = new sqs.Queue(this, 'MaskedLogsQueue', {
      retentionPeriod: Duration.days(1),
      visibilityTimeout: maxBatchingWindow.plus(
        Duration.seconds(6 * deleteAccessLogsLambdaTimeout.toSeconds()),
      ),
    });
    this.outputAccessLogsBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.SqsDestination(maskedLogsQueue),
      { prefix: maskedAccessLogsKeyPrefix },
    );
    deleteAccessLogsLambda.addEventSource(
      new lambda_event.SqsEventSource(maskedLogsQueue, {
        enabled: true,
        batchSize: 10,
        maxBatchingWindow,
      }),
    );

    // loads processed logs onto the data warehouse once a day.
    const loadAccessLogsLambda = new PythonFunction(
      this,
      'LoadAccessLogsLambda',
      {
        description:
          'Loads processed CloudFront access logs onto the data warehouse',
        runtime: lambda.Runtime.PYTHON_3_8,
        architecture: lambda.Architecture.ARM_64,
        entry: path.join('lambda', 'load-access-logs'),
        index: 'index.py',
        handler: 'lambda_handler',
        layers: [latestBoto3.layer, libdatawarehouse.layer],
        environment: {
          SOURCE_BUCKET_NAME: this.outputAccessLogsBucket.bucketName,
          SOURCE_KEY_PREFIX: maskedAccessLogsKeyPrefix,
          REDSHIFT_WORKGROUP_NAME: dataWarehouse.workgroupName,
          COPY_ROLE_ARN: dataWarehouse.namespaceRole.roleArn,
        },
        timeout: Duration.minutes(15),
        memorySize: 256,
      },
    );
    this.outputAccessLogsBucket.grantRead(loadAccessLogsLambda);
    dataWarehouse.grantQuery(loadAccessLogsLambda);
    // TODO: schedule running loadAccessLogsLambda
  }
}
