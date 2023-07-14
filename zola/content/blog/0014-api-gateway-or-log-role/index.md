+++
title = "API or CloudWatch Logs role: which comes first?"
description = "How to configure Amazon CloudWatch Logs role for Amazon API Gateway via AWS CLI"
date = 2023-07-14
draft = false
[extra]
hashtags = ["aws", "api_gateway", "cloudwatch"]
thumbnail_name = "thumbnail.png"
+++

Have you ever failed to deploy an API Gateway API due to a missing CloudWatch Logs role?
This blog post shows you how to address the issue.

<!-- more -->

## Background

You may have faced an error similar to the following while deploying an [AWS CloudFormation](https://aws.amazon.com/cloudformation/) stack to AWS:

```
Resource handler returned message: "CloudWatch Logs role ARN must be set in acc
ount settings to enable logging (Service: ApiGateway, Status Code: 400, Request
ID: 00000000-0000-0000-0000-000000000000)" (RequestToken: 00000000-0000-0000-00
00-000000000000, HandlerErrorCode: InvalidRequest)
```

The cause of this error should be simple; you have not configured the [Amazon CloudWatch Logs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html) role for [Amazon API Gateway (API Gateway)](https://aws.amazon.com/api-gateway/).
Thus, the solution should also be simple; configure the CloudWatch Logs role for API Gateway, done!

However, things do not go straightforward, if your account has no API Gateway API deployed yet.
The API Gateway console does not provide the page where you can configure the CloudWatch Logs role unless you have at least one API deployed.

## Workarounds

Workarounds may be:
1. **Through API Gateway console**: Deploy your API without logging enabled, and configure the CloudWatch Logs role on the API Gateway console afterward.
   Then redeploy your API with logging enabled.
2. **Through the AWS CLI**: Configure the CloudWatch Logs role via the [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html).
   Then deploy your API with logging enabled.
3. **Through the CDK\***: Turn on the [`cloudWatchRole`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApiProps.html#cloudwatchrole) property when configuring a [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html) in the CDK.
   **NOT recommended**

In the [next section](#Configuring_the_CloudWatch_Logs_role_via_the_AWS_CLI), I will show you the second option.
I will also explain why you should not turn on `cloudWatchRole` in the [Section "Why you should not turn on cloudWatchRole?"](#Why_you_should_not_turn_on_cloudWatchRole?).

\* CDK: [AWS Cloud Development Kit](https://aws.amazon.com/cdk/)

## Configuring the CloudWatch Logs role via the AWS CLI

Which AWS CLI command do we have to use to configure the CloudWatch Logs role for API Gateway?
Unfortunately, the [AWS documentation](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html) [\[1\]](#References) somehow does not explain how to configure it via the AWS CLI.
**The command is [`apigateway update-account`](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/apigateway/update-account.html)** [\[2\]](#References) in fact.
Not very intuitive, isn't it?
Putting that aside, the [example section](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/apigateway/update-account.html#examples) in the command documentation exactly shows how to set the CloudWatch Logs role.

```sh
aws apigateway update-account --patch-operations op='replace',path='/cloudwatchRoleArn',value='arn:aws:iam::123412341234:role/APIGatewayToCloudWatchLogs'
```

How to create an IAM role is out of the scope of this post, but you can find it in [Appendix](#Creating_an_IAM_role_for_API_Gateway_logging).

## Why you should not turn on cloudWatchRole?

It may seem handy to use the `cloudWatchRole` option, however, it would end up with subtle errors in the future.

It might happen when you delete the CDK (CloudFormation) stack.
When you delete the stack, the CloudWatch Logs role that the stack provisioned is also deleted.
Since the CloudWatch Logs role setting is account-wise, all the **other APIs in your account will start to fail due to the non-existing CloudWatch Logs role**.

## Wrap up

In this blog post, I explained
- [how to configure the CloudWatch Logs role for API Gateway through the AWS CLI](#Configuring_the_CloudWatch_Logs_role_via_the_AWS_CLI)
- [why you should not turn on the `cloudWatchRole` option of `RestApi` in the CDK](#Why_you_should_not_turn_on_cloudWatchRole?)

## Appendix

### Creating an IAM role for API Gateway logging

You can take the following steps to create and configure an IAM role for API Gateway logging through the AWS CLI:

1. Create an IAM role that `apigateway.amazonaws.com` can assume.

    ```sh
    aws iam create-role \
        --role-name APIGatewayToCloudWatchLogs \
        --description 'API Gateway logging role' \
        --assume-role-policy-document '{
          "Version": "2012-10-17",
          "Statement": [
            {
              "Sid": "",
              "Effect": "Allow",
              "Principal": {
                "Service": "apigateway.amazonaws.com"
              },
              "Action": "sts:AssumeRole"
            }
          ]
        }'
    ```

2. Attach the AWS-managed policy `AmazonAPIGatewayPushToCloudWatchLogs` to the IAM role created in Step 1.

    ```sh
    aws iam attach-role-policy --role-name APIGatewayToCloudWatchLogs --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs
    ```

## References

1. [Setting up CloudWatch logging for a REST API in API Gateway - _Amazon API Gateway Developer Guide_](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html)
2. [apigateway update-account - _AWS CLI Command Reference_](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/apigateway/update-account.html#examples)