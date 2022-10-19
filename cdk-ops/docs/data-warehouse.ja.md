[English](./data-warehouse.md) / 日本語

# アクセスログ用のデータウェアハウス

このCDKスタックはアクセスログ用のデータウェアハウスを確保します。
データウェアハウスは[Amazon Redshift Serverless](https://aws.amazon.com/redshift/redshift-serverless/)を使って実現しています。

## AWSアーキテクチャ

以下の図はデータウェアハウスのAWSアーキテクチャを表しています。

![データウェアハウスのAWSアーキテクチャ](./data-warehouse-aws-architecture.png)

### Amazon CloudFront

`Amazon CloudFront`は我々のウェブサイトのコンテンツを配布しアクセスログを[`Amazon S3 access log bucket`](#amazon-s3-access-log-bucket)に保存します。

### Amazon S3 access log bucket

`Amazon S3 access log bucket`は[Amazon S3 (S3)](https://aws.amazon.com/s3/)のバケットで、[`Amazon CloudFront`](#amazon-cloudfront)が作成したアクセスログを格納します。
このバケットはアクセスログファイルがPUTされた際、[`MaskAccessLogs queue`](#maskaccesslogs-queue)にイベントを送ります。

### MaskAccessLogs queue

`MaskAccessLogs queue`は[Amazon Simple Queue Service (SQS)](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)のキューで、[`MaskAccessLogs`](#maskaccesslogs)を呼び出します。
[`Amazon S3 access log bucket`](#amazon-s3-access-log-bucket)はアクセスログファイルがPUTされた際、このキューにイベントを送ります。

### MaskAccessLogs

`MaskAccessLogs`は[AWS Lambda (Lambda)](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)関数で、[`Amazon S3 access log bucket`](#amazon-s3-access-log-bucket)のアクセスログを変換します。
この関数は[CloudFrontアクセスログ](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/AccessLogs.html#LogFileFormat)内のIPアドレス(`c-ip`と`x-forwarded-for`)をマスクします。
この関数はアクセスログレコードの順序を保持するために行番号のカラムも追加します。
この関数は変換結果を[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)に保存します。
[`Amazon S3 access log bucket`](#amazon-s3-access-log-bucket)はアクセスログファイルをフラットに展開するのに対して、この関数はアクセスログレコードの年月日に相当するフォルダ階層を作成します。
このフォルダ構造は[`LoadAccessLogs`](#loadaccesslogs)が特定の日付のアクセスログをバッチで処理するのに役立ちます。

### Amazon S3 transformed log bucket

`Amazon S3 transformed log bucket`はS3バケットで、[`MaskAccessLogs`](#maskaccesslogs)が変換したアクセスログを格納します。
このバケットは変換されたアクセスログファイルがPUTされると[`DeleteAccessLogs queue`](#deleteaccesslogs-queue)にイベントを送ります。

### DeleteAccessLogs queue

`DeleteAccessLogs queue`はSQSキューで、[`DeleteAccessLogs`](#deleteaccesslogs)を呼び出します。
[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)は変換されたアクセスログがPUTされるとこのキューにイベントを送ります。

### DeleteAccessLogs

`DeleteAccessLogs`はLambda関数で、[`MaskAccessLogs`](#maskaccesslogs)が変換し[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)に保存したアクセスログファイルを[`Amazon S3 access log bucket`](#amazon-s3-access-log-bucket)から削除します。

### Amazon Redshift Serverless

`Amazon Redshift Serverless`は[Amazon Redshift Serverless](https://aws.amazon.com/redshift/)のリソースをまとめたもので、データウェアハウスのコアとなります。

ひとつの[ファクトテーブル](https://en.wikipedia.org/wiki/Fact_table)と
- `access_log`

5つの[ディメンジョンテーブル](https://en.wikipedia.org/wiki/Dimension_(data_warehouse))からなります。
- `referer`
- `page`
- `edge_location`
- `user_agent`
- `result_type`

`Amazon Redshift Serverless`のノードはプライベートサブネットに配置されます。
Lambda関数([`PopulateDwDatabase`](#populatedwdatabase), [`LoadAccessLogs`](#loadaccesslogs), [`VacuumTable`](#vacuumtable))は[`Amazon Redshift Data API`](#amazon-redshift-data-api)を介して`Amazon Redshift Serverless`を操作します。

[Amazon Redshift Serverlessネームスペース](https://docs.aws.amazon.com/redshift/latest/mgmt/serverless-workgroup-namespace.html)のデフォルトロール([`Redshift namespace role`](#redshift-namespace-role))は[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)からオブジェクトを読み込むことができます。
`Amazon Redshift Serverless`は[`Gateway endpoint`](#gateway-endpoint)を介して[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)にアクセスします。

このCDKスタックは`Amazon Redshift Serverless`を確保する際に管理ユーザーを作成します。
[`AWS Secrets Manager`](#aws-secrets-manager)は管理ユーザーのパスワードを生成・管理します。

### Redshift namespace role

`Redshift namespace role`は[AWS Identity and Access Management (IAM)](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html)のロールで、[`Amazon Redshift Serverless`](#amazon-redshift-serverless)のネームスペースのデフォルトロールであり[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)からオブジェクトを読み込むことができます。

### Gateway endpoint

`Gateway endpoint`は[`Amazon Redshift Serverless`](#amazon-redshift-serverless)と[`Amazon S3 transformed log bucket`](#amazon-s3-transformed-log-bucket)の間のトラフィックがインターネットに出て行かないようにします。
詳しくは["Enhanced VPC routing in Amazon Redshift" - *Amazon Redshift Management Guide*](https://docs.aws.amazon.com/redshift/latest/mgmt/enhanced-vpc-routing.html)をご参照ください。

### AWS Secrets Manager

`AWS Secrets Manager`は[`Amazon Redshift Serverless`](#amazon-redshift-serverless)の管理ユーザーのパスワードを生成・管理します。
[*AWS Secrets Manager User Guide*](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)もご参照ください。

残念ながら、`AWS Secrets Manager`が管理するシークレットは[`Amazon Redshift Serverless`](#amazon-redshift-serverless)の管理パスワードと同期していません(初回生成時を除く)。
なので`AWS Secrets Manager`が新しいシークレットを生成してしまった際には、[`Amazon Redshift Serverless`](#amazon-redshift-serverless)の管理パスワードを手作業でリセットしなければなりません(対処方法は[READMEの「Amazon Redshift Serverlessネームスペースの管理ユーザー」](../README.ja.md#amazon-redshift-serverlessネームスペースの管理ユーザー)をご参照ください)。

### Amazon Redshift Data API

`Amazon Redshift Data API`は[`Amazon Redshift Serverless`](#amazon-redshift-serverless)のクライアントをデータベースへの接続を管理することから解放してくれます。
詳しくは["Using the Amazon Redshift Data API" - *Amazon Redshift Management Guide*](https://docs.aws.amazon.com/redshift/latest/mgmt/data-api.html)をご参照ください。

### PopulateDwDatabase

`PopulateDwDatabase`はLambda関数で、アクセスログを格納するデータベースとテーブルを[`Amazon Redshift Serverless`](#amazon-redshift-serverless)に作成します。
この関数は[`Amazon Redshift Serverless`](#amazon-redshift-serverless)の管理クレデンシャルを[`AWS Secrets Manager`](#aws-secrets-manager)から取得します。
管理者(`Admin`)はこのCDKスタックをデプロイした後にこの関数を呼び出さなければなりません。

### Amazon EventBridge

`Amazon EventBridge`は毎日午前2時(UTC)に[`LoadAccessLogs`](#loadaccesslogs)を実行する[Amazon EventBridgeのルール](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)を定義します。

### LoadAccessLogs

`LoadAccessLogs`はLambda関数で、指定した日付のアクセスログを[`Amazon Redshift Serverless`](#amazon-redshift-serverless)に読み込みます。
この関数はアクセスログの読み込みが終了すると[`AWS Step Functions`](#aws-step-functions)を実行します。
[`Amazon EventBridge`](#amazon-eventbridge)は1日に1回この関数を実行します。

この関数は[`Amazon EventBridge`](#amazon-eventbridge)から呼び出すことを想定していますが、適切なペイロードを与えて手作業で実行することもできます。

### AWS Step Functions

`AWS Step Functions`は[`Amazon Redshift Serverless`](#amazon-redshift-serverless)のすべてのテーブル(`access_log`, `referer`, `page`, `edge_location`, `user_agent`, `result_type`)に対して[`VacuumTable`](#vacuumtable)を実行する[AWS Step Functionsのステートマシン](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)を定義します。
[`VACUUM` SQLコマンド](https://docs.aws.amazon.com/redshift/latest/dg/r_VACUUM_command.html)の実行は同時に1つしか許されていないので、`AWS Step Functions`はテーブルをひとつずつ[`VacuumTable`](#vacuumtable)で処理します。

### VacuumTable

`VacuumTable`はLambda関数で、[`VACUUM` SQLコマンド](https://docs.aws.amazon.com/redshift/latest/dg/r_VACUUM_command.html)を指定したテーブルに対して実行します。
この関数は[`Amazon Redshift Serverless`](#amazon-redshift-serverless)の管理クレデンシャルを[`AWS Secrets Manager`](#aws-secrets-manager)から取得します。