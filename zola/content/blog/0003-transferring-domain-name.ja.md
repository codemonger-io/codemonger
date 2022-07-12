+++
title = "Distribution間でドメイン名を移行する"
description = "このブログ投稿はあるCloudFront Distributionから別のDistributionにドメイン名を移動する上で気づいたことを紹介します。"
date = 2022-06-27
draft = false
[extra]
hashtags = ["AWS", "Route53", "CloudFront", "CertificateManager", "CDK"]
+++

ドメイン名をあるCloudFront Distributionから別のDistributionに移動しました。
このブログ投稿はドメイン名の移動で気づいたことを紹介します。

<!-- more -->

## 背景

[前回のブログ投稿](/ja/blog/0002-serving-contents-from-s3-via-cloudfront)で書いたとおり、[Amazon CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Introduction.html) Distributionをこのウェブサイトのコンテンツを配信するのに使っています。
またこのウェブサイトに関するDNSレコードの管理には[Amazon Route 53](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/Welcome.html)を使っています。

現在のCloudFront Distributionの前に古い別のDistributionをドメイン名`codemonger.io`に関連づけていました。
以前のDistributionは生の[AWS CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html)テンプレートで記述していましたが、新しいDistributionを書くのに[AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/)でやり直しました。

新しいCDKスタックを最初にデプロイしようとしたとき、以下のエラーメッセージで失敗しました。

> One or more of the CNAMEs you provided are already associated with a different resource.

