+++
title = "FlechasDB"
description = "サーバーレスと相性のよいベクトルデータベース"
date = 2023-10-19
draft = false
weight = 1
[extra]
hashtags = ["FlechasDB", "vector-database", "serverless"]
thumbnail_name = "flechasdb-brand.png"
+++

サーバーレスと相性のよいベクトルデータベースを意のままに

<!-- more -->

**FlechasDB**は[サーバーレス](https://aws.amazon.com/serverless/)と相性のよい[ベクトルデータベース](https://www.pinecone.io/learn/vector-database/)[^1]です。

[^1]: _What is a Vector Database?_ by [Pinecone](https://www.pinecone.io). ベクトルデータベースに関する[ウィキペディア](https://www.wikipedia.org)ページが見当たらないのは驚きでした。

## 特徴

1. データベースファイルを[Amazon S3](https://aws.amazon.com/s3/)バケットに保存・読込
2. [Amazon Linux 2](https://aws.amazon.com/amazon-linux-2/?amazon-linux-whats-new.sort-by=item.additionalFields.postDateTime&amazon-linux-whats-new.sort-order=desc)[^2]で動く

今後の機能向上にもご期待ください!

[^2]: Amazon Linux 2はこの記事を書いている時点で[AWS Lambda](https://aws.amazon.com/lambda/)インスタンスの標準オペレーティングシステムです。

## 始め方

コアライブラリの`flechasdb`とAmazon S3拡張の`flechasdb-s3`はそれぞれ以下のGitHubレポジトリで入手できます。
- <https://github.com/codemonger-io/flechasdb>
- <https://github.com/codemonger-io/flechasdb-s3>

[Amazon Linux 2](https://aws.amazon.com/amazon-linux-2/?amazon-linux-whats-new.sort-by=item.additionalFields.postDateTime&amazon-linux-whats-new.sort-order=desc)用の[カスタムLambdaランタイム](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html)に組み込むことで、`flechasdb`と`flechasdb-s3`を[AWS Lambda](https://aws.amazon.com/lambda/)で利用できます。
`flechasdb`も`flechasdb-s3`も[Rust](https://www.rust-lang.org)で記述されていますので、[`cargo-lambda`](https://www.cargo-lambda.info)を使うと便利でしょう。
`flechasdb`と`flechasdb-s3`を使うLambda関数を[AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/)でデプロイする例が、以下のGitHubレポジトリにあります。
- <https://github.com/codemonger-io/mumble/tree/main/cdk>
- <https://github.com/codemonger-io/mumble-embedding/tree/main/cdk>

## FlechasDBの実例

[Mumble](../mumble/)は検索機能を実現するのにFlechasDBを使っています。
投稿(_ゴニョゴニョ_)に対して計算した[OpenAIのエンべディング](https://platform.openai.com/docs/models/embeddings)からFlechasDBのデータベースを構築し、[Amazon S3](https://aws.amazon.com/s3/)バケットにデータベースファイルを格納しています。
[KikuoのMumbleプロフィール](https://mumble.codemonger.io/viewer/users/kemoto/)で試すことができます。

![similarity search demo](./similarity-search-demo.gif)

## 背景

[Pinecone](https://www.pinecone.io)や[Milvus](https://milvus.io)など、世の中にはもっと優れたプロダクトやサービスがあります。
[`Faiss`](https://github.com/facebookresearch/faiss)はベクトルサーチではデファクトのライブラリで`flechasdb`よりよほど高速で信頼性も高いでしょう。

正直、この「車輪の再発明」は私(Kikuo)の興味本位で行ったものです。
- IVFPQインデクシングの仕組み[^3]
- [Rust](https://www.rust-lang.org)オプティマイザによる自動ベクトル化を使いこなす方法[^4]
- Asyncな[Rust](https://www.rust-lang.org)の書き方

しかし、小規模なプロジェクトにとってFlechasDBは最安のソリューションのひとつではないかと思いますので、
ベクトルデータベースの**フィージビリティスタディにFlechasDB**を検討してみてはいかがでしょうか?

[^3]: _Product Quantizers for k-NN Tutorial Part 2_ - <https://mccormickml.com/2017/10/22/product-quantizer-tutorial-part-2/>

[^4]: _Taking Advantage of Auto-Vectorization in Rust_ - <https://www.nickwilcox.com/blog/autovec/>