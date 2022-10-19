import * as path from 'path';
import { aws_lambda as lambda } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { PythonLibraryLayer } from 'cdk2-python-library-layer';

/** CDK construct that provisions a Lambda layer of `libdatawarehouse`. */
export class LibdatawarehouseLayer extends Construct {
  /** Lambda layer of `libdatawarehouse`. */
  readonly layer: lambda.ILayerVersion;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.layer = new PythonLibraryLayer(this, 'Layer', {
      runtime: lambda.Runtime.PYTHON_3_8,
      entry: path.join('lambda', 'libdatawarehouse'),
    });
  }
}