[こちらの記事](https://aws.amazon.com/premiumsupport/knowledge-center/resolve-cnamealreadyexists-error/)によると、古いCloudFront Distributionから新しいDistributionにドメイン名を移動させなければならないということでした。

このブログ投稿は私の課題に特化したトピックのみをカバーしています。
他の一般的なトピックについては[「参考」節](#参考)にリストされているリンクを参照してください。

## 課題

Amazonのドキュメントは[ドメイン名を2つのCloudFront Distribution間で移動する方法](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html#alternate-domain-names-move)を説明してくれていますが、以下の私の2つの疑問に対する答えを見出すことができませんでした。
1. [ドキュメントのステップはApex(ルート)ドメイン名に対しても機能するのか?](#疑問1:_ドキュメントのステップはルートドメイン名に対しても機能するのか?)
2. [Route 53のAレコードをいつ置き換えるべきか?](#疑問2:_Route_53のAレコードをいつ置き換えるべきか?)

[CDKスタックの設定でも課題](#CDKで新しいCloudFront_Distributionを確保する)がありました。

### 疑問1: ドキュメントのステップはルートドメイン名に対しても機能するのか?

答えは **「はい」** です。

私が移動したかったドメイン名`codemonger.io`はルートドメインです。
ドメイン名の移動についてググっていると、[こちらの記事](https://dev.classmethod.jp/articles/swap-cname-between-cloudfront-distribution/)を見つけました。
記事によると、[AWS Supportの力を借りないとルートドメインは移動できない](https://dev.classmethod.jp/articles/swap-cname-between-cloudfront-distribution/#toc-7)ようです\*。
幸いこれは古い情報で[Amazonのドキュメント](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html#alternate-domain-names-move-options)にはAWS Supportなしでも可能であるとはっきり書いてあります。

> Use the associate-alias command in the AWS CLI to move the alternate domain name. This method works for all same-account moves, **including when the alternate domain name is an apex domain** (also called a root domain, like example.com). For more information, see Use associate-alias to move an alternate domain name.

それでもよく分からなかったのはドメイン所有の事実を示すために必要な[DNSのTXTレコード](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/ResourceRecordTypes.html#TXTFormat)にどのような名前をつけたらよいかということでした。
[Amazonのドキュメント](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html#alternate-domain-names-move-options)に例示されているドメインはルートドメインではなく`www.example.com`というサブドメインであり、TXTレコードの名前は`_www.example.com`だったからです。
[こちらの記事](https://aws.amazon.com/premiumsupport/knowledge-center/resolve-cnamealreadyexists-error/)から察して、以下のDNSレコードを試しました。
- name: `_.codemonger.io`
- type: TXT
- value: dexample123456.cloudfront.net _(例示です)_
- TTL: 300
- policy: simple routing

上記のTXTレコードを追加した後、[`associate-alias`](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/cloudfront/associate-alias.html)コマンドは成功して`codemonger.io`は新しいCloudFront Distributionからコンテンツを配信し始めました。

\* 後で記事には[補足](https://dev.classmethod.jp/articles/cloudfront-cnamealreadyexists-fix-flowchart/)があったことに気づきました。

### 疑問2: Route 53のAレコードをいつ置き換えるべきか?

答えは **「`associate-alias`コマンドを実行した後」** です。

`associate-alias`コマンドの[ドキュメント](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/cloudfront/associate-alias.html)によると

> With this operation you can move an alias that’s already in use on a CloudFront distribution to a different distribution in one step. This prevents the downtime that could occur if you first remove the alias from one distribution and then separately add the alias to another distribution.

2つの操作(エイリアスの削除と追加)を1つにするということは分かりました。
しかし、Route 53のAレコードとAAAAレコード(まとめてAレコード)をいつ置き換えたらよいかというのははっきりしませんでした。
もしAレコードを古いCloudFront Distributionを指したままにしておくと、Route 53は`codemonger.io`に対するトラフィックを古いDistributionにルーティングし続けてしまうのではないかと考えました。
これだとAレコードを新しいDistributionを指すように変えるまで結局ダウンしてしまいそうでした。
ということでAレコードのRouting Policyを[Multivalue Answer Routing](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-policy-multivalue.html)に設定してみようとしましたが、Multivalue AnswerのAレコードをCloudFront Distributionを指すようにはできませんでした\*。
結局、Aレコードを更新せずに`associate-alias`を試すことにしました。
なんにせよ私のウェブサイトには大してトラフィックはありません・・・

`associate-alias`を実行した後、`codemonger.io`に対するトラフィックは新しいDistributionにルーティングされ始めました。
どうやら`associate-alias`は古いDistributionに対するトラフィックを新しいDistributionに転送するということもやってくれるようです。

\* 代わりにIPアドレスを指定すべしと怒られました。

### CDKで新しいCloudFront Distributionを確保する

`associate-alias`コマンドを実行するため、新しいCloudFront Distributionには`codemonger.io`の有効なSSL/TLS証明書\*を設定しつつドメイン名は空欄にしておく必要がありました。
残念ながら、[CDKのDistribution](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_cloudfront.Distribution.html)はSSL/TLS証明書を設定しつつドメイン名を空欄にしておくということを許してくれませんでした。
ということで回避策として以下のステップを踏みました。

1. CDKスタックをSSL/TLS証明書とドメイン名なしでCloudFront Distributionを確保するように設定する。
2. CDKスタックをデプロイする。
3. AWS Consoleで`codemonger.io`のSSL/TLS証明書を新しいDistributionに設定する。ただしドメイン名は空欄にしておく。
4. ドメイン名を古いDistributionから新しいDistributionに移動する。
5. CDKスタックをSSL/TLS証明書とドメイン名ありでCloudFront Distributionを確保するように設定する。

スクリプトを編集せずにステップ1と5の間で挙動を切り替えられるようCDKコンテキストを導入しました。

CDKスタックのスクリプトは[GitHubレポジトリ](https://github.com/codemonger-io/codemonger/tree/main/cdk)で入手できます。

\* 私のSSL/TLS証明書は[AWS Certificate Manager](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html)から取得しました。

## 参考

Amazon Route 53, AWS Certificate Manager, Amazon CloudFrontに関する一般的なトピックについては以下のドキュメントをご参照ください。
- [Routing traffic to an Amazon CloudFront distribution by using your domain name](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/routing-to-cloudfront-distribution.html) (自身のドメイン名を用いてAmazon CloudFront Distributionにトラフィックをルーティングする)
- [Requesting a public certificate](https://docs.aws.amazon.com/acm/latest/userguide/gs-acm-request-public.html) (公開証明書を要求する)
- [Requirements for using SSL/TLS certificates with CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cnames-and-https-requirements.html) (CloudFrontで使うSSL/TLS証明書に関する要求事項)