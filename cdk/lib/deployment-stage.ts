import { Node } from 'constructs';

/** Possible deployment stages. */
export const DEPLOYMENT_STAGES = ['development', 'production'] as const;

/** Deployment stage type. */
export type DeploymentStage = typeof DEPLOYMENT_STAGES[number];

/** Name of the CDK context value for the deployment stage. */
export const DEPLOYMENT_STAGE_CDK_CONTEXT = 'codemonger:stage';

/**
 * Converts a given string into an equivalent deployment stage.
 *
 * Case-insensitive.
 *
 * @throws RangeError
 *
 *   If `stageStr` is invalid deployment stage.
 */
export function asDeploymentStage(stageStr: string): DeploymentStage {
  const stageStrL = stageStr.toLowerCase();
  for (const stage of DEPLOYMENT_STAGES) {
    if (stage === stageStrL) {
      return stage;
    }
  }
  throw new RangeError(`invalid deployment stage: ${stageStr}`);
}

/**
 * Returns the deployment stage specified to the CDK context.
 *
 * The deployment stage must be specified to the `"codemonger:stage"` CDK
 * context value.
 *
 * @param node
 *
 *   CDK construct node that provides the CDK context.
 *
 * @throws RangeError
 *
 *   If no deployment stage is specified,
 *   or the specified deployment stage is invalid.
 */
export function getDeploymentStage(node: Node): DeploymentStage {
  const stage = node.tryGetContext(DEPLOYMENT_STAGE_CDK_CONTEXT);
  if (typeof stage !== 'string') {
    throw new RangeError(`invalid deployment stage: ${stage}`);
  }
  return asDeploymentStage(stage);
}
