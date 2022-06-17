import { CfnOutput, Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { ContentsBucket } from './contents-bucket';
import { ContentsDistribution } from './contents-distribution';
import { DeploymentStage } from 'cdk-common';

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
    const contentsDistribution = new ContentsDistribution(
      this,
      'ContentsDistribution',
      {
        contentsBucket,
        deploymentStage,
      },
    );

    new CfnOutput(this, 'ContentsBucketName', {
      description: 'Name of the S3 bucket for contents of the codemonger website',
      value: contentsBucket.bucket.bucketName,
    });
    new CfnOutput(this, 'ContentsDistributionDomainName', {
      description: 'Domain name of the CloudFront distribution for contents of the codemonger website',
      value: contentsDistribution.distribution.distributionDomainName,
    });
  }
}
