import * as path from 'path';

import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';
import { RemovalPolicy, aws_lambda as lambda, aws_s3 as s3 } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import type { DeploymentStage } from 'cdk-common';

export interface Props {
  /** S3 bucket that stores CloudFront access logs. */
  accessLogsBucket: s3.IBucket;
  /** Deployment stage. */
  deploymentStage: DeploymentStage;
}

/** CDK construct that provisions resources to mask CloudFront access logs. */
export class AccessLogsMasking extends Construct {
  /** S3 bucket for masked access logs. */
  readonly maskedAccessLogsBucket: s3.IBucket;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const { accessLogsBucket } = props;

    // provisions an S3 bucket for masked access logs.
    this.maskedAccessLogsBucket = new s3.Bucket(
      this,
      'MaskedAccessLogsBucket',
      {
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        encryption: s3.BucketEncryption.S3_MANAGED,
        enforceSSL: true,
        removalPolicy: RemovalPolicy.RETAIN,
      },
    );

    // Lambda functions
    // - masks CloudFront access logs.
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
          DESTINATION_BUCKET_NAME: this.maskedAccessLogsBucket.bucketName,
        },
      },
    );
    accessLogsBucket.grantRead(maskAccessLogsLambda);
    this.maskedAccessLogsBucket.grantPut(maskAccessLogsLambda);
  }
}
