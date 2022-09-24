+++
title = "Mapboxの非表示シンボルを扱う (3. 型の拡張編)"
description = "Series: About development of a library that deals with Mapbox hidden symbols"
date = 2022-09-24
draft = true
[extra]
hashtags = ["Mapbox", "MapboxGLJS", "TypeScript"]
thumbnail_name = "thumbnail.jpg"
+++

[Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/guides/)の画面上で別のシンボルに隠されたシンボルを扱うユーティリティライブラリを開発中です。
これはライブラリの開発過程を紹介するシリーズのブログ投稿第3弾です。

<!-- more -->

## 背景

本シリーズの過去の2回の投稿で以下を示しました。
- [シンボルの衝突ボックスを再計算する方法](../0009-mapbox-collision-boxes/)
- [シンボルのFeatureを再計算した衝突ボックスと関連づける方法](../0010-mapbox-collision-boxes/)

このブログ投稿では、[Mapbox GL JS (`mapbox-gl-js`)](https://docs.mapbox.com/mapbox-gl-js/guides/)のいくつかの型が[TypeScript](https://www.typescriptlang.org)で利用できないという残課題に挑みます。

ライブラリ(`mapbox-collision-boxes`)は[私のGitHubレポジトリ](https://github.com/codemonger-io/mapbox-collision-boxes)で手に入ります。

## TypeScript?

TypeScriptは[JavaScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript)の亜種で、強力な型機能を提供します。
詳しくは[TypeScriptの公式ウェブサイト](https://www.typescriptlang.org)を参照ください。
[このページ](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html)[\[1\]](#参考)はTypeScriptとJavaScriptの違いを理解するのに役立ちます。
`mapbox-collision-boxes`の実装言語にはTypeScriptを選択しました。

## mapbox-gl-jsには型が定義されているのか?

答えは「はい」ですが、`mapbox-gl-js`はJavaScriptに型を導入する別の流儀である[Flow](https://flow.org)で型を定義しています。
残念ながら、Flowの型定義はTypeScriptと互換性がありません。
なので`mapbox-gl-js`の外側にTypeScriptの型定義が必要です。
TypeScriptコミュニティのコントリビュータさんが頑張ってくださっているおかげで、これらの型は[`@types/mapbox-gl`](https://www.npmjs.com/package/@types/mapbox-gl)\*として利用することができます。

\* このブログを書いているときの`@types/mapbox-gl`の最新バージョンは2.7.5で、これは`mapbox-gl-js`バージョン2.7をベースにしています。
当時の`mapbox-gl-js`の最新版は2.10ですが、バージョンの違いによる問題にはとりあえず遭遇していません。

## @types/mapbox-glが欠いているもの

`@types/mapbox-gl`は`mapbox-collision-boxes`が依存しているいくつかのプロパティや型を公開していません。
たとえば、`Map`クラス([@types/mapbox-gl/index.d.ts#L201-L602](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/482d94eee7b27c478034e188bbeb64e2f995bbd8/types/mapbox-gl/index.d.ts#L201-L602))は`style: Style`プロパティを欠いています。
`@types/mapbox-gl`は`Bucket`クラスも`SymbolBucket`も定義していません。

### どう対処するか?

型チェックを諦めるというのに惹かれるかもしれませんが、これは最終手段です。

`mapbox-gl-js`の既存の型定義を拡張するには[モジュール拡張(Module Augmentation)](https://www.typescriptlang.org/docs/handbook/declaration-merging.html#module-augmentation)を使うことができます。
「モジュール拡張」はTypeScriptの少し踏み込んだ機能です。
詳しくは[TypeScriptのドキュメント](https://www.typescriptlang.org/docs/handbook/declaration-merging.html#module-augmentation)の参照ください。

たとえば、以下のスニペットは`Map`クラスに`style: Style`プロパティを追加します。
```ts
import { Map, Style } from 'mapbox-gl';

declare module 'mapbox-gl' {
    interface Map {
        style: Style;
    }
}
```

上記の宣言の後は、`Map#style`に型安全にアクセスできます。

`Bucket`と`SymbolBucket`については、単純に`@types/mapbox-gl`に存在していないのでインターフェイスを追加するだけで良いです。
```ts
export interface Bucket {}

export interface SymbolBucket extends Bucket {
  bucketInstanceId: number;
  // ... 他のプロパティ
}
```

指定した`Bucket`が`SymbolBucket`かどうかをチェックするユーティリティ関数([mapbox-collision-boxes/private/mapbox-types.ts#L232-L234](https://github.com/codemonger-io/mapbox-collision-boxes/blob/b48e39231ef328815ef9ad276fd230de2ccfcaab/src/private/mapbox-types.ts#L232-L234))も導入しました。これはTypeScriptの[「型述語(Type Predicates)」](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#using-type-predicates)という機能を利用しています。
```ts
export function isSymbolBucket(bucket: Bucket): bucket is SymbolBucket {
  return (bucket as SymbolBucket).symbolInstances !== undefined;
}
```

`mapbox-collision-boxes`を実装するのに最低限必要な定義は[私のGitHubレポジトリ](https://github.com/codemonger-io/mapbox-collision-boxes/blob/db7812e7c874df1f59ea6264e027ac0eeeb95875/src/private/mapbox-types.ts)にあります。

## まとめ

今回の短い投稿では、以下のTypeScriptの機能を紹介しつつ`mapbox-gl-js`の既存の型(`@types/mapbox-gl`)をどうやって拡張するかを示しました。
- [モジュール拡張(Module Augmentation)](https://www.typescriptlang.org/docs/handbook/declaration-merging.html#module-augmentation)
- [型述語(Type Predicates)](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#using-type-predicates)

`mapbox-collision-boxes`は[私のGitHubレポジトリ](https://github.com/codemonger-io/mapbox-collision-boxes)で手に入ります。

## 参考

1. [_TypeScript for the New Programmer_ - https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html) (TypeScriptとJavaScriptの違いを理解する)