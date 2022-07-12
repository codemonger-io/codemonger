+++
title = "Omit<Type, Keys>が(期待どおりに)機能しないとき"
description = "このブログ投稿はOmitが機能しない理由を考えることで学んだことを共有します。"
date = 2022-07-12
draft = false
[extra]
hashtags = ["TypeScript"]
thumbnail_name = "thumbnail.png"
+++

[TypeScript](https://www.typescriptlang.org)の[`Omit<Type, Keys>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#omittype-keys)が意図したとおりに機能せず頭を抱えてしまいました。
このブログ投稿は`Omit`が機能しない理由を考えることで学んだことを共有します。

<!-- more -->

## Omit<Type, Keys>とは?

[`Omit<Types, Keys>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#omittype-keys)は[TypeScript](https://www.typescriptlang.org)が提供するユーティリティ型です。
`Type`のすべてのプロパティをすべて持つが`Keys`に指定したプロパティは欠く新しい型を定義します。
`Keys`を`Type`から削除する型演算子と見ることができます。

以下の定義があるとすると、

```ts
interface IdentifiedPerson {
  id: number;
  name: string;
}
type Person = Omit<IdentifiedPerson, 'id'>;
```

導出された`Person`は以下と等価です。

```ts
interface Person {
  name: string;
}
```

## Omit<Type, Keys>が機能しないとき

自分のプロジェクト外に以下のような型が定義されていると想定します。

```ts
interface IElement {
  [extensionName: string]: any;
}

interface InfoObject extends IElement {
  title: string;
  version: string;
  description?: string;
}
```

`InfoObject`の`title`プロパティをオプションにしたいとします。
そこで`InfoObject`から`Omit`を使って新しい型を導出します。

```ts
type InfoObjectOmittingTitle = Omit<InfoObject, 'title'> & {
  title?: string; // オプションになる
};
```

これで`InfoObjectOmittingTitle`のインスタンスを初期化する際に`title`プロパティを省略することができます。

```ts
const info: InfoObject = {
  version: '0.0.1',
}; // エラー! error TS2741: Property 'title' is missing in type '{ version: string; }' but required in type 'InfoObject'.

const info2: InfoObjectOmittingTitle = {
  version: '0.0.1',
}; // OK!
```

しかし**おかしなことが起こります**。
期待に反して`version`プロパティもオプションになっているのです。

```ts
const info3: InfoObjectOmittingTitle = {}; // OKなの!?
```

さらには、以下ですらコンパイルできてしまいます!

```ts
const info4: InfoObjectOmittingTitle = {
  version: 123,
}; // OKなの!?
```

## Omit<Type, Keys>はどのように機能するか

`Omit`自体の定義はTypeScriptソースコードの[こちら](https://github.com/microsoft/TypeScript/blob/28dc248e5c500c7be9a8c3a7341d303e026b023f/src/lib/es5.d.ts#L1574)にあります。
以下はコードの抜粋です。

```ts
type Omit<T, K extends keyof any> = Pick<T, Exclude<keyof T, K>>;
```

`Omit`は実際のところ[`Pick`](https://www.typescriptlang.org/docs/handbook/utility-types.html#picktype-keys)と[`Exclude`](https://www.typescriptlang.org/docs/handbook/utility-types.html#excludeuniontype-excludedmembers)という別のユーティリティ型を組み合わせたものです。

### Pick<Type, Keys>とは?

`Pick`は`Omit`の反対です。
`Type`のプロパティで`Keys`に含まれるものを持つ新しい型を定義します。
`Pick`自体の定義は[こちら](https://github.com/microsoft/TypeScript/blob/28dc248e5c500c7be9a8c3a7341d303e026b023f/src/lib/es5.d.ts#L1550-L1552)にあります。
以下はコードの抜粋です。

```ts
type Pick<T, K extends keyof T> = {
    [P in K]: T[P];
};
```

### Exclude<UnionType, ExcludedMembers>とは?

`Exclude`は`UnionType`のすべてのメンバーを持つが`ExcludedMembers`に含まれるものは除外する新しいユニオン型を定義します。
`Exclude`自体の定義は[こちら](https://github.com/microsoft/TypeScript/blob/28dc248e5c500c7be9a8c3a7341d303e026b023f/src/lib/es5.d.ts#L1564)にあります。
以下はコードの抜粋です。

```ts
type Exclude<T, U> = T extends U ? never : T;
```

### 私の失敗例では何が起きているのか?

[前の節](#Omit<Type,_Keys>が機能しないとき)の以下の部分を詳しく分解していきます。

```ts
Omit<InfoObject, 'title'>
```

これは以下のようになります。

```ts
Pick<InfoObject, Exclude<keyof InfoObject, 'title'>>
```

`keyof InfoObject`は以下のユニオン型と等価です。
`keyof`がどのように機能するかについては[こちらのページ](https://www.typescriptlang.org/docs/handbook/2/keyof-types.html)を参照ください。

```ts
'title' | 'version' | 'description' | string;
```

`string`はベースインターフェイス`IElement`の[Index Signature](https://www.typescriptlang.org/docs/handbook/2/objects.html#index-signatures) `[extensionName: string]: any`からきています。

ということで`Omit`部分はさらに以下のようになります。

```ts
Pick<InfoObject, Exclude<'title' | 'version' | 'description' | string, 'title'>>
```

以下のテーブルは`'title' | 'version' | 'description' | string`の各メンバー`T`について`Exclude<T, 'title'>`を評価した結果を示しています。
`Exclude<'title' | 'version' | 'description' | string, 'title'>`の部分で何が起きているのかを知るには["Distributive Conditional Types"](https://www.typescriptlang.org/docs/handbook/2/conditional-types.html#distributive-conditional-types)を理解しなければなりません。

| `T` | `T extends 'title' ?` | `Exclude<T, 'title'>` |
|-|-|-|
| `'title'` | `true` | `never` |
| `'version'` | `false` | `'version'` |
| `'description'` | `false` | `'description'` |
| `string` | `false` | `string` |

つまり`Exclude<'title' | 'version' | 'description' | string, 'title'>`は以下のようになります。

```ts
'version' | 'description' | string
```

そして`Omit`部分は以下のようになります。

```ts
Pick<InfoObject, 'version' | 'description' | string>
```

最終的な`Pick`では何が起きるでしょうか?
ここは結果から**推測することしか**できません。
`Pick<T, K>`の展開の際に`K extends keyof T`もしくは`P in K`で最も包括的な`string`が優先し、より限定的なメンバーの`'version'`と`'description'`が抑え込まれるのではないかと思われます。

```ts
{
  [p: string]: InfoObject[string];
}
```

結果的に`Pick`は以下のようになります。

```ts
{
  [extensionsName: string]: any;
}
```

しかし、私の推測をバックアップする根拠となる文献はまだ確認できていません。

## 回避策

[こちらの記事](https://javascript.plainenglish.io/how-to-make-certain-properties-optional-in-typescript-9b4f8e85c5de)によると、以下が回避策になりそうです。

```ts
type InfoObjectWithOptionalTitle = Partial<InfoObject> & Pick<InfoObject, 'version'>;
```

[`Partial<Type>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#partialtype)は`Type`のすべてのプロパティをオプションとする新しい型を定義します。
`Pick<InfoObject, 'version'>`とのインターセクションにより`version`プロパティが必須のままになります。

主な難点は必須プロパティを残さず列挙しなければならないことです。

## 結論

[`Omit<Type, Keys>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#omittype-keys)は`Type`が[Index Signature](https://www.typescriptlang.org/docs/handbook/2/objects.html#index-signatures)を含むと機能しないかもしれません。
なぜこれが起きるのかTypeScriptの仕様からは確認できていません。
しかし[回避策](#回避策)は見つかりました。

## 参考

- [_How to Make Certain Properties Optional in TypeScript_](https://javascript.plainenglish.io/how-to-make-certain-properties-optional-in-typescript-9b4f8e85c5de)