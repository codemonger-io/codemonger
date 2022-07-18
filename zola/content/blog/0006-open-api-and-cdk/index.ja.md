+++
title = "AWS APIGateway × OpenAPI (1. 動機編)"
description = "OpenAPI定義をCDKのREST API定義に統合するライブラリの開発過程を紹介するブログシリーズです。"
date = 2022-07-18
draft = true
[extra]
hashtags = ["AWS", "CDK", "APIGateway", "OpenAPI"]
thumbnail_name = "thumbnail.png"
+++

[OpenAPI](https://www.openapis.org)定義を[CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html)のREST API定義に統合する[ライブラリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)を開発しています。
これはライブラリの開発過程を紹介するシリーズの最初のブログ投稿です。

<!-- more -->

## 動機

最近、[Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html)で記述した[Amazon API Gateway (API Gateway)](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html)上のREST APIについてOpenAPI定義を書くべきだろうなと強く感じています。
私の知る限り、API GatewayのREST APIでOpenAPI定義を扱うオプションは2つあります。
1. [既存のREST APIからOpenAPI定義をエクスポートする](#1._既存のREST_APIからOpenAPI定義をエクスポートする)
2. [既存のOpenAPI定義をインポートしてREST APIを作成する](#2._既存のOpenAPI定義をインポートしてREST_APIを作成する)

### 1. 既存のREST APIからOpenAPI定義をエクスポートする

API Gatewayでは[既存のREST APIからOpenAPI定義をエクスポート](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-export-api.html)することができます。
意味のあるOpenAPI定義をエクスポートするには[REST APIに別途ドキュメントを追加](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-documenting-api.html)しなければなりません。
CDKには[L1 Constructの`CfnDocumentationPart`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.CfnDocumentationPart.html)があり、それでAPI要素のドキュメントを書くことができます([「OpenAPIとREST APIを一緒に」](#OpenAPIとREST_APIを一緒に)の例を参照ください)。
しかし、ドキュメントと実際のAPI要素定義が分離しているのはドキュメントを最新に保つのに不都合かもしれません。
REST API要素とそのドキュメントを一緒に書くことができたら素晴らしいのではないかと考えています。

### 2. 既存のOpenAPI定義をインポートしてREST APIを作成する

AWS特有の拡張を含むOpenAPI定義が既に手元にあるなら、[それをAPI GatewayでインポートしてREST APIを構築](https://docs.aws.amazon.com/apigateway/latest/developerguide/import-edge-optimized-api.html)することができます。
CDKには既存のOpenAPI定義をインポートするための[専用のConstruct `SpecRestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.SpecRestApi.html)もあります。
しかし一からREST APIを構築するなら、私は以下の理由からCDKのパーツ([`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)とサブ要素)を選びます。
- 単純に慣れている。
- CDKのパーツは面倒な[IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html)設定と脆弱性を減らすことができる。
- OpenAPI定義にAWS特有の拡張を書くのは面倒かもしれない。\*
- 素のOpenAPI定義には多くの繰り返しが必要かもしれない。\*

\* このオプションは試していないので私が間違っているかもしれません。

### 3番目のオプション

ということで、CDKのパーツを使って**REST APIとOpenAPI定義を一緒に書く**ことができるような3番目のオプションがあるといいなと考えています。

## デザインゴール

[こちらのブログ投稿](https://dev.to/aws-builders/openapi-specs-from-cdk-stack-without-deploying-first-4g83?utm_source=dormosheio&utm_campaign=dormosheio)[\[1\]](#参照)は類似の成果を紹介しており刺激になりました。
しかし私の目的は[TypeScript](https://www.typescriptlang.org)の力を使いこなすことではありません。
目的は2つです。

1. [OpenAPIとREST APIを一緒に](#OpenAPIとREST_APIを一緒に)
2. [RestApiとの互換性](#RestApiとの互換性)

### OpenAPIとREST APIを一緒に

本ライブラリを使用すると、OpenAPI定義を別のドキュメントリソースではなくREST API要素のすぐそばに記述することができます。

例えば、以下のようにすることができます。

```ts
const pet = api.root.addResource('pet');
const findByStatus = pet.addResource('findByStatus');
findByStatus.addMethod(
  'GET',
  new MockIntegration({
    // ... integration settings
  }),
  {
    operationName: 'findPetsByStatus',
    summary: 'Finds Pets by status',
    description: 'Multiple status values can be provided with comma separated strings',
    requestParameters: {
      'method.request.querystring.status': {
        description: 'Status values that need to be considered to filter',
        required: false,
        explode: true,
        schema: {
          type: 'string',
          enum: ['available', 'pending', 'sold'],
          default: 'available'
        }
      }
    },
    methodResponses: [
      {
        statusCode: '200',
        description: 'successful operation',
        responseModel: {
          'application/json': petArrayModel
        }
      }
    ]
  }
);
```

本ライブラリを使わない場合は以下のようになります。

```ts
const pet = api.root.addResource('pet');
const findByStatus = pet.addResource('findByStatus');
findByStatus.addMethod(
  'GET',
  new MockIntegration({
    // ... integration settings
  }),
  {
    operationName: 'findPetsByStatus',
    requestParameters: {
      'method.request.querystring.status': true
    },
    methodResponses: [
      {
        statusCode: '200',
        responseModel: {
          'application/json': petArrayModel
        }
      }
    ]
  }
);
new CfnDocumentationPart(this, 'FindPetsByStatusDocPart', {
  location: {
    type: 'METHOD',
    path: '/pet/findByStatus',
    method: 'GET'
  },
  properties: {
    summary: 'Finds Pets by status',
    description: 'Multiple status values can be provided with comma separated strings'
  },
  restApiId: api.restApiId
});
new CfnDocumentationPart(this, 'FindPetsByStatusParamsDocPart', {
  location: {
    type: 'QUERY_PARAMETER',
    path: '/pet/findByStatus',
    method: 'GET',
    name: 'status'
  },
  properties: {
    description: 'Status values that need to be considered to filter',
    required: false,
    explode: true,
    schema: {
        type: 'string',
        enum: ['available', 'pending', 'sold'],
        default: 'available'
    }
  },
  restApiId: api.restApiId
});
new CfnDocumentationPart(this, 'FindPetsByStatus200ResponseDocPart', {
  location: {
    type: 'RESPONSE',
    path: '/pet/findByStatus',
    method: 'GET',
    statusCode: '200'
  },
  properties: {
    description: 'successful operation'
  }
});
```

### RestApiとの互換性

本ライブラリを使うと、[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)を使うのと同じ使用感を得られます。

拡張されたConstruct `RestApiWithSpec`を[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)の代わりにインスタンス化するだけです。

```ts
const api = new RestApiWithSpec(this, 'example-api', {
  description: 'Example of RestApiWithSpec',
  openApiInfo: {
    version: '1.0.0'
  },
  openApiOutputPath: 'openapi.json',
  deploy: true,
  deployOptions: {
    stageName: 'staging',
    description: 'Default stage'
  }
});
```

`RestApiWithSpec`のインスタンスを得たあとは、[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)と全く同様に使用することができます。
もちろんOpenAPI定義を記述するための拡張機能も提供されます([「OpenAPIとREST APIを一緒に」](#OpenAPIとREST_APIを一緒に)の例を参照ください)。

## 課題

いくつか課題があります。
- [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)との互換性はどうやって実現するか?
    - [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)のサブクラスやラッパーを書くとしたら、[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)がサブ要素([Resource](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)や[Method](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Method.html))としてインスタンス化するものを直接操作することはできません。
      どうやってサブ要素を拡張したら良いでしょうか?
    - [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)を再利用しないとしたら、互換性を実現するのは本当に大変なことになるでしょう。
- いつ実際にOpenAPI定義ファイルを出力すべきか?
    - 保存のための関数をユーザーが明示的に呼び出さなければならないのでしょうか?
    - それともCDKが[CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html)テンプレートに対してやるようにOpenAPIの定義ファイルもいつのまにやら保存されようにできるでしょうか?
- [Lambdaプロキシ](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html)をサポートできるか?

今後のブログ投稿でこれらの課題に挑んでいきます。

## まとめ

私が開発中のものは[GitHubレポジトリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)で手に入ります。
次のブログ投稿では[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)との互換性をどう実現するかに挑むつもりです。

## 参照

1. [_OpenAPI Specs from CDK Stack WITHOUT Deploying First_](https://dev.to/aws-builders/openapi-specs-from-cdk-stack-without-deploying-first-4g83?utm_source=dormosheio&utm_campaign=dormosheio)