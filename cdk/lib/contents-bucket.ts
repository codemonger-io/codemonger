import { RemovalPolicy, aws_s3 as s3 } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { DeploymentStage } from 'cdk-common';

type Props = Readonly<{
  // Deployment stage.
  deploymentStage: DeploymentStage;
}>

/**
 * CDK construct that provisions an S3 bucket to store contents of the
 * codemonger website.
 *
 * The S3 bucket is versioned in the production stage.
 */
export class ContentsBucket extends Construct {
  /** S3 bucket to store contents of the codemonger website. */
  readonly bucket: s3.IBucket;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const { deploymentStage } = props;

    this.bucket = new s3.Bucket(this, 'ContentsBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      // encryption is unnecessary because contents are basically public.
      encryption: s3.BucketEncryption.UNENCRYPTED,
      // enables versioning only for the production stage.
      versioned: deploymentStage === 'production',
      removalPolicy: RemovalPolicy.RETAIN,
    });
  }
}
