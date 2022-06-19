import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import {
  CodemongerResources,
  CodemongerResourceNames,
} from './codemonger-resources';
import { ContentsPipeline } from './contents-pipeline';

type Props = StackProps & Readonly<{
  // names of the main codemonger resources.
  codemongerResourceNames: CodemongerResourceNames;
}>;

export class CdkOpsStack extends Stack {
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

    const codemongerResources = new CodemongerResources(
      this,
      'CodemongerResources',
      props.codemongerResourceNames,
    );
    const pipeline = new ContentsPipeline(this, 'ContentsPipeline', {
      codemongerResources,
    });
  }
}
