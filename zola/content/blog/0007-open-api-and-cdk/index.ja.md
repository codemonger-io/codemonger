+++
title = "AWS APIGateway × OpenAPI (2. Proxy編)"
description = "OpenAPI定義をCDKのREST API定義に統合するライブラリの開発過程を紹介するブログシリーズです。"
date = 2022-07-26
draft = false
[extra]
hashtags = ["AWS", "CDK", "APIGateway", "OpenAPI", "Proxy"]
thumbnail_name = "thumbnail.png"
+++

[OpenAPI](https://www.openapis.org)定義を[CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html)のREST API定義に統合する[ライブラリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)を開発しています。
これはライブラリの開発過程を紹介するシリーズのブログ投稿第2弾です。

<!-- more -->

## 背景

[本シリーズの最初のブログ投稿](../0006-open-api-and-cdk/)で、以下の課題を残しました。

> [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)との互換性はどうやって実現するか?
> - [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)のサブクラスやラッパーを書くとしたら、[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)がサブ要素([Resource](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)や[Method](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Method.html))としてインスタンス化するものを直接操作することはできません。
>   どうやってサブ要素を拡張したら良いでしょうか?
> - [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)を再利用しないとしたら、互換性を実現するのは本当に大変なことになるでしょう。

[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)を再利用しないのは大変すぎるので、サブクラスを書くことにします。

## インターフェイスの定義

[AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html)のAPIを拡張する前に、最低限のインターフェイスを定義しましょう。
以下のセクションに現れるインターフェイスやコードはシンプルにするために私のライブラリから部分的に抽出し改変したものなのでご注意ください。
完全な定義は[GitHubレポジトリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)にあります。

### IRestApiWithSpec

`IRestApiWithSpec`は[`IRestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IRestApi.html)の拡張です。

```ts
interface IRestApiWithSpec extends IRestApi {
  readonly root: IResourceWithSpec;
  // ... 他のプロパティ
}
```

### IResourceWithSpec

`IResourceWithSpec`は[`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html)の拡張\*です。

```ts
interface IResourceWithSpec extends Resource {
  addResource(pathPart: string, options?: ResourceOptionsWithSpec): IResourceWithSpec;
  addMethod(httpMethod: string, target?: Integration, options?: MethodOptionsWithSpec): Method;
  // ... 他のプロパティ
}
```

\* [`IResource.addResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html#addwbrresourcepathpart-options)を正しく拡張するには、`IResourceWithSpec`は[`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html)ではなく[`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)を実装していなくてはなりません。
一方で、`IRestApiWithSpec.root`は[`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)ではなく[`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html)を実装しなければならないので、`IRestApiWithSpec`の`root: IResourceWithSpec`定義は限定的すぎます。
しかし、[`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)の公開インターフェイスと[`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html)は私の知る限り同じなので問題にはならないはずです。

### ResourceOptionsWithSpec

`ResourceOptionsWithSpec`は[`ResourceOptions`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.ResourceOptions.html)の拡張です。

```ts
interface ResourceOptionsWithSpec extends ResourceOptions {
  defaultMethodOptions?: MethodOptionsWithSpec;
}
```

### MethodOptionsWithSpec

`MethodOptionsWithSpec`は[`MethodOptions`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.MethodOptions.html)の拡張です。

```ts
interface MethodOptionsWithSpec extends MethodOptions {
  requestParameterSchemas?: { [key: string]: BaseParameterObject };
  // ... 他のプロパティ
}
```

`BasePrameterObject`は外部ライブラリ[OpenApi3-TS](https://github.com/metadevpro/openapi3-ts)[\[1\]](#Reference)から借りてきました。

当初は[`MethodOptions.requestParameters`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.MethodOptions.html#requestparameters)の定義を以下のようにオーバーライドするつもりだったのですが([前のブログ投稿の例](../0006-open-api-and-cdk/#OpenAPIとREST_APIを一緒に)参照)・・・

```ts
requestParameters?: { [key: string]: boolean | BaseParameterObject };
```

`MethodOptionsWithSpec`を[`MethodOptions`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.MethodOptions.html)に代入できなくしてしまうのでこの試みは失敗しました。
ということで回避策として`requestParameterSchemas`という新しいプロパティを導入しました。

## RestApiを拡張する

[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)を拡張するのは単純です。
言語機能(`extends`)を使い[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)のプロパティをオーバーライドするだけです。

```ts
class RestApiWithSpec extends RestApi implements IRestApiWithSpec {
  readonly root: IResourceWithSpec;

  constructor(scope: Construct, id: string, props: RestApiWithSpecProps) {
    super(scope, id, props);
    // `root`をどう実装しましょうか?
  }
}
```

単純化のため`RestApiWithSpecProps`の詳細は省きます。
ご興味がありましたら[GitHubレポジトリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)をご参照ください。

ここで、疑問はどのように`root`を実装するかです。
親クラス([`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html))の`root`をラップするのが良さそうです。
ではどうやってラップしましょうか?
ほとんどのリクエストを[`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)の`root`に転送するだけのラッパークラスを書きましょうか?
大量のBoilerplate(定型的なコード)が発生しそうです。
それなら[`Proxy`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy)がニーズにもっとマッチしそうです。

### rootにProxyをかませる

`root`用の`Proxy`を書くのはとても簡単です。
ハンドラオブジェクトの[`get`](https://devdocs.io/javascript/global_objects/proxy/proxy/get)関数を実装するだけです。

```ts
// root: IResource
const rootWithSpec: IResourceWithSpec = new Proxy(root, {
  get: (target, prop, receiver) => {
    switch (prop) {
      case 'addResource':
        return (pathPart, options) => {
          // ... 新しいリソースを作成して再びラップする
        };
      case 'addMethod':
        return (httpMethod, target, options) => {
          // ... optionsを処理する
        };
      default:
        return Reflect.get(target, prop, receiver);
          // `Reflect.get(...arguments)`とするとTypeScriptが文句を言いました
    }
  }
});
```

残念ながら、[TypeScript](https://www.typescriptlang.org)は上記コードでProxyをかませたオブジェクトを`IResourceWithSpec`だと認識せずエラーになります。
[`Proxy`コンストラクタのデフォルトのTypeScript定義](https://microsoft.github.io/PowerBI-JavaScript/interfaces/_node_modules_typedoc_node_modules_typescript_lib_lib_es2015_proxy_d_.proxyconstructor.html#constructor)が以下のようになっているからです。

```ts
declare global {
  interface ProxyConstructor {
    new <T extends object>(target: T, handler: ProxyHandler<T>): T; // TのProxyはやっぱりT
  }
}
```

この問題に対処するため、`Proxy`コンストラクタが`target`とは違う型を生成することができるように定義を拡張できます。
[StackOverflowのこちらの投稿](https://stackoverflow.com/a/50603826)[\[2\]](#Reference)がまさに答えです。
ということで以下の宣言を追加するとTypeScriptエラーが解決します。

```ts
declare global {
  interface ProxyConstructor {
    new <T extends object, U extends object>(target: T, handler: ProxyHandler<T>): U; // TのProxyはUでもよい
  }
}
```

## Resourceを拡張する

[`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)を生成するたびに、節[「rootにProxyをかませる」](#rootにProxyをかませる)で記述したように`Proxy`でラップする必要があります。
ということで既存のどんな[`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html)でも`IResourceWithSpec`の機能でラップできるファクトリーメソッド`augmentResource`を導入しました。
このファクトリーメソッドは`root`にも適用可能です。

```ts
class ResourceWithSpec {
  static augmentResource(restApi: IRestApiWithSpec, resource: IResource, parent?: IResourceWithSpec): IResourceWithSpec {
    const resourceWithSpec: IResourceWithSpec = new Proxy(resource, {
      get: (target, prop, receiver) => {
        switch (prop) {
          case 'addResource':
            return (pathPart, options) => {
              return augmentResource(
                restApi,
                resource.addResource(pathPart, options),
                resourceWithSpec
              );
            };
          // ... 他のプロパティを処理
        }
      }
    });
    return resourceWithSpec;
  }
}
```

上記のコードはシンプルにしてあり、実際の定義は[GitHubレポジトリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)にあります。

## まとめ

このブログ投稿では、CDK APIの拡張を簡単にするために`Proxy`を導入しました。
`Proxy`に関するTypeScriptのエラーを回避するトリックも紹介しました。
次のブログ投稿では、いつOpenAPI定義ファイルを出力するかという課題に挑む予定です。

## Reference

1. [OpenApi3-TS](https://github.com/metadevpro/openapi3-ts)

   OpenAPI 3の仕様そのものに対するTypeScriptバインディング。
2. [How to use Proxy<T> with a different type than T as argument? - Answer](https://stackoverflow.com/questions/50602903/how-to-use-proxyt-with-a-different-type-than-t-as-argument/50603826#50603826)