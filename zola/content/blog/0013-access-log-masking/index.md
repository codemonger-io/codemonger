+++
title = "Analyzing access logs (1. Masking)"
description = "Series: About analysis of access logs on my website"
date = 2022-11-02
draft = false
[extra]
hashtags = ["AWS", "CloudFront", "GDPR"]
thumbnail_name = "thumbnail.jpg"
+++

This blog post shares how I have reduced personal data in CloudFront access logs on my website.
This is the first post of a series about access log analysis.

<!-- more -->

## Background

It is crucial to me to know the audience of my website.
I do not need to identify who is viewing but want to see an overview of them.
This website is delivered via an [Amazon CloudFront (CloudFront)](https://aws.amazon.com/cloudfront/) distribution, and CloudFront records access logs.
So analyzing those access logs is the first step for me to understand the audience\*.
Although we cannot control which [parameters CloudFront includes in access logs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/AccessLogs.html#LogFileFormat), we have to ensure our collection of access logs is compliant with the [General Data Protection Regulation (GDPR)](https://gdpr-info.eu)[\[1\]](#Reference)\*2.
In this blog post, I show you my architecture on AWS to transform CloudFront access logs to reduce personal data.

\* One may suggest [Google Analytics](https://analytics.google.com/analytics/), but Google Analytics collects far more detailed (unnecessary) information than I need.
And I neither want to introduce creepy Cookies by adopting Google Analytics and likes.
[Google Analytics also has difficulties in GDPR compliance](https://piwik.pro/blog/is-google-analytics-gdpr-compliant/)[\[2\]](#Reference).

\*2 Although I do not think I could do anything harmful to you with the information collected on this website, we should not collect unnecessary information anyway.

## Are CloudFront access logs GDPR compliant?

The answer is likely **no**.
[Individual columns in CloudFront access logs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/AccessLogs.html#LogFileFormat) may not identify a single person.
However, if we combine columns like IP address and user-agent in CloudFront access logs, we likely could identify\* a single person and track that person.
According to [this article](https://cloudonaut.io/anonymize-cloudfront-access-logs/)[\[3\]](#Reference), we should at least drop certain bits from IP addresses in CloudFront access logs if we want to store them for long.
What I introduce here is essentially the same as what the article[\[3\]](#Reference) describes.

\* To "identify" here does not mean to know one's name, email, contact, etc., but to distinguish one person from others without knowing exactly who it is.

### Disclaimer

I am not a lawyer.
**This is not legal advice**.

## Overview of my architecture

The following diagram shows the overview of my architecture on AWS.

![AWS architecture](./aws-architecture.png)

The workflow is described below,
1. [`Amazon CloudFront`](#Amazon_CloudFront) saves an access logs file in [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket).
2. [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket) sends a PUT event to [`MaskAccessLogs queue`](#MaskAccessLogs_queue).
3. [`MaskAccessLogs queue`](#MaskAccessLogs_queue) invokes [`MaskAccessLogs`](#MaskAccessLogs).
4. [`MaskAccessLogs`](#MaskAccessLogs) transforms the new access logs file and saves the results in [`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket).
5. [`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket) sends a PUT event to [`DeleteAccessLogs queue`](#DeleteAccessLogs_queue).
6. [`DeleteAccessLogs queue`](#DeleteAccessLogs_queue) invokes [`DeleteAccessLogs`](#DeleteAccessLogs).
7. [`DeleteAccessLogs`](#DeleteAccessLogs) deletes the original access logs file from [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket).

You can find a [AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/) stack that provisions the above architecture\* for this website on [my GitHub repository](https://github.com/codemonger-io/codemonger/tree/e7562e9197a71cd914e1b8e4c964ca0adc74a859/cdk-ops); specifically [cdk-ops/lib/access-logs-etl.ts](https://github.com/codemonger-io/codemonger/blob/e7562e9197a71cd914e1b8e4c964ca0adc74a859/cdk-ops/lib/access-logs-etl.ts).
I have had a CDK-specific issue there, and please refer to the [Section "Identifying the S3 bucket for CloudFront access logs"](#Identifying_the_S3_bucket_for_CloudFront_access_logs) for more details.

The following subsections describe each component on the above diagram.

\* The latest code on my GitHub repository contains extra features like a data warehouse.

### Amazon CloudFront

`Amazon CloudFront` distributes the contents of our website through an [Amazon CloudFront](https://aws.amazon.com/cloudfront/) distribution and saves access logs in [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket).

### Amazon S3 access log bucket

`Amazon S3 access log bucket` is an [Amazon S3 (S3)](https://aws.amazon.com/s3/) bucket that stores access logs created by [`Amazon CloudFront`](#Amazon_CloudFront).
This bucket sends an event to [`MaskAccessLogs queue`](#MaskAccessLogs_queue) when an access logs file is PUT into this bucket.

### MaskAccessLogs queue

`MaskAccessLogs queue` is an [Amazon Simple Queue Service (SQS)](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html) queue that invokes [`MaskAccessLogs`](#MaskAccessLogs).
[`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket) sends an event to this queue when an access logs file is PUT into the bucket.

We could directly deliver events from [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket) to [`MaskAccessLogs`](#MaskAccessLogs), but I have not.
Please refer to the [Section "Why don't you directly connect an S3 bucket and Lambda function?"](#Why_don't_you_directly_connect_an_S3_bucket_and_Lambda_function?) for why I have avoided it.

### MaskAccessLogs

`MaskAccessLogs` is an [AWS Lambda (Lambda)](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) function that transforms access logs in [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket).
This function masks IP addresses, `c-ip` and `x-forwarded-for`, in the [CloudFront access logs](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/AccessLogs.html#LogFileFormat).
It drops (fills with zeros)
- 8 least significant bits (LSBs) out of 32 bits from an IPv4 address
- 96 LSBs out of 128 bits from an IPv6 address

This function also introduces a new column of row numbers to retain the original order of the access log records.
This function saves transformed results in [`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket).
While [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket) spreads access logs files flat, this function creates a folder hierarchy corresponding to the year, month, and day of access log records.
This folder structure will help a subsequent stage\* process access logs on a specific date in a batch.

You can find the implementation of this function in [cdk-ops/lambda/mask-access-logs/index.py on my GitHub repository](https://github.com/codemonger-io/codemonger/blob/e7562e9197a71cd914e1b8e4c964ca0adc74a859/cdk-ops/lambda/mask-access-logs/index.py).

\* An upcoming blog post will describe the later stage that loads access logs onto a data warehouse.

### Amazon S3 transformed log bucket

`Amazon S3 transformed log bucket` is an S3 bucket that stores access logs transformed by [`MaskAccessLogs`](#MaskAccessLogs).
This bucket sends an event to [`DeleteAccessLogs queue`](#DeleteAccessLogs_queue) when a transformed access logs file is PUT into this bucket.

### DeleteAccessLogs queue

`DeleteAccessLogs queue` is an SQS queue that invokes [`DeleteAccessLogs`](#DeleteAccessLogs).
[`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket) sends an event to this queue when a transformed access logs file is PUT into the bucket.

We could directly deliver events from [`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket) to [`DeleteAccessLogs`](#DeleteAccessLogs), but I have not.
Please refer to the [Section "Why don't you directly connect an S3 bucket and Lambda function?"](#Why_don't_you_directly_connect_an_S3_bucket_and_Lambda_function?) for why I have avoided it.

### DeleteAccessLogs

`DeleteAccessLogs` is a Lambda function that deletes an access logs file from [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket), which [`MaskAccessLogs`](#MaskAccessLogs) has transformed and saved in [`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket).

You can find the implementation of this function in [cdk-ops/lambda/delete-access-logs/index.py on my GitHub repository](https://github.com/codemonger-io/codemonger/blob/e7562e9197a71cd914e1b8e4c964ca0adc74a859/cdk-ops/lambda/delete-access-logs/index.py).

## Wrap-up

In this blog post, we learned [**storing CloudFront access logs for long may violate the GDPR**](#Are_CloudFront_access_logs_GDPR_compliant?).
Then I showed you [my AWS architecture to **reduce personal data from CloudFront access logs**](#Overview_of_my_architecture).

In an upcoming blog post, I will introduce how to load access logs onto a data warehouse backed by [Amazon Redshift Serverless](https://aws.amazon.com/redshift/redshift-serverless/).

## Appendix

### Identifying the S3 bucket for CloudFront access logs

If we omit the [S3 bucket for access logs](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.Distribution.html#logbucket) while [enabling logging](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.DistributionProps.html#enablelogging) when provisioning a CloudFront distribution ([`cloudfront.Distribution (Distribution)`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.Distribution.html)), the CDK allocates one on our behalf.
A drawback of this is that we cannot manage the identity of the S3 bucket that the CDK provisions.
Unfortunately, as the L2 construct (`Distribution`) provides no handy way to obtain the name of the S3 bucket for access logs, we have to dig the L1 layer of a CloudFront distribution ([`cloudfront.CfnDistribution (CfnDistribution)`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.CfnDistribution.html)).
To extract the name of the S3 bucket for access logs, we have to chase `Distribution` &rightarrow; `CfnDistribution` &rightarrow; [`CfnDistribution#distributionConfig`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.CfnDistribution.html#distributionconfig-1) &rightarrow; [`CfnDistribution.DistributionConfigProperty#logging`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.CfnDistribution.DistributionConfigProperty.html#logging) &rightarrow; [`CfnDistribution.LoggingProperty#bucket`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.CfnDistribution.LoggingProperty.html#bucket).

Here are steps to extract the name of the S3 bucket for access logs from `Distribution`:
1. Suppose you have `distribution: Distribution`.

2. Cast `distribution.node.defaultChild` as `CfnDistribution`:
    ```ts
    cfnDistribution = distribution.node.defaultChild as cloudfront.CfnDistribution;
    ```

3. Resolve `cfnDistribution.distributionConfig`.
   You cannot simply reference `cfnDistribution.distributionConfig` as `CfnDistribution.DistributionConfigProperty` because it may be an [`IResolvable`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.IResolvable.html):
    ```ts
    stack = Stack.of(distribution);
    distributionConfig = stack.resolve(cfnDistribution.distributionConfig) as CfnDistribution.DistributionConfigProperty;
    ```

4. Resolve `distributionConfig.logging`.
   You can neither simply reference `distributionConfig.logging` as `CfnDistribution.LoggingProperty` because it also may be an `IResolvable`:
    ```ts
    loggingConfig = stack.resolve(distributionConfig.logging) as CfnDistribution.LoggingProperty;
    ```

5. Extract the logical ID (ID in the CloudFormation template) of the S3 bucket from `loggingConfig.bucket`.
   According to my observation and [the CDK source code](https://github.com/aws/aws-cdk/blob/7d8ef0bad461a05caa41d140678481c5afb9d33e/packages/%40aws-cdk/aws-cloudfront/lib/distribution.ts#L443-L457), `loggingConfig.bucket` is an [intrinsic function `Fn::GetAtt`](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/intrinsic-function-reference-getatt.html) that obtains the regional domain name of the S3 bucket.
   So we extract the logical ID before referencing the name of the S3 bucket:
    ```ts
    bucketRef = loggingConfig.bucket;
    getAtt = bucketRef['Fn::GetAtt'];
    bucketLogicalId = getAtt[0];
    ```

6. Reference the name of the S3 bucket specified by `bucketLogicalId`:
    ```ts
    accessLogsBucketName = Fn.ref(bucketLogicalId);
    ```

You can find the implementation of the above steps in [cdk/lib/contents-distribution.ts#L122-L154 on my GitHub repository](https://github.com/codemonger-io/codemonger/blob/e7562e9197a71cd914e1b8e4c964ca0adc74a859/cdk/lib/contents-distribution.ts#L122-L154).

By the way, bringing your own S3 bucket as the access log destination shall be much easier.

### Why don't you directly connect an S3 bucket and Lambda function?

You can directly wire an S3 bucket and Lambda function with event notifications so that changes in the S3 bucket trigger the Lambda function.
Please refer to ["Using AWS Lambda with Amazon S3," _AWS Lambda Developer Guide_](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html)[\[4\]](#Reference) for how to do it.
However, as you can see on [my AWS architecture](#Overview_of_my_architecture), I have decided to insert an extra SQS queue between an S3 bucket and Lambda function instead of directly connecting them: [`Amazon S3 access log bucket`](#Amazon_S3_access_log_bucket) &rightarrow; [**`MaskAccessLogs queue`**](#MaskAccessLogs_queue) &rightarrow; [`MaskAccessLogs`](#MaskAccessLogs), and [`Amazon S3 transformed log bucket`](#Amazon_S3_transformed_log_bucket) &rightarrow; [**`DeleteAccessLogs queue`**](#DeleteAccessLogs_queue) &rightarrow; [`DeleteAccessLogs`](#DeleteAccessLogs).
This additional complexity allows you to easily turn on/off the invocation of a Lambda function in case there is any problem.
Otherwise, you have to delete the event trigger from a Lambda function to cut the event flow.

## Reference

1. [_General Data Protection Regulation (GDPR) Compliance Guidelines_ - https://gdpr.eu](https://gdpr.eu)
2. [_Is Google Analytics (3 &amp; 4) GDPR-compliant? \[Updated\] - https://piwik.pro/blog/is-google-analytics-gdpr-compliant/_](https://piwik.pro/blog/is-google-analytics-gdpr-compliant/)
3. [_Anonymize CloudFront Access Logs_ - https://cloudonaut.io/anonymize-cloudfront-access-logs/](https://cloudonaut.io/anonymize-cloudfront-access-logs/)
4. ["Using AWS Lambda with Amazon S3," _AWS Lambda Developer Guide_ - https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html](https://docs.aws.amazon.com/lambda/latest/dg/with-s3.html)