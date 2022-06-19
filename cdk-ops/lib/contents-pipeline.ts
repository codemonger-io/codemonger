import {
  aws_codebuild as codebuild,
  aws_codepipeline as codepipeline,
  aws_codepipeline_actions as actions,
  aws_s3 as s3,
} from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { CodemongerResources } from './codemonger-resources';
import {
  GITHUB_BRANCH,
  GITHUB_CONNECTION_ARN,
  GITHUB_OWNER,
  GITHUB_REPOSITORY,
} from './github-connection-config';

type Props = Readonly<{
  /** Resources in the main codemonger stacks. */
  codemongerResources: CodemongerResources;
}>;

/** CDK construct that provisions a CodePipeline for contents delivery. */
export class ContentsPipeline extends Construct {
  /** CodePipeline for contents delivery. */
  readonly pipeline: codepipeline.IPipeline;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const {
      developmentContentsBucket,
      developmentDistributionDomainName,
      productionContentsBucket,
      productionDomainName,
    } = props.codemongerResources;

    const pipeline = new codepipeline.Pipeline(this, 'ContentsPipeline', {
      // we do not consider about cross-account access so far
      crossAccountKeys: false,
    });
    this.pipeline = pipeline;

    // artifacts
    // - source code
    const sourceArtifact = new codepipeline.Artifact();
    // - contents for development (review)
    const reviewArtifact = new codepipeline.Artifact();
    // - contents for production
    const productionArtifact = new codepipeline.Artifact();

    // build project
    const buildProject = new codebuild.PipelineProject(this, 'BuildProject', {
      environment: {
        buildImage: codebuild.LinuxBuildImage.fromDockerRegistry(
          // Alpine Linux where Zola is available through apk
          'public.ecr.aws/docker/library/alpine:3.16.0',
        ),
      },
      buildSpec: codebuild.BuildSpec.fromObject({
        version: 0.2,
        phases: {
          install: {
            commands: [
              'apk add zola --repository http://dl-cdn.alpinelinux.org/alpine/edge/community/',
            ],
          },
          build: {
            commands: [
              'cd zola',
              'zola build --base-url https://$CONTENTS_DISTRIBUTION_DOMAIN_NAME',
            ],
          },
        },
        artifacts: {
          'base-directory': 'zola/public',
          files: ['**/*'],
        },
      }),
    });

    // Source stage
    const sourceStage = pipeline.addStage({
      stageName: 'Source',
    });
    // - source action for GitHub repository
    sourceStage.addAction(new actions.CodeStarConnectionsSourceAction({
      actionName: 'GitHub_Source',
      owner: GITHUB_OWNER,
      repo: GITHUB_REPOSITORY,
      branch: GITHUB_BRANCH,
      connectionArn: GITHUB_CONNECTION_ARN,
      output: sourceArtifact,
      runOrder: 1,
    }));
    // Review stage
    const reviewStage = pipeline.addStage({
      stageName: 'Review',
    });
    // - build action for development
    reviewStage.addAction(new actions.CodeBuildAction({
      actionName: 'DevelopmentBuild',
      project: buildProject,
      input: sourceArtifact,
      outputs: [reviewArtifact],
      environmentVariables: {
        CONTENTS_DISTRIBUTION_DOMAIN_NAME: {
          value: developmentDistributionDomainName,
        },
      },
      runOrder: 1,
    }));
    // - deploy action for development
    reviewStage.addAction(new actions.S3DeployAction({
      actionName: 'DevelopmentDeploy',
      bucket: developmentContentsBucket,
      input: reviewArtifact,
      extract: true,
      runOrder: 2,
    }));
    // - approval of the contents
    reviewStage.addAction(new actions.ManualApprovalAction({
      actionName: 'ContentsApproval',
      externalEntityLink: `https://${developmentDistributionDomainName}`,
      // TODO: add an SNS topic
      runOrder: 3,
    }));
    // Production stage
    const productionStage = pipeline.addStage({
      stageName: 'Production',
    });
    // - build action for production
    productionStage.addAction(new actions.CodeBuildAction({
      actionName: 'ProductionBuild',
      project: buildProject,
      input: sourceArtifact,
      outputs: [productionArtifact],
      environmentVariables: {
        CONTENTS_DISTRIBUTION_DOMAIN_NAME: {
          value: productionDomainName,
        },
      },
      runOrder: 1,
    }));
    // - deploy action for production
    productionStage.addAction(new actions.S3DeployAction({
      actionName: 'ProductionDeploy',
      bucket: productionContentsBucket,
      input: productionArtifact,
      extract: true,
      runOrder: 2,
    }));
  }
}
