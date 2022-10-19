/* Populates the data warehouse. */

const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');
const {
  CloudFormationClient,
  DescribeStacksCommand,
} = require('@aws-sdk/client-cloudformation');
const { LambdaClient, InvokeCommand } = require('@aws-sdk/client-lambda');

const CODEMONGER_OPERATIONS_STACK_NAME = 'codemonger-operations';

yargs(hideBin(process.argv))
  .command(
    '$0 <stage>',
    'populates the data warehouse',
    _yargs => {
      _yargs.positional('stage', {
        describe: 'deployment stage of the data warehouse',
        choices: ['development', 'production'],
      });
    },
    run,
  )
  .help()
  .argv;

async function run({ stage }) {
  console.log('obtaining populate function for', stage);
  const functionArn = await getPopulateFunctionArn(stage);
  console.log('running populate function for', stage);
  await runPopulate(functionArn);
  console.log('populated the data warehouse for', stage);
}

// obtains the ARN of the Lambda function that populates the database and
// tables.
async function getPopulateFunctionArn(stage) {
  const client = new CloudFormationClient({});
  const command = new DescribeStacksCommand({
    StackName: CODEMONGER_OPERATIONS_STACK_NAME,
  });
  const results = await client.send(command);
  const outputs = (results.Stacks ?? [])[0]?.Outputs;
  if (outputs == null) {
    throw new Error(
      `please deploy the latest stack ${CODEMONGER_OPERATIONS_STACK_NAME}`,
    );
  }
  const outputKey = stage === 'production'
    ? 'PopulateProductionDwDatabaseLambdaArn'
    : 'PopulateDevelopmentDwDatabaseLambdaArn';
  const output = outputs.find(o => o.OutputKey === outputKey);
  if (output == null) {
    throw new Error(
      `please deploy the latest stack ${CODEMONGER_OPERATIONS_STACK_NAME}`,
    );
  }
  return output.OutputValue;
}

// runs a given populate function.
async function runPopulate(functionArn) {
  const client = new LambdaClient({});
  const command = new InvokeCommand({
    FunctionName: functionArn,
    Payload: '{}',
  });
  const results = await client.send(command);
  if (results.StatusCode !== 200) {
    const decoder = new TextDecoder();
    const payload = decoder.decode(results.Payload);
    console.error('failed to populate the data warehouse', payload);
    throw new Error('failed to populate the data warehouse');
  }
}
