import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { AccessLogsETL } from './access-logs-etl';
import {
  CodemongerResources,
  CodemongerResourceNames,
} from './codemonger-resources';
import { ContentsPipeline } from './contents-pipeline';
import { DataWarehouse } from './data-warehouse';
import { LatestBoto3Layer } from './latest-boto3-layer';
import { LibdatawarehouseLayer } from './libdatawarehouse-layer';

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
    const latestBoto3 = new LatestBoto3Layer(this, 'LatestBoto3');
    const libdatawarehouse =
      new LibdatawarehouseLayer(this, 'Libdatawarehouse');
    const pipeline = new ContentsPipeline(this, 'ContentsPipeline', {
      codemongerResources,
    });
    const dataWarehouse = new DataWarehouse(this, 'DevelopmentDataWarehouse', {
      latestBoto3,
      libdatawarehouse,
      deploymentStage: 'development',
    });
    const developmentContentsAccessLogsETL = new AccessLogsETL(
      this,
      'DevelopmentContentsAccessLogsETL',
      {
        accessLogsBucket:
          codemongerResources.developmentContentsAccessLogsBucket,
        deploymentStage: 'development',
      },
    );
  }
}
