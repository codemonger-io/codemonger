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

## コンテンツをデプロイする

[コンテンツを生成](#コンテンツを生成する)したら、`public`フォルダの中身をコンテンツ用S3バケットにコピーしてください。

```sh
aws s3 cp --recursive ./public s3://$CONTENTS_BUCKET_NAME/
```

`CONTENTS_BUCKET_NAME`をコンテンツ用S3バケットの名前に置き換えてください。
S3バケットを確保する方法については[`../cdk`](../cdk/README.ja.md)フォルダの解説をご覧ください。