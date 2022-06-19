import {
  CloudFormationClient,
  DescribeStacksCommand,
} from '@aws-sdk/client-cloudformation';
import { aws_s3 as s3 } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { DeploymentStage } from 'cdk-common';

/** Domain name for production. */
const CODEMONGER_DOMAIN_NAME = 'codemonger.io';

/** Prefix of the main codemonger stacks. */
const CODEMONGER_STACK_PREFIX = 'codemonger-';

/** Resource names in the main codemonger stacks. */
export type CodemongerResourceNames = {
  /** Name of the S3 bucket for development contents. */
  developmentContentsBucketName: string;
  /** Domain name of the CloudFront distribution for development. */
  developmentDistributionDomainName: string;
  /** Name of the S3 bucket for production contents. */
  productionContentsBucketName: string;
};

/**
 * Resolves the resource names in the main codemonger stacks.
 *
 * @throws Error
 *
 *   If the stacks are not configured as expected.
 */
export async function resolveCodemongerResourceNames():
  Promise<CodemongerResourceNames>
{
  const developmentOutputs = await fetchStackOutput('development');
  const productionOutputs = await fetchStackOutput('production');
  const developmentContentsBucketName =
    developmentOutputs.get('ContentsBucketName');
  if (developmentContentsBucketName == null) {
    throw new Error('contents bucket for development is not available');
  }
  const developmentDistributionDomainName =
    developmentOutputs.get('ContentsDistributionDomainName');
  if (developmentDistributionDomainName == null) {
    throw new Error('contents distribution for development is not available');
  }
  const productionContentsBucketName =
    productionOutputs.get('ContentsBucketName');
  if (productionContentsBucketName == null) {
    throw new Error('contents bucket for production is not available');
  }
  return {
    developmentContentsBucketName,
    developmentDistributionDomainName,
    productionContentsBucketName,
  };
}

/**
 * Obtains the outputs from the main codemonger stack of a given stage.
 *
 * @return
 *
 *   Maps an output key to its output value.
 *
 * @throws Error
 *
 *   If no stack exists, or the stack is not configured as expected.
 */
async function fetchStackOutput(stage: DeploymentStage):
  Promise<Map<string, string>>
{
  const stackName = `${CODEMONGER_STACK_PREFIX}-${stage}`;
  const client = new CloudFormationClient({});
  const command = new DescribeStacksCommand({
    StackName: stackName,
  });
  const response = await client.send(command);
  const stacks = response.Stacks ?? [];
  const stack = stacks[0];
  if (stack == null) {
    throw new Error(`no codemonger stack: ${stackName}`);
  }
  const outputs = stack.Outputs ?? [];
  const outputMap: Map<string, string> = new Map();
  for (const output of outputs) {
    const key = output.OutputKey;
    const value = output.OutputValue;
    if (key != null && value != null) {
      outputMap.set(key, value);
    }
  }
  return outputMap;
}

/** CDK construct that resolves the resources of the main codemonger stacks. */
export class CodemongerResources extends Construct {
  /** S3 bucket for development contents. */
  readonly developmentContentsBucket: s3.IBucket;
  /** Domain name of the CloudFront distribution for development. */
  readonly developmentDistributionDomainName: string;
  /** S3 bucket for production contents. */
  readonly productionContentsBucket: s3.IBucket;
  /** Domain name for production. */
  readonly productionDomainName = CODEMONGER_DOMAIN_NAME;

  constructor(
    scope: Construct,
    id: string,
    resourceNames: CodemongerResourceNames,
  ) {
    super(scope, id);

    const {
      developmentContentsBucketName,
      developmentDistributionDomainName,
      productionContentsBucketName,
    } = resourceNames;

    this.developmentContentsBucket = s3.Bucket.fromBucketName(
      this,
      'DevelopmentContentsBucket',
      developmentContentsBucketName,
    );
    this.developmentDistributionDomainName = developmentDistributionDomainName;
    this.productionContentsBucket = s3.Bucket.fromBucketName(
      this,
      'ProductionContentsBucket',
      productionContentsBucketName,
    );
  }
}
