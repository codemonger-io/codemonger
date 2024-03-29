#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';

import { CdkOpsStack } from '../lib/cdk-ops-stack';
import { resolveCodemongerResourceNames } from '../lib/codemonger-resources';

// before creating an App, resolves resource names of the main codemonger stacks
resolveCodemongerResourceNames()
  .then(names => {
    const app = new cdk.App();
    new CdkOpsStack(app, 'codemonger-operations', {
      /* If you don't specify 'env', this stack will be environment-agnostic.
       * Account/Region-dependent features and context lookups will not work,
       * but a single synthesized template can be deployed anywhere. */

      /* Uncomment the next line to specialize this stack for the AWS Account
       * and Region that are implied by the current CLI configuration. */
      // env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },

      /* Uncomment the next line if you know exactly what Account and Region you
       * want to deploy the stack to. */
      // env: { account: '123456789012', region: 'us-east-1' },

      /* For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html */
      env: {
        // without the following properties `account` and `region`,
        // the stack becomes "environment-agnostic."
        // only two availability zones (AZs) are visible in an
        // evironment-agnostic stack.
        // https://docs.aws.amazon.com/cdk/v2/guide/environments.html
        account: process.env.CDK_DEFAULT_ACCOUNT,
        region: process.env.CDK_DEFAULT_REGION,
      },
      codemongerResourceNames: names,
      tags: {
        project: 'codemonger',
      },
    });
  })
  .catch(err => {
    console.error('failed to resolve main codemonger resources', err);
  });
