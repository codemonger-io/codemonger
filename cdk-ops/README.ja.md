[English](./README.md) / 日本語

# codemonger運用のためのCDKスタック

これはcodemongerウェブサイトを運用するためのAWSリソースを確保するCDKスタックです。
codemongerウェブサイトのコンテンツを保管し配信するAWSリソースを確保するCDKスタックは[`../cdk`](../cdk)に定義されています。

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

## 事前準備

### コンテンツのためのCDKスタックをデプロイする

このCDKスタックをデプロイする前にcodemongerウェブサイトのコンテンツのためのCDKスタックをデプロイしなければなりません。
開発用と製品用の両方のスタックが必要です。
デプロイの仕方については[`../cdk`](../cdk)を参照ください。

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

`cdk deploy`コマンドはCDKスタックを[`AWS_PROFILE`環境変数](#awsprofileを設定する)に紐づくAWSアカウントにデプロイします。

```sh
npx cdk deploy --toolkit-stack-name $TOOLKIT_STACK_NAME -c "@aws-cdk/core:bootstrapQualifier=$TOOLKIT_STACK_QUALIFIER"
```

CDKスタックをデプロイすると、CloudFormationスタック`codemonger-operation`が作成または更新されます。

## なぜExportを使わないのか?

このCDKスタックはメインとなるcodemongerのCloudFormationスタックに依存します。
なのでメインスタックからこのスタックに[リソースをエクスポート](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-cfn-stack-exports.html)することでこのスタックとメインスタックとのリンクを強化すべきと思われるかもしれません。
しかし、私は過去にExportを使ってみて苦い経験をしました。
スタックが別のスタックのExportに依存すると、Exportされたリソースは前者のスタックからの依存が削除されるまで置き換えることができません。
依存関係をスタックから削除するのはやっかいです。なぜなら代わりの偽のリソースが必要だからです。
リソースを頻繁に作り直すかもしれないので開発初期には特にイライラすることになります。
ということでExportせずにメインスタックのOutputを取得することにしました。

幸い、CDKだとメインスタックからOutputを取得してこのスタックへのパラメータとして渡すスクリプトを書くのが簡単になります。