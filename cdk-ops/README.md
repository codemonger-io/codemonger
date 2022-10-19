English / [日本語](./README.ja.md)

# CDK stack for codemonger operation

This is a CDK stack that provisions AWS resources for the operation of the codemonger website.
The CDK stack that provisions AWS resources which store and deliver the contents of the codemonger website is defined in [`../cdk`](../cdk).

This stack is described with the CDK version 2.

## Automated workflow

This CDK stack provisions a [AWS CodePipeline](https://docs.aws.amazon.com/codepipeline/latest/userguide/welcome.html) pipeline that automates the following workflow,
1. Obtain the source code from the `main` branch of this repository.
2. Run [`zola build`](https://www.getzola.org/documentation/getting-started/cli-usage/#build) command for development in the `zola` folder.
3. Upload the `zola/public` folder to the contents bucket for development.
4. Manually review the contents on the website for development.
5. Approve the contents.
6. Run `zola build` command for production in the `zola` folder.
7. Upload the `zola/public` folder to the contents bucket for production.

The workflow is triggered when the `main` branch is updated; e.g., a pull request is merged.
An author of a pull request has to locally review contents with [`zola serve`](https://www.getzola.org/documentation/getting-started/cli-usage/#serve) before making the pull request.

## Data warehouse for access logs

This CDK stack provisions a data warehouse for access logs.
Please refer to [`docs/data-warehouse.md`](./docs/data-warehouse.md) for more details.

## Prerequisites

### Deploying CDK stack for contents

You have to deploy the CDK stacks for the contents of the codemonger website before deploying this CDK stack.
You need both development and production stacks.
Please refer to [`../cdk`](../cdk) for how to deploy them.

### Creating CodeStar project connecting to this repository

The [AWS CodePipeline](https://docs.aws.amazon.com/codepipeline/latest/userguide/welcome.html) pipeline provisioned by this CDK stack has to connect to this repository to trigger actions when this repository is udpated.
[AWS CodeStar](https://docs.aws.amazon.com/codestar/latest/userguide/welcome.html) connects a GitHub repository and a pipeline.
This project supposes that a file `lib/github-connection-config.ts` stores information on this GitHub repository like the following,

```ts
export const GITHUB_OWNER = 'codemonger-io';
export const GITHUB_REPOSITORY = 'codemonger';
export const GITHUB_BRANCH = 'main';
export const GITHUB_CONNECTION_ARN = 'arn:aws:codestar-connections:ap-northeast-1:<Account ID>:connection/<Connection ID>';
```

You need to fill `GITHUB_CONNECTION_ARN` with the ARN of your GitHub connection.

`lib/github-connection-config.ts` is never pushed to this repository.

## Working with the CDK stack

### Resolving dependencies

You have to resolve dependencies before starting development.

```sh
npm install
```

### Setting AWS_PROFILE

This documentation supposes that an AWS profile with sufficient credentials is stored in the [`AWS_PROFILE`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html) environment variable.
The following is an example in my case,

```sh
export AWS_PROFILE=codemonger-jp
```

### Setting the toolkit stack name

We reuse the toolkit stack deployed by the [contents CDK stack](../cdk/README.md#setting-the-toolkit-stack-name).
So this project supposes the toolkit stack name is `"codemonger-toolkit-stack"` and is stored in a variable `TOOLKIT_STACK_NAME`.

```sh
TOOLKIT_STACK_NAME=codemonger-toolkit-stack
```

### Setting the synthesizer qualifier

We reuse the toolkit stack deployed by the [contents CDK stack](../cdk/README.md#setting-the-synthesizer-qualifier).
So this documentation supposes the qualifier is `"cdmngr2022"` and is stored in a variable `TOOLKIT_STACK_QUALIFIER`.

```sh
TOOLKIT_STACK_QUALIFIER=cdmngr2022
```

### Provisioning the toolkit stack

We reuse the toolkit stack deployed by the [contents CDK stack](../cdk/README.md#provisioning-the-toolkit-stack).

### Synthesizing a CloudFormation template

Before deploying this CDK stack, you may want to check what CloudFormation template is going to be deployed.
`cdk synth` command will output a CloudFormation template without deploying it.

```sh
npx cdk synth -c "@aws-cdk/core:bootstrapQualifier=$TOOLKIT_STACK_QUALIFIER"
```

### Deploying the CDK stack

`cdk deploy` command will deploy the CDK stack to the AWS account associated with the [`AWS_PROFILE` environment variable](#setting-aws_profile).

```sh
npx cdk deploy --toolkit-stack-name $TOOLKIT_STACK_NAME -c "@aws-cdk/core:bootstrapQualifier=$TOOLKIT_STACK_QUALIFIER"
```

After deploying the CDK stack, you will find the CloudFormation stack `codemonger-operation` created or updated.

#### Admin user of the Amazon Redshift Serverless namespace

This CDK stack creates the admin user of the [Amazon Redshift Serverless (Redshift Serverless)](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-serverless.html) namespace when it provisions the namespace.
The password of the admin user is created as a secret managed by [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html).
Since **CloudFormation cannot change the admin username and password of the Redshift Serverless namespace** once it is provisioned, the **admin password is lost in case the secret is updated (regenerated)**.

If this happens, you have to manually update the admin password as another superuser.
You can change the admin password on the Redshift Serverless console, or you can assume the CloudFormation execution role\* on [Query Editor v2](https://aws.amazon.com/redshift/query-editor-v2/) to reset the admin password.

\* Redshift Serverless gives the creator of a new namespace an admin privilege of it.
Because we are using CDK (CloudFormation) to provision a Redshift Serverless namespace, the execution role of CloudFormation deserves the power.

## Post deployment

### Populating the database and tables on the data warehouse

After deploying this CDK stack, you have to populate the database and tables on the data warehouse.
Please run the following commands.

```sh
npm run populate-dw -- development
npm run populate-dw -- production
```

The `populate-dw` script runs [`bin/populate-data-warehouse.js`](./bin/populate-data-warehouse.js).

### Enabling the daily access log loading

This CDK stack provisions an [Amazon EventBridge](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html) rule that runs the Lambda function that loads CloudFront access logs onto the data warehouse once a day.
Since the rule is disabled by default, you have to enable the rule to run the daily access log loading.
There are separate rules for development\* and production.

Please make sure that you have [populated the database and tables on the data warehouse](#populating-the-database-and-tables-on-the-data-warehouse).

\* The rule for development triggers **every hour**.

## Why am I not using exports?

This CDK stack depends on the main codemonger CloudFormation stacks.
So you may think we should tighten the link between this stack and the main stacks by [exporting resources](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-exports.html) from the main stacks to this stack.
However, I had a bitter experience with exports when I tried them in the past.
If a stack depends on another stack's exports, we cannot replace the exported resources before removing the dependency from the former stack.
Removing a dependency from a stack is tricky because you need an alternative fake resource to depend on.
This is especially annoying at the early stage of development because we may frequently recreate resources.
So I decided not to use exports but to obtain outputs from the main stacks.

Fortunately, CDK makes it easy to write a script that obtains outputs from the main stacks and passes them as parameters for this stack.