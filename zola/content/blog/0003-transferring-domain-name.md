+++
title = "Moving the domain name between distributions"
date = 2022-06-27
draft = false
[extra]
hashtags = ["AWS", "Route53", "CloudFront", "CertificateManager"]
+++

I moved the domain name from one CloudFront distribution to another.
This blog post shows my findings on domain name move.

<!-- more -->

## Background

As I wrote in the [last blog post](/blog/0002-serving-contents-from-s3-via-cloudfront), I am using an [Amazon CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html) distribution to deliver the contents of this website.
And I am using [Amazon Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/Welcome.html) to manage DNS records for this website.

I had another older CloudFront distribution associated with the domain name `codemonger.io` before the current distribution.
While I had described the former distribution with a plain [AWS CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) template, I started over with the [AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/) to write the new one.

When I first tried to deploy my new CDK stack, the deployment failed with the following error message,

> One or more of the CNAMEs you provided are already associated with a different resource.

According to [this article](https://aws.amazon.com/premiumsupport/knowledge-center/resolve-cnamealreadyexists-error/), I had to move the domain name from the older CloudFront distribution to the new one.

This blog post covers only topics specific to my challenges.
Please refer to the links listed in the [_Reference_ section](#Reference) for other general topics.

## Challenges

Although Amazon's documentation explains [how to move a domain name between two CloudFront distributions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html#alternate-domain-names-move), I could not figure out answers to the following two questions I had.
1. [Do the steps in the documentation work for an apex domain name?](#Question_One:_Do_the_steps_in_the_documentation_work_for_an_apex_domain_name?)
2. [When do I have to replace my A records in Route 53?](#Question_Two:_When_do_I_have_to_replace_my_A_records_in_Route_53?)

I also had a [challenge configuring my CDK stack](#Provisioning_a_new_CloudFront_distribution_with_CDK).

### Question One: Do the steps in the documentation work for an apex domain name?

The answer is **Yes**.

The domain name `codemonger.io` I wanted to move is an apex domain.
While I was googling about domain name move, I came across [this article](https://dev.classmethod.jp/articles/swap-cname-between-cloudfront-distribution/) (written in Japanese).
According to the article, [we cannot move an apex domain without the help of AWS Support](https://dev.classmethod.jp/articles/swap-cname-between-cloudfront-distribution/#toc-7)\*.
Fortunately, the information was outdated and [Amazon's documentation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html#alternate-domain-names-move-options) clearly says it is possible without AWS Support.

> Use the associate-alias command in the AWS CLI to move the alternate domain name. This method works for all same-account moves, **including when the alternate domain name is an apex domain** (also called a root domain, like example.com). For more information, see Use associate-alias to move an alternate domain name.

A bit unclear to me still was how I had to name a [DNS TXT record](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html#TXTFormat) which I needed to prove my ownership of the domain.
Because the example domain in [Amazon's documentation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html#alternate-domain-names-move-options) was not an apex domain but a subdomain `www.example.com` and the name of the TXT record was `_www.example.com`.
Guessing from [this article](https://aws.amazon.com/premiumsupport/knowledge-center/resolve-cnamealreadyexists-error/), I tried the following DNS record,
- name: `_.codemonger.io`
- type: TXT
- value: dexample123456.cloudfront.net _(demonstration purpose only)_
- TTL: 300
- policy: simple routing

After adding the above TXT record, the [`associate-alias`](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/cloudfront/associate-alias.html) command succeeded and `codemonger.io` started delivering contents from the new CloudFront distribution.

\* Later, I found that the article had an [amendment](https://dev.classmethod.jp/articles/cloudfront-cnamealreadyexists-fix-flowchart/).

### Question Two: When do I have to replace my A records in Route 53?

The answer is **after running the `associate-alias` command**.

The [documentation](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/cloudfront/associate-alias.html) about the `associate-alias` command says

> With this operation you can move an alias that’s already in use on a CloudFront distribution to a different distribution in one step. This prevents the downtime that could occur if you first remove the alias from one distribution and then separately add the alias to another distribution.

I understood that it turns two operations, remove and add an alias, into one.
However, when I had to replace my A and AAAA records (A records) in Route 53 was not clear to me.
I thought if I left my A records pointing to my old CloudFront distribution, Route 53 would have continued to route traffic to `codemonger.io` to the old distribution.
This could have still led to the downtime until I would have made my A records point to the new distribution.
So I tried to set the routing policy of A records to the [multivalue answer routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-multivalue.html), but I could not make a multivalue answer A record point to a CloudFront distribution\*.
Thus, I decided to try `associate-alias` without updating my A records.
My website had not gotten much traffic anyway.

After running `associate-alias`, traffic to `codemonger.io` started to be routed to the new distribution.
So it seems that `associate-alias` also forwards traffic to the old distribution to the new one.

\* It complained that I had to specify an IP address instead.

### Provisioning a new CloudFront distribution with CDK

To run the `associate-alias` command, I needed a new CloudFront distribution configured with the valid SSL/TLS certificate\* of `codemonger.io` but a blank domain name.
Unfortunately, CDK did not allow me to configure the SSL/TLS certificate of the [Distribution](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.Distribution.html) while keeping the alternate domain name blank.
So I took the following steps as a workaround,

1. Configure the CDK stack to provision a CloudFront distribution without the SSL/TLS certificate and alternate domain name.
2. Deploy the CDK stack.
3. On the AWS console, assign the SSL/TLS certificate of `codemonger.io` to the new distribution but keep the alternate domain name blank.
4. Move the domain name from the old distribution to the new one.
5. Configure the CDK stack to provision the CloudFront distribution with the SSL/TLS certificate and alternate domain name `codemonger.io`.

I introduced a CDK context so that I can switch the behavior between the step 1 and 5 without editing the scripts.

The scripts for the CDK stack are available on the [GitHub repository](https://github.com/codemonger-io/codemonger/tree/main/cdk).

\* I had obtained my SSL/TLS certificate through [AWS Certificate Manager](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html).

## Reference

Please refer to the following documentation for general topics related to Amazon Route 53, AWS Certificate Manager, and Amazon CloudFront,
- [Routing traffic to an Amazon CloudFront distribution by using your domain name](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-to-cloudfront-distribution.html)
- [Requesting a public certificate](https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html)
- [Requirements for using SSL/TLS certificates with CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html)