import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { ContentsBucket } from './contents-bucket';
import { DeploymentStage } from './deployment-stage';

type Props = StackProps & Readonly<{
  // Deployment stage.
  deploymentStage: DeploymentStage;
}>

export class CdkStack extends Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

    const { deploymentStage } = props;

    const contentsBucket = new ContentsBucket(this, 'ContentsBucket', {
      deploymentStage,
    });

    new CfnOutput(this, 'ContentsBucketName', {
      description: 'Name of the S3 bucket for the contents of codemonger website',
      value: contentsBucket.bucket.bucketName,
    });
  }
}
