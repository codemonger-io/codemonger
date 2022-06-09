+++
title = "Zolaを導入する"
date = 2022-06-09
draft = false
+++

このサイトは[Zola](https://www.getzola.org)を用いて生成されています。
このブログ記事ではZolaを使う上で私が気づいたことを紹介します。

<!-- more -->

## Zolaとは？

[Zola](https://www.getzola.org)は[Hugo](https://gohugo.io)のような静的なサイトジェネレータです。
[Rust](https://www.rust-lang.org)で書かれています。
詳しくは[公式ドキュメント](https://www.getzola.org/documentation/getting-started/overview/)を参照してください。
ちなみに私はZolaの作者でもコントリビュータでもありません。

## なぜ私のウェブサイトにZolaを選んだのか？

Zolaの実装言語がRustだということで惹かれました(Rustは2022年6月9日現在で私が勉強中の言語です)。
Zolaを使うだけなら実装言語は関係ないんですが・・・

## ZolaでBulmaを使う

[Bulma](https://bulma.io)は私の好きなCSSフレームワークでこのウェブサイトに使いたいと思いました。
Bulmaがうまく機能するには少し細工が必要でした。

### Bulmaをインポートする

Bulmaの`sass`フォルダと`bulma.sass`ファイルをZolaの`sass`フォルダに単純に投げ込むだけでは機能しませんでした。Bulmaはサブフォルダのsassファイルをすべて露出するようにしていたからです。
[同じ課題に関する議論](https://github.com/getzola/zola/issues/431)を見つけ、投稿者が提案する解決策に従うことにしました。
ということで、Bulmaの全てのsassファイルの頭にアンダースコア(`_`)を追加して解決しました。

### MarkdownにBulmaのスタイリングを適用する

Zolaが生成したMarkdownコンテンツにBulmaのスタイルを適用するために、[`.content`クラス](https://bulma.io/documentation/elements/content/)を持つエレメントでラップしました。
[同じ課題に関するフォーラムの投稿](https://zola.discourse.group/t/how-to-style-html-generated-from-markdown/868)を見つけました。

## 多言語対応

このウェブサイトの記事は英語と日本語の両方で提供したいので、多言語対応は私にとって重要です。
Zolaは[多言語サイト(Multilingual sites)](https://www.getzola.org/documentation/content/multilingual/)に対応していますが、その機能に関するドキュメントはあまり整備されていません。

### セクションの_index.{code}.mdファイル

セクションは`_index.md`ファイルを伴います。
セクションをデフォルトの言語以外で書きたい場合、`_index.{code}.md`ファイルも作成しなければなりません(`{code}`は使いたい言語のコードに置き換えます)。
私の場合、各セクションにつき以下の2つのファイルを用意しました。
- `_index.md` &rightarrow; 英語 (デフォルト)
- `_index.ja.md` &rightarrow; 日本語

### 言語を意識してセクションを取得する

[`get_section`](https://www.getzola.org/documentation/templates/overview/#get-section)関数を使えば特定のパスのセクションオブジェクトを取得できます。
`get_section`は言語オプションを受け取らないので、`lang`変数で与えられる現在の言語に対応するセクションオブジェクトを要求するのは少しやっかいです。
`"_index." ~ lang ~ ".md"`のように単純に`lang`を連結してもうまくいきませんでした。デフォルト言語については`_index.md`が期待されるところ`_index.en.md`のように間違ったパスを作ってしまうからです。

ということで現在の言語に対応した拡張子に置き換わる`lang_ext`というマクロを作成しました。
このマクロは`".{code}"`に置き換わりますが、デフォルト言語については空文字列になります。

```
{% macro lang_ext() %}{% if lang != config.default_language %}.{{ lang }}{% else %}{% endif %}{% endmacro lang_ext %}
```

私はこのマクロを以下のように使っています。

```
{% set lang_ext = macros::lang_ext() %}
{% set root = get_section(path="_index" ~ lang_ext ~ ".md") %}
```

ちなみに`{% set root = get_section(path="_index" ~ macros::lang_ext() ~ ".md") %}`のようにすることはできません。

### 現在の言語のルートURLを取得する

特定の言語に対するルートURLは`{base_url}/{code}`のように与えられますが、デフォルト言語については`{base_url}`で与えられます。
[「言語を意識してセクションを取得する」](#言語を意識してセクションを取得する)と同様に、特定の言語のルートURLは少しやっかいです。

またしても現在の言語に対応したパスセグメントに置き換わる`lang_seg`というマクロを作成しました。
このマクロは`"/{code}"`に置き換わりますが、デフォルト言語については空文字列になります。

```
{% macro lang_seg() %}{% if lang != config.default_language %}/{{ lang }}{% else %}{% endif %}{% endmacro lang_seg %}
```

私はこのマクロを以下のように使っています。

```html
<a class="navbar-item" href="{{ config.base_url }}{{ macros::lang_seg() }}">
  <img src="/codemonger.svg" width="112" height="28" alt="codemonger logo">
</a>
```

### 現在のページの言語を切り替える

英語と日本語を切り替えるためのリンクをこのウェブサイトのすべてのページに設置したかったのですが、すべてのページに手作業でリンクを埋め込みたくはありませんでした。
ということでこのウェブサイトのすべてのHTMLテンプレートのベースになっている`base.html`にリンクを埋め込むことにしました。

[`get_url`](https://www.getzola.org/documentation/templates/overview/#get-url)関数は`path`引数だけでなく`lang`オプションも受け取るので、この機能に適していそうでした。
もし現在のページのパスを`@/{section}/{page}.md`の形式で取得することができれば、`get_url`を通じて簡単に所望の言語で翻訳したURLと交換できそうです。

何度か試行錯誤したのち、`get_url`の`path`引数を作るのに`page.components`と`section.components`を使えることに気づきました。
`page.components`と`section.components`の挙動を注意深く観察し、分かったことは、
- `page.components`と`section.components`は現在のパスをスラッシュで区切ったパスセグメントの配列である。
- `page.components`と`section.components`はデフォルト言語を除いて言語コードから始まる。
  デフォルトの言語コードは省略される。
- `page.components`の最後の項目は拡張子(`.md`)を除く現在のページの名前である。
- `section.components`の最後の項目はインデックス(`_index.md`)ではなくセクションの名前である。
- デフォルト言語のルートページでは`section.components`は空である。

そして以下の複雑なテンプレートにたどり着きました。

```
{% if page %}
{%   if lang == config.default_language %}
{%     set relative_path = page.components | join(sep="/") %}
{%   else %}
{%     set relative_path = page.components | slice(start=1) | join(sep="/") %}
{%   endif %}
{%   set internal_path = "@/" ~ relative_path ~ ".md" %}
{% elif section %}
{%   if section.components | length  > 0 %}
{%     if lang == config.default_language %}
{%       set relative_path = section.components | join(sep="/") %}
{%     else %}
{%       set relative_path = section.components | slice(start=1) | join(sep="/") %}
{%     endif %}
{%     set internal_path = "@/" ~ relative_path ~ "/_index.md" %}
{%   else %}
{%     set internal_path = "/" %}
{%   endif %}
{% endif %}
```

上記のテンプレートが評価された後に、`get_url(path=internal_path, lang={code})`で`{code}`に指定した言語のページのURLを取得することができます。

最大の難点はすべてのページについて英語と日本語両方の翻訳を用意しなければならず、そうしないとZolaがエラーを出すということです。

### アンカーIDの難点

ZolaはデフォルトでMarkdownのすべてのセクションタイトルを[スラッグ化(slugified)アンカーID](https://www.getzola.org/documentation/getting-started/configuration/#slugification-strategies)に変換します。
セクションタイトルがASCII文字だけを含んでいる場合は何の問題もありませんが、ASCII以外の文字(例えば日本語文字)が含まれた途端にZolaは(少なくとも私には)予測不能なアンカーIDを吐き出します。
例えば、"言語を意識してセクションを取得する"というセクションタイトルは"yan-yu-woyi-shi-sitesekusiyonwoqu-de-suru"というアンカーIDに変わります。

この変換は`config.toml`ファイルのアンカーに関する`slugify`オプションを`"safe"`に変更すると回避できます。
しかしこの設定にすると記号等(non-letter)の文字に対して馴染みのない挙動\*をしてしまいます。例えば、空白はハイフン(`-`)ではなくアンダースコア(`_`)に置き換わり、大文字はそのまま、記号もそのままになります。
(\*私はGitHubのルールに馴染みがあります。)

当面の回避策はアンカーの`slugify`オプションを`"safe"`にし、新しいルールを受け入れるというものです。

たぶんいつかプルリクエストを投げるべきなのでしょう・・・