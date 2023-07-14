+++
title = "APIが先か? CloudWatch Logsのロールが先か?"
description = "AWS CLIを介してAmazon API Gateway用のAmazon CloudWatch Logsロールを設定する方法"
date = 2023-07-14
draft = false
[extra]
hashtags = ["aws", "api_gateway", "cloudwatch"]
thumbnail_name = "thumbnail.png"
+++

CloudWatch LogsのロールがないためにAPI Gatewayのデプロイに失敗したことはありませんか?
このブログ投稿ではその解決方法を紹介します。

<!-- more -->

## 背景

[AWS CloudFormation (CloudFormation)](https://aws.amazon.com/cloudformation/)のスタックをデプロイする際に、次のようなエラーに遭遇したことはないですか?

```
Resource handler returned message: "CloudWatch Logs role ARN must be set in acc
ount settings to enable logging (Service: ApiGateway, Status Code: 400, Request
ID: 00000000-0000-0000-0000-000000000000)" (RequestToken: 00000000-0000-0000-00
00-000000000000, HandlerErrorCode: InvalidRequest)
```

このエラーの原因は単純(なはず)で、[Amazon API Gateway (API Gateway)](https://aws.amazon.com/api-gateway/)用の[Amazon CloudWatch Logs (CloudWatch Logs)](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html)ロールを設定していないからです。
ということで解決方法も単純で、CloudWatch LogsロールをAPI Gatewayに設定するだけです。以上!

ところが、アカウントにAPI GatewayのAPIをまだ一度もデプロイしたことがない場合は単純には解決しません。
API Gatewayのコンソールは、少なくともひとつ以上のAPIをデプロイしない限りCloudWatch Logsのロールを設定するページを表示してくれないのです。

## 解決方法

考えられる解決方法は:
1. **API Gatewayのコンソールを介する方法**: ログを無効にしてAPIをデプロイした後、API GatewayのコンソールでCloudWatch Logsのロールを設定。
   それからログを有効にしてAPIを再デプロイする。
2. **AWS CLIを介する方法**: CloudWatch Logsのロールを[AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-welcome.html)を介して設定。
   それからログを有効にしてAPIをデプロイする。
3. **CDK\*を介する方法**: CDKで[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)を設定する際に[`cloudWatchRole`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApiProps.html#cloudwatchrole)プロパティを有効にする。
   **お勧めしません**。

[次の節](#AWS_CLIを介してCloudWatch_Logsロールを設定する)で、2番目の方法を紹介します。
[節「なぜcloudWatchRoleを有効化すべきでないか?」](#なぜcloudWatchRoleを有効化すべきでないか?)では、なぜ`cloudWatchRole`を有効化すべきでないかについても解説します。

\* CDK: [AWS Cloud Development Kit](https://aws.amazon.com/cdk/)

## AWS CLIを介してCloudWatch Logsロールを設定する

API Gateway用のCloudWatch Logsロールを設定するのに使うAWS CLIのコマンドはどれでしょうか?
残念なことに、[AWSのドキュメント](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html) [\[1\]](#参考)はAWS CLIを介して設定する方法をなぜか紹介していません。
実は **[`apigateway update-account`](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/apigateway/update-account.html)がそのコマンド** [\[2\]](#参考)なのですが、
分かりにくくないですか?
それはさておき、コマンドの[サンプル](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/apigateway/update-account.html#examples)ではまさにCloudWatch Logsのロールを設定する方法を紹介しています。

```sh
aws apigateway update-account --patch-operations op='replace',path='/cloudwatchRoleArn',value='arn:aws:iam::123412341234:role/APIGatewayToCloudWatchLogs'
```

IAMロールを作成する方法はこの投稿の範囲外ですが、[補足](#API_Gatewayのログ用のIAMロールを作成する)で紹介します。

## なぜcloudWatchRoleを有効化すべきでないか?

`cloudWatchRole`オプションを使うとお手軽な気がしますが、将来的に分かりにくいエラーが起きる可能性があります。

問題が起こる可能性があるのはCDK (CloudFormation)スタックを削除したときです。
スタックを削除すると、そのスタックが確保したCloudWatch Logsのロールも同時に削除されます。
CloudWatch Logsロールはアカウントレベルの設定なので、**アカウント内の他のすべてのAPIが存在しないロールのせいでクラッシュし始めます**。

## まとめ

この投稿では、以下を紹介しました。
- [AWS CLIを介してAPI Gateway用のCloudWatch Logsのロールを設定する方法](#AWS_CLIを介してCloudWatch_Logsロールを設定する)
- [なぜCDKで`RestApi`の`cloudWatchRole`オプションを有効化すべきでないか](#なぜcloudWatchRoleを有効化すべきでないか?)

## 補足

### API Gatewayのログ用のIAMロールを作成する

以下のステップで、AWS CLIを使ってAPI Gatewayのログ用のIAMロールを作成・設定できます。

1. `apigateway.amazonaws.com`が引き受ける(assume)ことのできるIAMロールを作成

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

2. ステップ1で作成したIAMロールにAWSのマネージドポリシー`AmazonAPIGatewayPushToCloudWatchLogs`を追加

    ```sh
    aws iam attach-role-policy --role-name APIGatewayToCloudWatchLogs --policy-arn arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs
    ```

## 参考

1. [Setting up CloudWatch logging for a REST API in API Gateway - _Amazon API Gateway Developer Guide_](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html)
2. [apigateway update-account - _AWS CLI Command Reference_](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/apigateway/update-account.html#examples)