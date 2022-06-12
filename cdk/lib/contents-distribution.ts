import * as path from 'path';

import {
  Duration,
  aws_certificatemanager as acm,
  aws_cloudfront as cloudfront,
  aws_cloudfront_origins as origins,
} from 'aws-cdk-lib';
import { Construct, Node } from 'constructs';

import {
  CODEMONGER_DOMAIN_NAME,
  CODEMONGER_CERTIFICATE_ARN,
} from './certificate-config';
import { ContentsBucket } from './contents-bucket';
import { DeploymentStage } from './deployment-stage';

type Props = Readonly<{
  // S3 bucket for contents of the codemonger website.
  contentsBucket: ContentsBucket;
  // Deployment stage.
  deploymentStage: DeploymentStage;
}>

// TTL of the cache of each deployment stage.
const CACHE_TTL_OF_STAGE = {
  'development': Duration.seconds(1),
  'production': Duration.minutes(10), // TODO: increase in the future
} as const;

// name of the CDK context variable that specifies if the domain name
// assignment to the CloudFront distribution is prevented.
const NO_DOMAIN_NAME_CDK_CONTEXT = 'codemonger:no-domain-name';

/**
 * CDK construct that provisions a CloudFront distribution for contents of the
 * codemonger website.
 *
 * Traffic to `codemonger.io` will be served to the CloudFront distribution of
 * the production stage.
 * To prevent `codemonger.io` from being associated with the CloudFront
 * distribution, specify `"true"` to the CDK context variable
 * `codemonger:no-domain-name`.
 */
export class ContentsDistribution extends Construct {
  /** CloudFront distribution for contents of the codemonger website. */
  readonly distribution: cloudfront.IDistribution;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id);

    const { contentsBucket, deploymentStage } = props;

    const cachePolicy = new cloudfront.CachePolicy(this, 'CachePolicy', {
      comment: `codemonger contents cache policy (${deploymentStage})`,
      defaultTtl: CACHE_TTL_OF_STAGE[deploymentStage],
      minTtl: Duration.seconds(1),
      enableAcceptEncodingBrotli: true,
      enableAcceptEncodingGzip: true,
    });

    // domain name and certificate are configured only for the production stage
    const noDomain = isNoDomainName(Node.of(this));
    const certificateParams =
      deploymentStage === 'production' && !noDomain ? {
        domainNames: [CODEMONGER_DOMAIN_NAME],
        certificate: acm.Certificate.fromCertificateArn(
          this,
          'CodemongerDomainCertificate',
          CODEMONGER_CERTIFICATE_ARN,
        ),
      } : {};

    const expandIndexFn = new cloudfront.Function(this, 'ExpandIndexFunction', {
      // provides a fixed function name because there is a bug in CDK that may
      // generate different function IDs at different deployments and ends up
      // with an error updating a function.
      // see https://github.com/aws/aws-cdk/issues/15523
      //
      // note that a function name must be at most 64 characters long,
      // and Node.addr fills 42 characters.
      functionName: `ExpandIndexFunction${Node.of(this).addr}`,
      comment: 'Expands a given URI so that it ends with index.html',
      code: cloudfront.FunctionCode.fromFile({
        filePath: path.resolve('cloudfront-fn', 'expand-index.js'),
      }),
    });

    this.distribution = new cloudfront.Distribution(
      this,
      'ContentsDistribution',
      {
        comment: `codemonger distribution (${deploymentStage})`,
        defaultBehavior: {
          origin: new origins.S3Origin(contentsBucket.bucket),
          cachePolicy,
          functionAssociations: [{
            eventType: cloudfront.FunctionEventType.VIEWER_REQUEST,
            function: expandIndexFn,
          }],
          // only static contents are served so far
          cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD,
          viewerProtocolPolicy:
            cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        },
        // do not add a slash (/) before the root object name.
        defaultRootObject: 'index.html',
        enableLogging: true,
        ...certificateParams,
      },
    );
  }
}

// Returns if the domain name assignment to the CloudFront distribution is
// prevented.
//
// The configuration is read from the CDK context.
//
// Returns `false` if the CDK context value is other than `true` (boolean) or
// `"true"` (case-insensitive string).
function isNoDomainName(node: Node): boolean {
  const result = node.tryGetContext(NO_DOMAIN_NAME_CDK_CONTEXT);
  if (typeof result === 'boolean') {
    return result;
  }
  if (typeof result !== 'string') {
    return false;
  }
  return result.toLowerCase() === 'true';
}
