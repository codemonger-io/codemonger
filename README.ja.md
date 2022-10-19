[English](./README.md) / 日本語

# codemonger

![codemonger](docs/imgs/codemonger.svg)

`codemonger.io`のウェブサイトを管理するためのレポジトリです。

ウェブサイトは[AWS](https://aws.amazon.com)でホストしています。

## AWSのリソースを管理する

サブフォルダ[`cdk`](cdk/README.ja.md)をご覧ください。

## コンテンツを管理する

サブフォルダ[`zola`](zola/README.ja.md)をご覧ください。

## DevOps

以下の["DevOps"](https://en.wikipedia.org/wiki/DevOps)機能も提供します。
- Continuous Delivery: このレポジトリの`main`ブランチが更新されると、codemongerウェブサイトを更新するためのワークフローが開始します。
- データウェアハウス: codemongerウェブサイトのアクセスログはデータウェアハウスに格納されます。

詳しくはサブフォルダ[`cdk-ops`](cdk-ops/README.ja.md)をご覧ください。