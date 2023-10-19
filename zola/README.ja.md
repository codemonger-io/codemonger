[English](./README.md) / 日本語

# Zolaプロジェクト for codemonger

このZolaプロジェクトはcodemongerウェブサイトのコンテンツを生成します。

## コンテンツを生成する

以下のコマンドは`public`フォルダ内にcodemongerウェブサイトのコンテンツを出力します。

```sh
zola build
```

開発ステージにデプロイする際は、`--base-url`オプションを追加してください。

```sh
zola build --base-url https://$CONTENTS_DISTRIBUTION_DOMAIN_NAME
```

`$CONTENTS_DISTRIBUTION_DOMAIN_NAME`を開発ステージのCloudFront Distributionのドメイン名で置き換えてください。
CloudFront Distributionを確保する方法については[`../cdk`](../cdk/README.ja.md)フォルダの解説をご覧ください。
以下は開発ステージ用のコマンドです。

```sh
CONTENTS_DISTRIBUTION_DOMAIN_NAME=`AWS_PROFILE=codemonger-jp aws cloudformation describe-stacks --stack-name codemonger-development --query "Stacks[0].Outputs[?OutputKey=='ContentsDistributionDomainName']|[0].OutputValue" --output text`
```

## コンテンツをデプロイする

[コンテンツを生成](#コンテンツを生成する)したら、`public`フォルダの中身をコンテンツ用S3バケットにコピーしてください。

```sh
aws s3 sync --delete --exclude "*.DS_Store" ./public s3://$CONTENTS_BUCKET_NAME/
```

`CONTENTS_BUCKET_NAME`をコンテンツ用S3バケットの名前に置き換えてください。
S3バケットを確保する方法については[`../cdk`](../cdk/README.ja.md)フォルダの解説をご覧ください。
以下は開発ステージ用のコマンドです。

```sh
CONTENTS_BUCKET_NAME=`AWS_PROFILE=codemonger-jp aws cloudformation describe-stacks --stack-name codemonger-development --query "Stacks[0].Outputs[?OutputKey=='ContentsBucketName']|[0].OutputValue" --output text`
```

## ブログを書く

### ツイートボタンにハッシュタグを追加する

各ブログ投稿の[Front Matter](https://www.getzola.org/documentation/content/page/#front-matter)は`extra`データに`hashtags`オプションを含むことができます。
このオプションはブログ投稿のツイートボタンに追加したいハッシュタグ文字列の配列を受け付けます。
以下の例はツイートボタンに`"hashtags=aws,cloudfront"`を追加します。

```
+++
title = "CloudFrontを介してS3からコンテンツを提供する"
date = 2022-06-20
[extra]
hashtags = ["aws", "cloudfront"]
+++
```

### サムネイル画像を追加する

各ブログ投稿の[Front Matter](https://www.getzola.org/documentation/content/page/#front-matter)は`extra`データに`thumbnail_name`オプションを含むことができます。
このオプションはブログ投稿の冒頭に表示されSNSのサムネイル(例: Twitterカード)として現れる画像ファイルの名前を受け付けます。
以下の例はブログページの`index.md`ファイルと同じフォルダにある`"thumbnail.png"`という画像ファイルをサムネイルとして表示します。

```
+++
title = "Omit<Type, Keys>が(期待にどおりに)機能しないとき"
date = 2022-07-12
[extra]
thumbnail_name = "thumbnail.png"
+++
```

ブログ投稿にサムネイル画像を追加するには、ブログページのフォルダを作成し、そこにサムネイル画像ファイルを置きます。
画像ファイルはブログページの`index.md`ファイルと同じフォルダにあるべきで、そうしないとSNSのサムネイルが機能しないかもしれません。