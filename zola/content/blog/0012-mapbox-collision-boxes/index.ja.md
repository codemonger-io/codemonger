+++
title = "RustのカスタムLambdaランタイムでバイナリレスポンスを扱う"
date = 2022-10-14
draft = false
hashtags = ["AWS", "Lambda", "Rust"]
+++

このブログ投稿ではRustで書かれたAWS Lambdaカスタムランタイムでバイナリレスポンスを扱う方法を紹介します。

<!-- more -->

## 背景

[Lambdaインテグレーション](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-integrations.html)を使えば[Amazon API Gateway REST API (REST API)](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html)から動的なレスポンスを返すことができます。
私はREST API用に動的なバイナリデータを生成する[AWS Lambda (Lambda)](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)関数を実装することにしました。
[Rust](https://www.rust-lang.org)を学習中なので、Lambda関数をRustで実装することにしました\*。
このブログは[Non-Proxyインテグレーション](https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started-lambda-non-proxy-integration.html)用のLambda関数を扱いますのでご留意ください。

\* 私は[Python](https://www.python.org)と[Node.js (JavaScript)](https://nodejs.org/en/)はバイナリデータを処理するのはあまり得意でないだろうと考えています。
[Go](https://go.dev)はバイナリデータ処理によい選択かもしれず、AWSも[公式なGoのLambdaランタイム](https://docs.aws.amazon.com/lambda/latest/dg/lambda-golang.html)を提供していますが、とにかくRustを学びたいわけです。

## Rust用のLambdaランタイム

[AWSはRustに熱心な様子](https://aws.amazon.com/blogs/opensource/why-aws-loves-rust-and-how-wed-like-to-help/)ですが、[公式なRust用のLambdaランタイムは提供していません](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)。
ということで[カスタムLambdaランタイム](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html)をRustで実装するか、[コンテナ](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-package.html#gettingstarted-package-images)を作成するかしなければなりません。
Lambda関数をRustでどうやって実装するかを探していると、おそらく[`aws-lambda-rust-runtime`](https://github.com/awslabs/aws-lambda-rust-runtime)というライブラリに出くわします。
このライブラリはRust用のカスタムLambdaランタイムを実装する際に面倒なことを代わりに全部やってくれます。

`aws-lambda-rust-runtime`のおかげで、Lambda関数をRustで実装するのはかなり簡単です。
[`aws-lambda-rust-runtime`のGitHubレポジトリに簡単なチュートリアル](https://github.com/awslabs/aws-lambda-rust-runtime#getting-started)があります。
チュートリアルをここでは繰り返しませんが、抜粋(実際に記述するRustコード)を以下に示します。
```rust
use lambda_runtime::{service_fn, LambdaEvent, Error};
use serde_json::{json, Value};

#[tokio::main]
async fn main() -> Result<(), Error> {
    let func = service_fn(func);
    lambda_runtime::run(func).await?;
    Ok(())
}

async fn func(event: LambdaEvent<Value>) -> Result<Value, Error> {
    let (event, _context) = event.into_parts();
    let first_name = event["firstName"].as_str().unwrap_or("world");

    Ok(json!({ "message": format!("Hello, {}!", first_name) }))
}
```

### aws-lambda-rust-runtimeでバイナリデータを扱う

`aws-lambda-rust-runtime`は出力が[JSON](https://www.json.org/json-en.html)にエンコード可能な限りうまく機能します。

#### Vec\<u8\>を返すのはうまくいかない

コアモジュール[`lambda_runtime`](https://docs.rs/lambda_runtime/0.6.1/lambda_runtime/index.html)の[`run`](https://docs.rs/lambda_runtime/0.6.1/lambda_runtime/fn.run.html)関数は[`serde::Serialize`](https://docs.rs/serde/1.0.145/serde/trait.Serialize.html)を実装する値を返すサービスならなんでも受け付けます。
バイナリを出力するのに、まず私はサービス関数に`Vec<u8>`を返させれば良いと考えてやってみました。
すると、`lambda_runtime`は[BLOB](https://en.wikipedia.org/wiki/Binary_large_object)の代わりに配列のJSON形式を生成しました。
例えば、`[0x61, 0x62, 0x63]`を`Vec<u8>`として`lambda_runtime`に与えると、以下のような出力を、
```json
[
  97,
  98,
  99
]
```
`abc`\*の代わりに得ました。

\* `0x61`, `0x62`, `0x63`は[ASCII](https://en.wikipedia.org/wiki/ASCII)でそれぞれ`'a'`, `'b'`, `'c'`を表します。

#### lambda_runtimeはどのように結果を扱っているのか?

[`lambda_runtime::run`](https://github.com/awslabs/aws-lambda-rust-runtime/tree/main/lambda-runtime)はあらゆるサービス関数の出力をJSONに変換しますが、この動作は[lambda-runtime/src/requests.rs#L77-L85](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/requests.rs#L77-L85)にハードコードされています(`serde_json::to_vec(&self.body)`に注目)。
```rust
    fn into_req(self) -> Result<Request<Body>, Error> {
        let uri = format!("/2018-06-01/runtime/invocation/{}/response", self.request_id);
        let uri = Uri::from_str(&uri)?;
        let body = serde_json::to_vec(&self.body)?;
        let body = Body::from(body);

        let req = build_request().method(Method::POST).uri(uri).body(body)?;
        Ok(req)
    }
```

#### 解決策?

[バイナリレスポンスに関する議論](https://github.com/awslabs/aws-lambda-rust-runtime/issues/69)がGitHubに見つかりましたが、それは[`lambda_http`](https://docs.rs/lambda_http/0.6.1/lambda_http/)モジュールを使うことを提案しています。
私が調べた限り、`lambda_http`は[LambdaのProxyインテグレーション](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html)用に設計されています。
なので単純にBLOBを生成することはできません。

そこで以下の2つの回避策を思いつきました。
1. [Base64](https://en.wikipedia.org/wiki/Base64)エンコードされたバイナリをJSONオブジェクトのフィールド値として埋め込み、[インテグレーションレスポンスのマッピングテンプレート](https://docs.aws.amazon.com/apigateway/latest/developerguide/models-mappings.html#models-mappings-mappings)でそれを取り出し、[`CONVERT_TO_BINARY`](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-payload-encodings-workflow.html)を適用
2. `lambda_runtime`をバイナリ出力を扱えるように改造

簡単な方法は最初のものだったはずですが、
**Rustを練習するよい機会**だったので2番目の方法\*を採りました。

\* 後に、私の努力は必要なかったことが判明します。
もっと単純で簡単な方法を知りたい方は[節「もっと単純な解決策」](#もっと単純な解決策)まで読み飛ばしてもらって結構です。

### lambda_runtimeの改造

改造の主な目的はバイナリレスポンスをサポートすることですが、2番目の目的も設定しました。JSONシリアライズ可能なオブジェクトを返す既存のプログラムも確実に動作し続けるということ(後方互換性)です。

この節では以下を紹介します。
1. [関数のレスポンスの出口となる`IntoRequest` Trait](#IntoRequest_Trait)
2. [私の回避策: `IntoBytes`と`RawBytes`の導入](#IntoBytesとRawBytesの導入)

#### IntoRequest Trait

`IntoRequest`([lambda-runtime/src/requests.rs#L8-L10](https://github.com/awslabs/aws-lambda-rust-runtime/blob/b1c5dfd1a09c62f77e91c03f278f73b7e2ecfd30/lambda-runtime/src/requests.rs#L8-L10))はサービス関数のすべての成功出力をシリアライズし、[Lambda関数の呼び出しレスポンス用エンドポイント](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-api.html#runtimes-api-response)\*に送るリクエストオブジェクトを作成します。
```rust
pub(crate) trait IntoRequest {
    fn into_req(self) -> Result<Request<Body>, Error>;
}
```

`IntoRequest`は`lambda_runtime`において重要な役割を果たしていますが、関数の出力用に皆さんが直接実装\*2 することはありません。
関数の結果と`IntoRequest`の間には「ブリッジ」があります。`EventCompletionRequest<T>` (`T`は関数が出力する型)です([lambda-runtime/src/requests.rs#L68-L71](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/requests.rs#L68-L71))。
```rust
pub(crate) struct EventCompletionRequest<'a, T> {
    pub(crate) request_id: &'a str,
    pub(crate) body: T,
}
```

`lambda_runtime`は関数の出力を`EventCompletionRequest<T>`でラップし`IntoRequest`として処理します([lambda-runtime/src/lib.rs#L164-L168](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/lib.rs#L164-L168))。
```rust
                                EventCompletionRequest {
                                    request_id,
                                    body: response,
                                }
                                .into_req()
```

`IntoRequest`は`T`が`serde::Serialize`であるような`EventCompletionRequest<T>`に対して実装されています([lambda-runtime/src/requests.rs#L73-L75](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/requests.rs#L73-L75))。
```rust
impl<'a, T> IntoRequest for EventCompletionRequest<'a, T>
where
    T: for<'serialize> Serialize,
```

これがサービス関数が出力する`Serialize`がJSONオブジェクトに変換される理由です。

\* `IntoRequest`が関数のレスポンスを表しているのに名前に"Request"という単語が含まれていて混乱するかもしれませんが、ここでの"Request"はカスタムLambdaランタイムの呼び出しレスポンス用エンドポイントに送るリクエストという意味です。

\*2 そもそも`IntoRequest`はエクスポートされていません。

#### IntoBytesとRawBytesの導入

[`IntoRequest::into_req`の中の`serde_json::to_vec`呼び出し](#lambda_runtimeはどのように結果を扱っているのか?)をどうにかして一般化しなければなりません。
これはサービス出力からバイト列(`Vec<u8>`)への変換と捉えることができます。
ならば`IntoRequest`を`EventCompletionRequest<'a, Vec<u8>>`用に特殊化してはどうでしょうか?
残念ながら、`lambda_runtime::run`を`Serialize`と`Vec<u8>`の両方をサービス出力として受け付けるようにすることはできないのでうまくいきません。
```rust
pub async fn run<A, B, F>(handler: F) -> Result<(), Error>
where
    F: Service<LambdaEvent<A>>,
    F::Future: Future<Output = Result<B, F::Error>>,
    F::Error: fmt::Debug + fmt::Display,
    A: for<'de> Deserialize<'de>,
    B: Serialize | Vec<u8>, // エラー: こういうことはできない!
```

`Serialize`にも生のバイト列にも解釈できるような新しい型が必要です。
では、新しい`IntoBytes` Traitを導入し以下のとおり`IntoRequest`を`EventCompletionRequest<'a, Serialize>`ではなく`EventCompletionRequest<'a, IntoBytes>`用に特殊化してはどうでしょうか?
```rust
pub trait IntoBytes {
    fn to_bytes(self) -> Result<Vec<u8>, Error>;
}

impl<'a, T> IntoRequest for EventCompletionRequest<'a, T>
where
    T: IntoBytes,
{
    fn into_req(self) -> Result<Request<Body>, Error> {
        let uri = format!("/2018-06-01/runtime/invocation/{}/response", self.request_id);
        let uri = Uri::from_str(&uri)?;
        let body = self.body.to_bytes()?;
        let body = Body::from(body);

        let req = build_request().method(Method::POST).uri(uri).body(body)?;
        Ok(req)
    }
}
```

すると、`lambda_runtime::run`のシグネチャも書き換えなければなりません。
以下はどうでしょうか?
```rust
pub async fn run<A, B, F>(handler: F) -> Result<(), Error>
where
    F: Service<LambdaEvent<A>>,
    F::Future: Future<Output = Result<B, F::Error>>,
    F::Error: fmt::Debug + fmt::Display,
    A: for<'de> Deserialize<'de>,
    B: IntoBytes, // Serializeを受け付けない
```

上記のようにすると、後方互換性が失われます(サービス関数は単純に`Serialize`を返すことができなくなります)。
この問題を回避するため、`IntoBytesBridge`という別のStructを導入しました。
```rust
pub struct IntoBytesBridge<T>(pub T);
```

`IntoBytes`は以下のように`IntoBytesBridge<Serialize>`に対して特殊化します。
```rust
impl<T> IntoBytes for IntoBytesBridge<T>
where
    T: Serialize,
{
    fn to_bytes(self) -> Result<Vec<u8>, Error> {
        let bytes = serde_json::to_vec(&self.0)?;
        Ok(bytes)
    }
}
```

`IntoBytesBridge`のおかげで、`lambda_runtime::run`のシグネチャは次のように書き換えることができます。
```rust
pub async fn run<A, B, F>(handler: F) -> Result<(), Error>
where
    F: Service<LambdaEvent<A>>,
    F::Future: Future<Output = Result<B, F::Error>>,
    F::Error: fmt::Debug + fmt::Display,
    A: for<'de> Deserialize<'de>,
    IntoBytesBridge<B>: IntoBytes, // IntoBytesをIntoBytesBridge<B>に対して実装していることを要求する
```

これは`Serialize`に対しても機能します。`IntoByte`が`IntoBytesBridge<Serialize>`に対して実装されているからです(上述のコード参照)。

今度は、生のバイト列を出力するという意図を伝えるために新しいデータ型`RawBytes`を導入し、`IntoBytes`を`IntoBytesBridge<RawBytes>`に対して特殊化します。
```rust
pub struct RawBytes(pub Vec<u8>);

impl IntoBytes for IntoBytesBridge<RawBytes> {
    fn to_bytes(self) -> Result<Vec<u8>, Error> {
        Ok(self.0.0)
    }
}
```

こうしてサービス関数の出力を`RawBytes`でラップすれば生のバイト列を出力することができます。
以下の例はJSONの配列`[97, 98, 99]`ではなく生の文字列`abc`を出力します。
```rust
use lambda_runtime::{service_fn, LambdaEvent, Error, RawBytes};
use serde_json::Value;

#[tokio::main]
async fn main() -> Result<(), Error> {
    let func = service_fn(func);
    lambda_runtime::run(func).await?;
    Ok(())
}

async fn func(event: LambdaEvent<Value>) -> Result<RawBytes, Error> {
    Ok(RawBytes(vec![0x61, 0x62, 0x63]))
}
```

### Lambdaインテグレーションの制限?

[前節で開発した新機能](#IntoBytesとRawBytesの導入)を自分のREST APIを実装するのに試してみましたが、おかしなことが起こりました。
APIがサービスレスポンスとして返したバイト列とは少し違うバイト列を出力してしまうのです。
APIがときどき特定の3バイト`(0xE, 0xBF, 0xBD)`を生成していることに気づきました。
問題をしっかり観察すると、その3バイトは最上位ビットが1の(言い換えると、`0x80`とのビットANDが`0`でない)バイトを置き換えていることが分かりました。
`(0xEF, 0xBF, 0xBD)`という3バイトは実際のところ[置換文字(`U+FFFD`)](https://www.compart.com/en/unicode/U+FFFD)のUTF-8表現であり、それはつまり、**有効なUTF-8列を期待している誰かが私のAPI出力の不明なバイトを置き換えた**ということです。
では誰に責任があるのでしょうか?
Lambdaの呼び出しレスポンス用のエンドポイント?
それともAmazon API Gatewayの[Lambdaインテグレーション](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-integrations.html)?
それともまさかRustの依存関係?

AWSのCLIコマンド[`aws lambda invoke`](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/lambda/invoke.html)でLambda関数を直接呼び出したときには、私が期待するバイト列が得られました。
ということはLambdaの呼び出しレスポンスのエンドポイントとRustの依存関係は無実で、**Lambdaインテグレーションが原因**ということです。
LambdaのProxyインテグレーションが出力にJSON(有効なUTF-8列の部分集合)を期待しているのは知っていましたが、
**LambdaのNon-Proxyインテグレーションも出力にUTF-8列を期待している**\*とは知りませんでした。

\* 公式な情報源ではまだ確認できていません。

#### 回避策

私の回避策はサービス出力をBase64にエンコードし`contentHandling`に`CONVERT_TO_BINARY`を指定するというものです。
しかしひとつ疑問が湧きます。バイナリをBase64テキストにエンコードしなければならないのなら、`lambda_runtime`の拡張は本当に必要だったのでしょうか?
この疑問は[次節](#もっと単純な解決策)で解説するもっと単純な解決策につながります。

### もっと単純な解決策

[前節](#Lambdaインテグレーションの制限?)では、サービスが任意のバイト列を出力することをLambdaのNon-Proxyインテグレーションが許さないことを学びました。
なので、結局サービス出力はBase64エンコードしなければならないわけです。
ということは`lambda_runtime`を改造したことのメリットはほとんど失われたことになります。
[節「解決策?」](#解決策?)では、`lambda_runtime`に対する改造を必要としない別の方法を提案しました。

> 1. [Base64](https://en.wikipedia.org/wiki/Base64)エンコードされたバイナリをJSONオブジェクトのフィールド値として埋め込み、[インテグレーションレスポンスのマッピングテンプレート](https://docs.aws.amazon.com/apigateway/latest/developerguide/models-mappings.html#models-mappings-mappings)でそれを取り出し、[`CONVERT_TO_BINARY`](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-payload-encodings-workflow.html)を適用

しかし、フィールドの値を取り出すためだけにマッピングテンプレートを書くのも少し面倒だと思います。
では、**Base64エンコードした[`String`](https://doc.rust-lang.org/std/string/struct.String.html)を直接出力し、それをJSONにシリアライズ**するというのはどうでしょうか?
`Serialize`は`String`に対して実装されているので、サービス関数はなんの改造もなく`String`を出力できます。
```rust
use lambda_runtime::{service_fn, LambdaEvent, Error};
use serde_json::Value;

#[tokio::main]
async fn main() -> Result<(), Error> {
    let func = service_fn(func);
    lambda_runtime::run(func).await?;
    Ok(())
}

async fn func(event: LambdaEvent<Value>) -> Result<String, Error> {
    Ok(base64::encode([0x61, 0x62, 0x63]))
}
```

私は最初これはダメだろうなと思っていました。なぜなら出力が余計なダブルクオーテーション(`"`)で囲まれてしまい無効なBase64テキストになってしまうからです。

ところが、**うまくいったのです**!

出力を`aws lambda invoke`で取り出すと、実際にダブルクオーテーションで取り囲まれていました。
しかしLambdaインテグレーションはどうしてかその扱い方を認識しており、所望のBase64テキストを正しくデコードしてくれたのです。

## まとめ

このブログでは、[`aws-lambda-rust-runtime`](https://github.com/awslabs/aws-lambda-rust-runtime)がRust用のカスタムLambdaランタイムを実装するのにとても役立つことを確認しました。
それから`aws-lambda-rust-runtime`がバイナリデータを扱えるようにするための改造を紹介しました。
しかし、Base64エンコードした`String`を単純に返すのが、Amazon API GatewayのLambdaインテグレーションでバイナリ出力を扱うのに最も簡単な方法だということが分かりました。

あまり役に立たなくなってしまいましたが、私が`aws-lambda-rust-runtime`に行った改造は[GitHubのフォーク](https://github.com/codemonger-io/aws-lambda-rust-runtime/tree/binary-support)で確認できます。

## 補足

### CDKでRustのLambdaランタイムをビルドする

[AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html)でRustのLambda関数をビルドするのに[`rust.aws-cdk-lambda`](https://github.com/rnag/rust.aws-cdk-lambda/tree/main)というモジュールがとても役に立ちました。