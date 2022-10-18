import * as path from 'path';

import {
  Arn,
  Duration,
  Stack,
  aws_ec2 as ec2,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_redshiftserverless as redshift,
  aws_secretsmanager as secrets,
  aws_stepfunctions as sfn,
  aws_stepfunctions_tasks as sfn_tasks,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import type { DeploymentStage } from 'cdk-common';

import { LatestBoto3Layer } from './latest-boto3-layer';
import { LibdatawarehouseLayer } from './libdatawarehouse-layer';

/** Name of the admin user. */
export const ADMIN_USER_NAME = 'dwadmin';

/** Subnet group name of the cluster for Redshift Serverless. */
export const CLUSTER_SUBNET_GROUP_NAME = 'dw-cluster';

export interface Props {
  /** Lambda layer containing the latest boto3. */
  latestBoto3: LatestBoto3Layer;
  /** Lambda layer containing libdatawarehouse. */
  libdatawarehouse: LibdatawarehouseLayer;
  /** Deployment stage. */
  deploymentStage: DeploymentStage;
}

/** Provisions resources for the data warehouse. */
export class DataWarehouse extends Construct {
  /** VPC for Redshift Serverless clusters. */
  readonly vpc: ec2.IVpc;
  // TODO: unnecessary exposure of `adminSecret`
  /** Secret for the admin user. */
  readonly adminSecret: secrets.ISecret;
  /** Default IAM role associated with the Redshift Serverless namespace. */
  readonly namespaceRole: iam.IRole;
  /** Name of the Redshift Serverless workgroup. */
  readonly workgroupName: string;
  /** Redshift Serverless workgroup. */
  readonly workgroup: redshift.CfnWorkgroup;
  /** Lambda function to populate the database and tables. */
  readonly populateDwDatabaseLambda: lambda.IFunction;
  /** Step Functions to run VACUUM over tables. */
  readonly vacuumWorkflow: sfn.IStateMachine;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const { deploymentStage, latestBoto3, libdatawarehouse } = props;

    this.vpc = new ec2.Vpc(this, `DwVpc`, {
      cidr: '192.168.0.0/16',
      enableDnsSupport: true,
      enableDnsHostnames: true,
      subnetConfiguration: [
        {
          name: CLUSTER_SUBNET_GROUP_NAME,
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          // to reserve private addresses for the future
          // allocates up to 1024 private addresses in each subnet
          cidrMask: 22,
        },
      ],
      gatewayEndpoints: {
        S3: {
          service: ec2.GatewayVpcEndpointAwsService.S3,
        },
      },
    });

    // provisions Redshift Serverless resources
    // - secret for admin
    this.adminSecret = new secrets.Secret(this, 'DwAdminSecret', {
      description: `Data Warehouse secret (${deploymentStage})`,
      generateSecretString: {
        // the following requirement is too strict, but should not matter.
        excludePunctuation: true,
        // the structure of a secret value for Redshift is described below
        // https://docs.aws.amazon.com/secretsmanager/latest/userguide/reference_secret_json_structure.html#reference_secret_json_structure_RS
        //
        // whether it also works with Redshift Serverless is unclear.
        // as far as I tested, only "username" and "password" are required.
        secretStringTemplate: JSON.stringify({
          username: ADMIN_USER_NAME,
        }),
        generateStringKey: 'password',
      },
    });
    // - IAM role for the namespace
    this.namespaceRole = new iam.Role(this, 'DwNamespaceRole', {
      description: `Data Warehouse Role (${deploymentStage})`,
      assumedBy: new iam.CompositePrincipal(
        new iam.ServicePrincipal('redshift-serverless.amazonaws.com'),
        new iam.ServicePrincipal('redshift.amazonaws.com'),
      ),
    });
    // - namespace
    const dwNamespace = new redshift.CfnNamespace(this, 'DwNamespace', {
      namespaceName: `datawarehouse-${deploymentStage}`,
      adminUsername: ADMIN_USER_NAME,
      adminUserPassword:
        this.adminSecret.secretValueFromJson('password').unsafeUnwrap(),
      defaultIamRoleArn: this.namespaceRole.roleArn,
      iamRoles: [this.namespaceRole.roleArn],
      tags: [
        {
          key: 'project',
          value: 'codemonger',
        },
        {
          key: 'stage',
          value: deploymentStage,
        },
      ],
    });
    dwNamespace.addDependsOn(
      this.adminSecret.node.defaultChild as secrets.CfnSecret,
    );
    // - workgroup
    this.workgroupName = `datawarehouse-${deploymentStage}`;
    this.workgroup = new redshift.CfnWorkgroup(this, 'DwWorkgroup', {
      workgroupName: this.workgroupName,
      namespaceName: dwNamespace.namespaceName,
      baseCapacity: 32,
      subnetIds: this.getSubnetIdsForCluster(),
      enhancedVpcRouting: true,
      tags: [
        {
          key: 'project',
          value: 'codemonger',
        },
        {
          key: 'stage',
          value: deploymentStage,
        },
      ],
    });
    this.workgroup.addDependsOn(dwNamespace);

    // Lambda function that populates the database and tables.
    this.populateDwDatabaseLambda = new PythonFunction(
      this,
      'PopulateDwDatabaseLambda',
      {
        description: `Populates the data warehouse database and tables (${deploymentStage})`,
        runtime: lambda.Runtime.PYTHON_3_8,
        architecture: lambda.Architecture.ARM_64,
        entry: path.join('lambda', 'populate-dw-database'),
        index: 'index.py',
        handler: 'lambda_handler',
        layers: [latestBoto3.layer, libdatawarehouse.layer],
        environment: {
          WORKGROUP_NAME: this.workgroupName,
          ADMIN_SECRET_ARN: this.adminSecret.secretArn,
          ADMIN_DATABASE_NAME: 'dev',
        },
        timeout: Duration.minutes(15),
        // a Lambda function does not have to join the VPC
        // as long as it uses Redshift Data API.
        //
        // if we want to directly connect to the Redshift cluster from a Lambda,
        // we have to put the Lambda in the VPC and allocate a VPC endpoint.
        // but I cannot afford VPC endpoints for now.
        //
        // alternatively, we could run the Redshift cluster in a public subnet.
      },
    );
    // Redshift Data API uses the execution role of the Lambda function to
    // retrieve the secret.
    this.adminSecret.grantRead(this.populateDwDatabaseLambda);
    // TODO: too permissive?
    this.populateDwDatabaseLambda.role?.addManagedPolicy(iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonRedshiftDataFullAccess'));

    // Step Functions that perform VACUUM over tables.
    // - Lambda function that runs VACUUM over a given table
    const vacuumTableLambda = new PythonFunction(this, 'VacuumTableLambda', {
      description: `Runs VACUUM over a table (${deploymentStage})`,
      runtime: lambda.Runtime.PYTHON_3_8,
      architecture: lambda.Architecture.ARM_64,
      entry: path.join('lambda', 'vacuum-table'),
      index: 'index.py',
      handler: 'lambda_handler',
      layers: [latestBoto3.layer, libdatawarehouse.layer],
      environment: {
        WORKGROUP_NAME: this.workgroupName,
        ADMIN_SECRET_ARN: this.adminSecret.secretArn,
      },
      timeout: Duration.minutes(15),
    });
    this.adminSecret.grantRead(vacuumTableLambda);
    this.grantQuery(vacuumTableLambda);
    // - state machine
    //   - lists table names
    const listTableNamesState = new sfn.Pass(this, 'ListTables', {
      comment: 'Lists table names',
      result: sfn.Result.fromArray([
        'access_log',
        'referer',
        'page',
        'edge_location',
        'user_agent',
        'result_type',
      ]),
      resultPath: '$.tables',
      // produces something like
      // {
      //   mode: 'SORT ONLY',
      //   tableNames: ['access_log', ...]
      // }
    });
    this.vacuumWorkflow = new sfn.StateMachine(this, 'VacuumWorkflow', {
      definition:
        listTableNamesState.next(
          new sfn.Map(this, 'MapTables', {
            comment: 'Iterates over tables',
            maxConcurrency: 1, // sequential
            itemsPath: '$.tables',
            parameters: {
              'tableName.$': '$$.Map.Item.Value',
              'mode.$': '$.mode',
            },
          }).iterator(
            new sfn_tasks.LambdaInvoke(this, 'VacuumTable', {
              lambdaFunction: vacuumTableLambda,
            }),
          ),
        ),
      timeout: Duration.hours(1),
    });
  }

  /** Returns subnet IDs for the cluster of Redshift Serverless. */
  getSubnetIdsForCluster(): string[] {
    return this.vpc.selectSubnets({
      subnetGroupName: CLUSTER_SUBNET_GROUP_NAME,
    }).subnetIds;
  }

  /**
   * Grants permissions to query this data warehouse via the Redshift Data API.
   *
   * Allows `grantee` to call `redshift-serverless:GetCredentials`.
   */
  grantQuery(grantee: iam.IGrantable): iam.Grant {
    iam.Grant
      .addToPrincipal({
        grantee,
        actions: ['redshift-serverless:GetCredentials'],
        resourceArns: [
          // TODO: how can we get the ARN of the workgroup?
          Arn.format(
            {
              service: 'redshift-serverless',
              resource: 'workgroup',
              resourceName: '*',
            },
            Stack.of(this.workgroup),
          ),
        ],
      })
      .assertSuccess();
    return iam.Grant.addToPrincipal({
      grantee,
      actions: ['redshift-data:*'],
      resourceArns: ['*'],
    });
  }
}
