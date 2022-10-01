import * as path from 'path';

import { aws_lambda as lambda } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonLayerVersion } from '@aws-cdk/aws-lambda-python-alpha';

/** CDK construct that provisions a Lambda layer containing the latest boto3. */
export class LatestBoto3Layer extends Construct {
  /** Lambda layer containing the latest boto3. */
  readonly layer: lambda.ILayerVersion;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.layer = new PythonLayerVersion(this, 'LambdaLayer', {
      description: 'Lambda layer containing the latest boto3',
      entry: path.join('lambda', 'latest-boto3'),
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_8,
        lambda.Runtime.PYTHON_3_9,
      ],
      compatibleArchitectures: [
        lambda.Architecture.ARM_64,
        lambda.Architecture.X86_64,
      ],
    });
  }
}
