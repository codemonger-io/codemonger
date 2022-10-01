import * as path from 'path';

import {
  Duration,
  aws_ec2 as ec2,
  aws_iam as iam,
  aws_lambda as lambda,
  aws_redshiftserverless as redshift,
  aws_secretsmanager as secrets,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { PythonFunction } from '@aws-cdk/aws-lambda-python-alpha';

import type { DeploymentStage } from 'cdk-common';

import { LatestBoto3Layer } from './latest-boto3-layer';

/** Name of the admin user. */
export const ADMIN_USER_NAME = 'dwadmin';

/** Subnet group name of the cluster for Redshift Serverless. */
export const CLUSTER_SUBNET_GROUP_NAME = 'dw-cluster';

export interface Props {
  /** Lambda layer containing the latest boto3. */
  latestBoto3: LatestBoto3Layer;
  /** Deployment stage. */
  deploymentStage: DeploymentStage;
}

/** Provisions resources for the data warehouse. */
export class DataWarehouse extends Construct {
  /** VPC for Redshift Serverless clusters. */
  readonly vpc: ec2.IVpc;
  /** Secret for the admin user. */
  readonly adminSecret: secrets.ISecret;
  /** IAM role of Redshift Serverless namespace. */
  readonly namespaceRole: iam.IRole;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const { deploymentStage, latestBoto3 } = props;

    this.vpc = new ec2.Vpc(this, `DwVpc`, {
      cidr: '192.168.0.0/16',
      enableDnsSupport: false,
      enableDnsHostnames: false,
      subnetConfiguration: [
        {
          name: CLUSTER_SUBNET_GROUP_NAME,
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          // to reserve private addresses for the future
          // allocates up to 1024 private addresses in each subnet
          cidrMask: 22,
        },
      ],
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
    const workgroup = new redshift.CfnWorkgroup(this, 'DwWorkgroup', {
      workgroupName: `datawarehouse-${deploymentStage}`,
      namespaceName: dwNamespace.namespaceName,
      baseCapacity: 32,
      subnetIds: this.getSubnetIdsForCluster(),
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
    workgroup.addDependsOn(dwNamespace);

    // Lambda function that populates the database and tables.
    const populateDwDatabaseLambda = new PythonFunction(
      this,
      'PopulateDwDatabaseLambda',
      {
        description: `Populates the data warehouse database and tables (${deploymentStage})`,
        runtime: lambda.Runtime.PYTHON_3_8,
        architecture: lambda.Architecture.ARM_64,
        entry: path.join('lambda', 'populate-dw-database'),
        index: 'index.py',
        handler: 'lambda_handler',
        layers: [latestBoto3.layer],
        environment: {
          WORKGROUP_NAME: workgroup.workgroupName,
          ADMIN_SECRET_ARN: this.adminSecret.secretArn,
          ADMIN_DATABASE_NAME: 'dev',
          ACCESS_LOGS_DATABASE_NAME: 'access_logs',
          PAGE_TABLE_NAME: 'page',
          REFERER_TABLE_NAME: 'referer',
          EDGE_LOCATION_TABLE_NAME: 'edge_location',
          USER_AGENT_TABLE_NAME: 'user_agent',
          RESULT_TYPE_TABLE_NAME: 'result_type',
          ACCESS_LOG_TABLE_NAME: 'access_log',
        },
        timeout: Duration.minutes(15),
        // a Lambda function does not have to join the VPC
        // as long as it uses Redshift Data API.
        //
        // if want to directly connect to the Redshift cluster from a Lambda,
        // we have to put the Lambda in the VPC and allocate a VPC endpoint.
        // but I cannot afford VPC endpoints for now.
        //
        // alternatively, we could run the Redshift cluster in a public subnet.
      },
    );
    // Redshift Data API uses the execution role of the Lambda function to
    // retrieve the secret.
    this.adminSecret.grantRead(populateDwDatabaseLambda);
    // TODO: too permissive?
    populateDwDatabaseLambda.role?.addManagedPolicy(iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonRedshiftDataFullAccess'));
  }

  /** Returns subnet IDs for the cluster of Redshift Serverless. */
  getSubnetIdsForCluster(): string[] {
    return this.vpc.selectSubnets({
      subnetGroupName: CLUSTER_SUBNET_GROUP_NAME,
    }).subnetIds;
  }
}
