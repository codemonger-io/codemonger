[English](./README.md) / 日本語

# codemonger運用のためのCDKスタック

これはcodemongerウェブサイトを運用するためのAWSリソースを確保するCDKスタックです。
codemongerウェブサイトのコンテンツを保管し配信するAWSリソースを確保するCDKスタックは[`../cdk`](../cdk/README.ja.md)に定義されています。

このスタックはCDKバージョン2で記述されています。

## 自動化されるワークフロー

このCDKスタックは以下のワークフローを自動化する[AWS CodePipeline](https://docs.aws.amazon.com/codepipeline/latest/userguide/welcome.html) Pipelineを確保します。
1. このレポジトリの`main`ブランチからソースコードを取得する。
2. [`zola build`](https://www.getzola.org/documentation/getting-started/cli-usage/#build)コマンドを`zola`フォルダで開発用に実行する。
3. `zola/public`フォルダを開発用のコンテンツバケットにアップロードする。
4. 開発用ウェブサイトのコンテンツを人手でレビューする。
5. コンテンツを承認する。
6. `zola build`コマンドを`zola`フォルダで製品用に実行する。
7. `zola/public`フォルダを製品用のコンテンツバケットにアップロードする。

ワークフローは`main`ブランチが更新された際(例えばプルリクエストがマージされた際)に開始されます。
プルリクエストの作成前に作成者は[`zola serve`](https://www.getzola.org/documentation/getting-started/cli-usage/#serve)でローカルにコンテンツをレビューしなければなりません。

## アクセスログ用のデータウェアハウス

このCDKスタックはアクセスログ用のデータウェアハウスを確保します。
詳しくは[`docs/data-warehouse.ja.md`](./docs/data-warehouse.ja.md)をご参照ください。

## 事前準備

### コンテンツのためのCDKスタックをデプロイする

このCDKスタックをデプロイする前にcodemongerウェブサイトのコンテンツのためのCDKスタックをデプロイしなければなりません。
開発用と製品用の両方のスタックが必要です。
デプロイの仕方については[`../cdk`](../cdk/README.ja.md)を参照ください。

### このレポジトリに接続するCodeStarプロジェクトを作成する

このCDKスタックが確保するAWS CodePipeline Pipelineはこのレポジトリが更新された際にアクションを開始するためにこのレポジトリに接続しなければなりません。
[AWS CodeStar](https://docs.aws.amazon.com/codestar/latest/userguide/welcome.html)はGitHubレポジトリとPipelineを接続します。
このプロジェクトは`lib/github-connection-config.ts`ファイルがこのGitHubレポジトリに関する以下のような情報を格納しているものと想定しています。

```ts
export const GITHUB_OWNER = 'codemonger-io';
export const GITHUB_REPOSITORY = 'codemonger';
export const GITHUB_BRANCH = 'main';
export const GITHUB_CONNECTION_ARN = 'arn:aws:codestar-connections:ap-northeast-1:<Account ID>:connection/<Connection ID>';
```

`GITHUB_CONNECTION_ARN`にあなたのGitHub ConnectionのARNを設定する必要があります。

`lib/github-connection-config.ts`はこのレポジトリにプッシュされません。

## CDKスタックをいじる

### 依存関係を解決する

開発を始める前に依存関係を解決しなければなりません。

```sh
npm install
```

### AWS_PROFILEを設定する

このドキュメントは十分なクレデンシャルを持つAWSプロファイルが[`AWS_PROFILE`](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html)環境変数に設定されているものと想定しています。
以下は私の場合の例です。

```sh
export AWS_PROFILE=codemonger-jp
```

### ツールキットスタック名を設定する

[コンテンツ用のCDKスタック](../cdk/README.ja.md#ツールキットスタック名を設定する)がデプロイしたツールキットスタックを再利用します。
ということでこのプロジェクトはツールキットスタック名が`"codemonger-toolkit-stack"`であり`TOOLKIT_STACK_NAME`変数に格納されているものと想定しています。

```sh
TOOLKIT_STACK_NAME=codemonger-toolkit-stack
```

### Synthesizer Qualifierを設定する

[コンテンツ用のCDKスタック](../cdk/README.ja.md#synthesizer-qualifierを設定する)がデプロイしたツールキットスタックを再利用します。
ということでこのドキュメントはQualifierが`"cdmngr2022"`であり`TOOLKIT_STACK_QUALIFIER`変数に格納されているものと想定しています。

```sh
TOOLKIT_STACK_QUALIFIER=cdmngr2022
```

### ツールキットスタックを確保する

[コンテンツ用のCDKスタック](../cdk/README.ja.md#ツールキットスタックを確保する)がデプロイしたツールキットスタックを再利用します。

### CloudFormationテンプレートを合成する

このCDKスタックをデプロイする前に、どのようなCloudFormationテンプレートがデプロイされるのかを確認したいかもしれません。
`cdk synth`コマンドはCloudFormationテンプレートをデプロイせずに出力します。

```sh
npx cdk synth -c "@aws-cdk/core:bootstrapQualifier=$TOOLKIT_STACK_QUALIFIER"
```

### CDKスタックをデプロイする

`cdk deploy`コマンドはCDKスタックを[`AWS_PROFILE`環境変数](#aws_profileを設定する)に紐づくAWSアカウントにデプロイします。

```sh
npx cdk deploy --toolkit-stack-name $TOOLKIT_STACK_NAME -c "@aws-cdk/core:bootstrapQualifier=$TOOLKIT_STACK_QUALIFIER"
```

CDKスタックをデプロイすると、CloudFormationスタック`codemonger-operation`が作成または更新されます。

#### Amazon Redshift Serverlessネームスペースの管理ユーザー

このCDKスタックは[Amazon Redshift Serverless (Redshift Serverless)](https://docs.aws.amazon.com/redshift/latest/mgmt/working-with-serverless.html)ネームスペースの確保時に管理ユーザーを作成します。
管理ユーザーのパスワードは[AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)の管理するシークレットとして作成されます。
**CloudFormationはRedshift Serverlessネームスペースの管理ユーザー名とパスワードを一度作成すると変更することができない**ので、**シークレットが更新(再生成)されると管理パスワードが失われます**。

これが起きてしまったら、別のスーパーユーザーで管理パスワードを手作業で更新しなければなりません。
Redshift Serverlessコンソールで管理パスワードを変更するか、CloudFormationの実行ロール\*で[Query Editor v2](https://aws.amazon.com/redshift/query-editor-v2/)を実行して管理パスワードをリセットすることもできます。

\* Redshift Serverlessはネームスペースの作成者に管理権限を与えます。
Redshift Serverlessネームスペースの確保にCDK (CloudFormation)を使用しているので、CloudFormationの実行ロールがその力を授かることになります。

## デプロイ後

### データウェアハウスにデータベースとテーブルを作成する

このCDKスタックをデプロイした後、データウェアハウスにデータベースとテーブルを作成しなければなりません。
以下のコマンドを実行してください。

```sh
npm run populate-dw -- development
npm run populate-dw -- production
```

`populate-dw`スクリプトは[`bin/populate-data-warehouse.js`](./bin/populate-data-warehouse.js)を実行します。

この手続きはCDKスタックを最初に確保した際に一度だけ必要です。

### 日々のアクセスログ読み込みを有効にする

このCDKスタックは、CloudFrontのアクセスログをデータウェアハウスに読み込むLambda関数を1日に1回実行する[Amazon EventBridge](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html)のルールを確保します。
ルールはデフォルトで無効化されているので、日々のアクセスログ読み込みを実行するには有効化しなければなりません。
開発用\*と製品用で別々のルールがあります。

確実に[データウェアハウスにデータベースとテーブルを作成](#データウェアハウスにデータベースとテーブルを作成する)しておいてください。

\* 開発用のルールは**毎時**トリガーされます。

## なぜExportを使わないのか?

このCDKスタックはメインとなるcodemongerのCloudFormationスタックに依存します。
なのでメインスタックからこのスタックに[リソースをエクスポート](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-exports.html)することでこのスタックとメインスタックとのリンクを強化すべきと思われるかもしれません。
しかし、私は過去にExportを使ってみて苦い経験をしました。
スタックが別のスタックのExportに依存すると、Exportされたリソースは前者のスタックからの依存が削除されるまで置き換えることができません。
依存関係をスタックから削除するのはやっかいです。なぜなら代わりの偽のリソースが必要だからです。
リソースを頻繁に作り直すかもしれないので開発初期には特にイライラすることになります。
ということでExportせずにメインスタックのOutputを取得することにしました。

幸い、CDKだとメインスタックからOutputを取得してこのスタックへのパラメータとして渡すスクリプトを書くのが簡単になります。