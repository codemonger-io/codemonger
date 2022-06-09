import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { DeploymentStage } from './deployment-stage';

type Props = StackProps & Readonly<{
  // Deployment stage.
  deploymentStage: DeploymentStage;
}>

export class CdkStack extends Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

  }
}
