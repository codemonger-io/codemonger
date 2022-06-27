+++
title = "CloudFrontを介してS3からコンテンツを提供する"
date = 2022-06-20
updated = 2022-06-27
draft = false
[extra]
hashtags = ["AWS", "CloudFront"]
+++

このウェブサイトは[Zola](https://www.getzola.org)で生成し[Amazon CloudFront](https://aws.amazon.com/cloudfront/)を介して[Amazon S3](https://aws.amazon.com/s3/)から配信しています。
このブログ投稿ではこの構成でコンテンツをうまく配信するために何をしたかをお伝えします。

<!-- more -->

## コンテンツ配信のためのプラン

私のウェブサイトは[S3バケット](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-buckets-s3.html)のバケットにデプロイし[CloudFront Distribution](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-working-with.html)を介して配信するつもりでした。
このアイデア自体はいたって普通です。

## Zolaはどのようにコンテンツを配置しているか

Zolaは各セクションとページのコンテンツを`/{parent section path}/{section or page title}/index.html`のようなパスに配置しています(このページならば`/ja/blog/0002-serving-contents-from-s3-via-cloudfront/index.html`)。
コンテンツを参照するときは、サーバ側で末尾に`/index.html`が追加される前提で`/index.html`を省略して`/{parent section path}/{section or page title}`のようにします(このページならば`/ja/blog/0002-serving-contents-from-s3-via-cloudfront`)。
残念ながらこれ(サブディレクトリに`index.html`を追加する)はCloudFront Distributionにとって簡単\*なタスクではありません。
(\*これは実際全然簡単ではありませんでした!)

## CloudFront Functionsの導入

上記の課題に対処するために[CloudFront Functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html)を使うことができます。
[CloudFront Functionをまさにこのような状況に使う例](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example-function-add-index.html)がAWSのガイドにあります。
しかしこの一見簡単そうなタスクは全く簡単でないことが分かりました。
URIの仕様に注意深く対処しなければならず、分かったことは、
- URIはアンカーIDで終わるかもしれない。つまり、ハッシュが続くかもしれない(`#`)。
    - 最後のURIセグメントとハッシュの間に`[/]index.html`挿入しなければならない。
- アンカーIDにはドットを含む記号が入っているかもしれない([過去の投稿「アンカーIDの難点」](/ja/blog/0001-introducing-zola#アンカーIDの難点)参照)。
    - [上述の例](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example-function-add-index.html)のように、単純にURIの中にドットがあるからといってファイル拡張子が指定されたとは判断できない。
- Markdownのセクションタイトルのすべての記号がそのままになるのでアンカーIDはハッシュやスラッシュを含んでしまうかもしれない。
    - URIの最初のハッシュをまず見つけて実際のパスとアンカーIDを分けなければならない。
      私が正しく[URIの文法](https://datatracker.ietf.org/doc/html/rfc3986#section-3.5)を理解しているとすれば、この処理は正当なはず。
- 試した限りでは、Zolaは最初のドットを見つけるとすぐに言語コードの区切りと判断するのでセクションとページのタイトルはドットを含まないはずである。
  ということでアンカーIDを除くURIの最後のパスセグメントがドットを含む場合はセクションやページとは別のリソースなので`/index.html`を提供すべきでない。
- URIはクエスチョンマーク(`?`)から始まるクエリパートを含むかもしれない。
    - 最後のURIセグメントとクエスチョンマークの間に`[/]index.html`を挿入しなければならない。

ということで、私のアルゴリズムは、
1. URIが与えられる &rightarrow; `uri`
2. 最初のオプションのハッシュ(`#`)を`uri`から見つけてフラグメント(`#`から始まる部分文字列もしくは空文字列)を分離する &rightarrow; [`uri`, `fragment`]
3. 最初のオプションのクエスチョンマーク(`?`)を`uri`から見つけてクエリ(`?`から始まる部分文字列もしくは空文字列)を分離する &rightarrow; [`uri`, `query`]
4. 最後のスラッシュ(`/`)を`uri`から見つけて最後のパスセグメント(`/`から始まる部分文字列)を分離する &rightarrow; [`uri`, `last path segment`]
5. `last path segment`がドット(`.`)を含んでいるなら、以下を`last path segment`に追加する。
    - `"index.html"`: `last path segment`が`/`で終わる場合
    - `"/index.html"`: それ以外
6. 新しいURIを返す = `uri` + `last path segment` + `query` + `fragment`

私が実装した`handler`関数は[こちら](https://github.com/codemonger-io/codemonger/blob/c681d9c928a3e02dc2efcaa89f4b4d9f93a6eeaa/cdk/cloudfront-fn/expand-index.js)で閲覧できます。

ところで、[CloudFront FunctionsのJavaScriptエンジンはECMA v5.1をベース](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/functions-javascript-runtime-features.html)にしており「古いなぁ・・・」と感じるかもしれません。

### CloudFront Functionsのユニットテストを行う

CloudFront Functionsのユニットテストもやっかいです。
[こちらの記事](https://www.uglydirtylittlestrawberry.co.uk/posts/unit-testing-cloudfront-functions/)が便利だと思いました。
問題はCloudFront Functionsのランタイムが`module.exports`の記述も`export`修飾子も許さないことです。
なのでCloudFront Functionsのスクリプトから関数をエクスポートする標準的な方法がありませんでした。
[上述の記事](https://www.uglydirtylittlestrawberry.co.uk/posts/unit-testing-cloudfront-functions/)の提案する回避策はインポートしたスクリプトに内部変数や内部関数にアクセスする関数を後付けする[`babel-plugin-rewire`](https://www.npmjs.com/package/babel-plugin-rewire)を使うというものでした。

`babel-plugin-rewire`を試してみると、使われていない内部関数が削除されてしまうという[`babel-plugin-rewire`の課題](https://github.com/speedskater/babel-plugin-rewire/issues/109#issuecomment-202526786)に出くわしました。
ランタイムから呼び出される`handler`関数自体はソースファイル内で呼び出されていないのでこれは問題です。
先述したとおり、`module.exports`の記述も`export`修飾子も使えません。
私の回避策は別の関数`handlerImpl`を追加してシンプルに`handler`からそれを呼び出すというもので、そうすると`handlerImpl`を代わりにテストできます。

```js
function handler(event) {
  return handlerImpl(event);
}
function handlerImpl(event) {
  // actual implementation...
}
```

特定のフォルダ内の`*.js`ファイルを[Babel](https://babeljs.io)と`babel-plugin-rewire`で処理するようにJestを設定しました。
私の`jest.config.js`ファイルは[こちら](https://github.com/codemonger-io/codemonger/blob/c681d9c928a3e02dc2efcaa89f4b4d9f93a6eeaa/cdk/babel.config.js)で閲覧できます。