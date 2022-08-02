+++
title = "AWS APIGateway × OpenAPI (3. 出力編)"
description = "OpenAPI定義をCDKのREST API定義に統合するライブラリの開発過程を紹介するブログシリーズです。"
date = 2022-08-02
draft = false
[extra]
hashtags = ["AWS", "CDK", "APIGateway", "OpenAPI"]
thumbnail_name = "thumbnail.png"
+++

[OpenAPI](https://www.openapis.org)定義を[CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html)のREST API定義に統合する[ライブラリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)を開発しています。
これはライブラリの開発過程を紹介するシリーズのブログ投稿第3弾です。

<!-- more -->

## 背景

[本シリーズ最初のブログ投稿](../0006-open-api-and-cdk/)で、以下の課題を残しました。

> いつ実際にOpenAPI定義ファイルを出力すべきか?
> - 保存のための関数をユーザーが明示的に呼び出さなければならないのでしょうか?
> - それともCDKが[CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html)テンプレートに対してやるようにOpenAPIの定義ファイルもいつのまにやら保存されようにできるでしょうか?

このブログ投稿では、we tackle the 後者のケース(ユーザの明示的な呼び出しなしにライブラリにOpenAPI定義を出力させる)に挑みます。

## CDKはいつCloudFormationテンプレートを出力するのか?

[AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html)がCloudFormationテンプレートを出力するタイミングをトラップできれば、ユーザの明示的な呼び出しなしにOpenAPI定義を出力できそうです。
ということでOpenAPI定義を出力するのに応用できそうなフックを探してCDKのソースコード\*を眺めていくことにします。
まずは`cdk`コマンドを見てみましょう。
長いコードレビューをスキップしたい場合は、[節「フック」](#フック)まで読み飛ばしてもよいです。

\* 当時最新の[CDKバージョン`2.34.2`](https://github.com/aws/aws-cdk/tree/v2.34.2)を分析しました。
他のCDKバージョンでは状況は違っているかもしれません。

### cdkコマンドはどこに定義されているのか?

`cdk`コマンドは[CDKレポジトリの`packages/aws-cdk`フォルダ](https://github.com/aws/aws-cdk/tree/v2.34.2/packages/aws-cdk)に含まれています。
[CDKのレポジトリ](https://github.com/aws/aws-cdk/tree/v2.34.2)は巨大なので、`cdk`コマンドがどこで定義されているかというのをよくわかっていませんでした。
このブログ投稿では、`packages/aws-cdk`フォルダを`aws-cdk`と省略します。

#### synthとdeployサブコマンドは何をするのか?

CloudFormationテンプレートを生成するという点では、以下の2つの`cdk`サブコマンドが関心の対象です。
- [`cdk synth`](https://github.com/aws/aws-cdk/tree/v2.34.2/packages/aws-cdk#cdk-synthesize)
- [`cdk deploy`](https://github.com/aws/aws-cdk/tree/v2.34.2/packages/aws-cdk#cdk-deploy)

`cdk`コマンドのコマンドラインインターフェイスは[`aws-cdk/lib/cli.ts`](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts)に定義されています。
[`yargs`](https://github.com/yargs/yargs)の設定を行う長い行の中に、`synth`と`deploy` サブコマンドの定義があります。
- `synth`
    - オプション: [aws-cdk/lib/cli.ts#L86-L89](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L86-L89)
    - ハンドラ: [aws-cdk/lib/cli.ts#L528-L534](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L528-L534)
        - 結果として[`CdkToolkit#synth`](#CdkToolkit#synth)の呼び出しとなる。
- `deploy`
    - オプション: [aws-cdk/lib/cli.ts#L107-L150](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L107-L150)
    - ハンドラ: [aws-cdk/lib/cli.ts#L454-L483](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L454-L483)
        - 結果として[`CdkToolkit#deploy`](#CdkToolkit#deploy)の呼び出しとなる。

`cdk`のサブコマンドは結果的に[`aws-cdk/lib/cdk-toolkit.ts`](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts)に定義される`CdkToolkit`の対応するメソッドを呼び出すことになります。

##### CdkToolkit#synth

定義: [aws-cdk/lib/cdk-toolkit.ts#L517-L545](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L517-L545)

[aws-cdk/lib/cdk-toolkit.ts#L518](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L518)で`CdkToolkit#selectStacksForDiff`を呼び出します。
```ts
    const stacks = await this.selectStacksForDiff(stackNames, exclusively, autoValidate);
```

メソッド名からは明白ではありませんが、`CdkToolkit#selectionStacksForDiff`はCloudFormationテンプレートの生成において重要な働きをします。
[aws-cdk/lib/cdk-toolkit.ts#L621](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L621)にて[`CdkToolkit#assembly`](#CdkToolkit#assembly)を呼び出すことになります。
```ts
    const assembly = await this.assembly();
```

##### CdkToolkit#deploy

定義: [aws-cdk/lib/cdk-toolkit.ts#L126-L282](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L126-L282)

[aws-cdk/lib/cdk-toolkit.ts#L140](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L140)で`CdkToolkit#selectStacksForDeploy`を呼び出します。
```ts
    const stacks = await this.selectStacksForDeploy(options.selector, options.exclusively, options.cacheCloudAssembly);
```

[`CdkToolkit#synth`](#CdkToolkit#synth)と同様、`CdkToolkit#selectStacksForDeploy`はCloudFormationテンプレートの生成において重要な働きをします。
[aws-cdk/lib/cdk-toolkit.ts#L608](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L608)にて同じく[`CdkToolkit#assembly`](#CdkToolkit#assembly)の呼び出しとなります。
```ts
    const assembly = await this.assembly(cacheCloudAssembly);
```

##### CdkToolkit#assembly

定義: [aws-cdk/lib/cdk-toolkit.ts#L690-L692](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L690-L692)
```ts
  private assembly(cacheCloudAssembly?: boolean): Promise<CloudAssembly> {
    return this.props.cloudExecutable.synthesize(cacheCloudAssembly);
  }
```

[`CloudExecutable#synthesize`](#CloudExecutable#synthesize)の呼び出しと等価です。
`CloudExecutable`は[`aws-cdk/lib/api/cxapp/cloud-executable`](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts)に定義されています。

##### CloudExecutable#synthesize

定義: [aws-cdk/lib/api/cxapp/cloud-executable.ts#L63-L68](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L63-L68)

[aws-cdk/lib/api/cxapp/cloud-executable.ts#L65](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L65)にて[`CloudExecutable#doSynthesize`](#CloudExecutable#doSynthesize)を呼び出します。
```ts
      this._cloudAssembly = await this.doSynthesize();
```

##### CloudExecutable#doSynthesize

定義: [aws-cdk/lib/api/cxapp/cloud-executable.ts#L70-L124](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L70-L124)

実際の合成は[aws-cdk/lib/api/cxapp/cloud-executable.ts#L79](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L79)で行われます。
```ts
      const assembly = await this.props.synthesizer(this.props.sdkProvider, this.props.configuration);
```

`this.props.synthesizer`は[aws-cdk/lib/api/cxapp/cloud-executable.ts#L14](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L14)に定義される`Synthesizer`です。
```ts
type Synthesizer = (aws: SdkProvider, config: Configuration) => Promise<cxapi.CloudAssembly>;
```

`aws-cdk/lib/cli.ts`のコンテキストでは、[aws-cdk/lib/cli.ts#L305-L309](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L305-L309)で初期化されているように`this.props.synthesizer`は常に`execProgram`です。
```ts
  const cloudExecutable = new CloudExecutable({
    configuration,
    sdkProvider,
    synthesizer: execProgram,
  });
```

`execProgram`は[aws-cdk/lib/api/cxapp/exec.ts#L12-L136](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L12-L136)に定義されています。
以下の行から分かるように、`cdk`コマンドの`app`オプションに指定したコマンドを実行します(それぞれ[aws-cdk/lib/api/cxapp/exec.ts#L54](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L54), [aws-cdk/lib/api/cxapp/exec.ts#L65](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L65), [aws-cdk/lib/api/cxapp/exec.ts#L86](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L86))。

```ts
  const app = config.settings.get(['app']);
```

```ts
  const commandLine = await guessExecutable(appToArray(app));
```

```ts
  await exec(commandLine.join(' '));
```

`cdk`コマンドに`app`オプションなんて指定したことがないと思われるかもしれません。
CDKプロジェクトを`cdk init`コマンドで初期化すると、`cdk.json`ファイルが作成され、そこに`app`オプションのデフォルト値が保存されます。
`cdk.json`ファイルを覗くと、以下のような行が見つかります。
```json
  "app": "npx ts-node --prefer-ts-exts bin/cdk.ts",
```

このコマンド(`npx ts-node --prefer-ts-exts bin/cdk.ts`)が`execProgram`の実行しているものです。

`app`オプションに渡されたコマンドを実行した後、`execProgram`は`cdk`コマンドの`output`オプションに指定した出力フォルダから生成物を読み込みます(それぞれ[aws-cdk/lib/api/cxapp/exec.ts#L67](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L67), [aws-cdk/lib/api/cxapp/exec.ts#L78](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L78), [aws-cdk/lib/api/cxapp/exec.ts#L88](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L88))。

```ts
  const outdir = config.settings.get(['output']);
```

```ts
  env[cxapi.OUTDIR_ENV] = outdir;
```

```ts
  return createAssembly(outdir);
```

`output`オプションはデフォルトで`"cdk.out"`です([aws-cdk/lib/settings.ts#L75-L79](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/settings.ts#L75-L79))。
```ts
  public readonly defaultConfig = new Settings({
    versionReporting: true,
    pathMetadata: true,
    output: 'cdk.out',
  });
```

ということで、`bin/cdk.ts`が何を行っているかが次の焦点です。

### AppはいつCloudFormationテンプレートを出力しているのか?

`bin/cdk.ts`では、通常[`App`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.App.html)のインスタンスを作成します。
では`App`はいつCloudFormationテンプレートを出力しているのでしょうか?
`App`のソースコードを見てみましょう。

`App`は[core/lib/app.ts#L94-L155](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/app.ts#L94-L155)に定義されています。
このブログ投稿では、`packages/@aws-cdk/core`フォルダを`core`と省略します。

`App`のコンストラクタには、[core/lib/app.ts#L131](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/app.ts#L131)に興味深い行があります。
```ts
      process.once('beforeExit', () => this.synth());
```

これは`App`を実行するプロセスが終了時に`App#synth`を呼ぶようにします。
どうやら`App#synth`に答えがありそうです。
`App`は[`Stage`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.Stage.html)を継承しているので、`App#synth`は[`Stage#synth`](#Stage#synth)と等価です。

#### Stage#synth

定義: [core/lib/stage.ts#L174-L183](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stage.ts#L174-L183)

```ts
  public synth(options: StageSynthesisOptions = { }): cxapi.CloudAssembly {
    if (!this.assembly || options.force) {
      this.assembly = synthesize(this, {
        skipValidation: options.skipValidation,
        validateOnSynthesis: options.validateOnSynthesis,
      });
    }

    return this.assembly;
  }
```

[core/lib/private/synthesis.ts#L23-L50](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L23-L50)に定義されている`synthesize`を呼び出します。

`synthesize`の以下の2行が使えそうな2つのフックにつながることがわかりました。
- [core/lib/private/synthesis.ts#L36](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L36)
    ```ts
        validateTree(root);
    ```

  [`validateTree`](#validateTree)は[「Validatorフック」](#Validatorフック)につながります。
- [core/lib/private/synthesis.ts#L47](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L47)
    ```ts
      synthesizeTree(root, builder, options.validateOnSynthesis);
    ```

  [`synthesizeTree`](#synthesizeTree)は[「_toCloudFormationフック」](#_toCloudFormationフック)につながります。

#### validateTree

定義: [core/lib/private/synthesis.ts#L201-L214](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L201-L214)

```ts
function validateTree(root: IConstruct) {
  const errors = new Array<ValidationError>();

  visit(root, 'pre', construct => {
    for (const message of construct.node.validate()) {
      errors.push({ message, source: construct });
    }
  });

  if (errors.length > 0) {
    const errorList = errors.map(e => `[${e.source.node.path}] ${e.message}`).join('\n  ');
    throw new Error(`Validation failed with the following errors:\n  ${errorList}`);
  }
}
```

`validateTree`は`root`から始まるConstructツリーのすべてのノードを辿って([`visit`](#visit))各ノードに[`Node#validate`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html#validate)を適用します。
`Node#validate`は[`Node#addValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html#addwbrvalidationvalidation)でノードに追加した[`IValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.IValidation.html)の[`IValidation#validate`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.IValidation.html#validate)を呼び出します。

ということで **`IValidation`はOpenAPI定義を出力するためのフック** になりそうです。
使い方については[「Validatorフック」](#Validatorフック)を参照ください。

#### synthesizeTree

定義: [core/lib/private/synthesis.ts#L174-L191](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L174-L191)

```ts
function synthesizeTree(root: IConstruct, builder: cxapi.CloudAssemblyBuilder, validateOnSynth: boolean = false) {
  visit(root, 'post', construct => {
    const session = {
      outdir: builder.outdir,
      assembly: builder,
      validateOnSynth,
    };


    if (Stack.isStack(construct)) {
      construct.synthesizer.synthesize(session);
    } else if (construct instanceof TreeMetadata) {
      construct._synthesizeTree(session);
    } else {
      const custom = getCustomSynthesis(construct);
      custom?.onSynthesize(session);
    }
  });
}
```

`synthesizeTree`は`root`から始まるConstructツリーのすべてのノードを辿って([`visit`](#visit))各Constructを処理します。
重要な行は[core/lib/private/synthesis.ts#L183](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L183)にあります。
```ts
      construct.synthesizer.synthesize(session);
```

ここで`construct`は[`Stack`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.Stack.html)のインスタンスであり、[`Stack#synthesizer`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.Stack.html#synthesizer-1)はデフォルトで[`DefaultStackSynthesizer`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.DefaultStackSynthesizer.html)です。
なので上記の行は通常[DefaultStackSynthesizer#synthesize](#DefaultStackSynthesizer#synthesize)の呼び出しとなります。

#### DefaultStackSynthesizer#synthesize

定義: [core/lib/stack-synthesizers/default-synthesizer.ts#L387-L424](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack-synthesizers/default-synthesizer.ts#L387-L424)

`DefaultStackSynthesizer#synthesize`は[core/lib/stack-synthesizers/default-synthesizer.ts#L400](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack-synthesizers/default-synthesizer.ts#L400)で`DefaultStackSynthesizer#synthesizeStackTemplate`を呼び出します。
```ts
    this.synthesizeStackTemplate(this.stack, session);
```

`DefaultStackSynthesizer#synthesizeStackTemplate`は[`Stack#_synthesizeTemplate`](#Stack#_synthesizeTemplate)の呼び出しと等価です([core/lib/stack-synthesizers/default-synthesizer.ts#L380-L382](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack-synthesizers/default-synthesizer.ts#L380-L382))。
```ts
  protected synthesizeStackTemplate(stack: Stack, session: ISynthesisSession) {
    stack._synthesizeTemplate(session, this.lookupRoleArn);
  }
```

#### Stack#_synthesizeTemplate

定義: [core/lib/stack.ts#L770-L804](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L770-L804)

このメソッドは[core/lib/stack.ts#L779](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L779)で[`Stack#_toCloudFormation`](#Stack#_toCloudFormation)を呼び出します。
```ts
    const template = this._toCloudFormation();
```

#### Stack#_toCloudFormation

定義: [core/lib/stack.ts#L1007-L1045](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L1007-L1045)

以下の２行に注目してください([core/lib/stack.ts#L1031-L1032](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L1031-L1032))。
```ts
    const elements = cfnElements(this);
    const fragments = elements.map(e => this.resolve(e._toCloudFormation()));
```

このメソッドは[`cfnElements`](#cfnElements)ですべての子[`CfnElement`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CfnElement.html)を集め、`CfnElement#_toCloudFormation`をそれぞれに適用します。
`CfnElement`はすべての[L1 Construct](https://docs.aws.amazon.com/cdk/v2/guide/constructs.html#constructs_l1_using)のベースクラスで、`CfnElement#_toCloudFormation`は[core/lib/cfn-element.ts#L161](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/cfn-element.ts#L161)に定義される内部メソッドです。

ということで **`CfnElement#_toCloudFormation`もOpenAPI定義を出力するためのもう1つのフック** になりそうです。
使い方については[「_toCloudFormationフック」](#_toCloudFormationフック)を参照ください。

## フック

上記の分析により、OpenAPI定義の出力に応用できるフックは2つありそうです。
- [Validatorフック](#Validatorフック)
- [_toCloudFormationフック](#_toCloudFormationフック)

### Validatorフック

「Validatorフック」は[`Node#addValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html#addwbrvalidationvalidation)で[`Node`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html)に追加することのできる[`IValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.IValidation.html)を応用します。
細かい分析については[節「validateTree」](#validateTree)を参照ください。

とりあえずシンプルさを優先して[私のライブラリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)を実装するのには **このフックを選択** しました。
以下のコードは`RestApiWithSpec`のコンストラクタから抽出したものです。
完全な定義は[GitHubレポジトリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)にあります。

```ts
  constructor(scope: Construct, id: string, readonly props: RestApiWithSpecProps) {
    // ... 他の初期化ステップ
    Node.of(this).addValidation({
      validate: () => this.synthesizeOpenApi(), // synthesizeOpenApiがOpenAPI定義を書き込む
    });
  }
```

弱点はバリデーションが無効だと機能しないことです。

### _toCloudFormationフック

「_toCloudFormationフック」は内部メソッドの`CfnElement#_toCloudFormation`をオーバーライドして応用します。
細かい分析については[節「synthesizeTree」](#synthesizeTree)を参照ください。

もし[私のライブラリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)でこのフックを使うとしたら、`RestApiWithSpec`のコンストラクタは以下のようなものになりそうです。

```ts
  constructor(scope: Construct, id: string, readonly props: RestApiWithSpecProps) {
    // ... 他の初期化ステップ
    class ToCloudFormationHook extends CfnElement {
      constructor(private scope: RestApiWithSpec, id: string) {
        super(scope, id);
      }

      _toCloudFormation() {
        this.scope.synthesizeOpenApi(); // synthesizeOpenApiがOpenAPI定義を書き込む
        return {}; // 実際にはCloudFormationリソースは追加されない
      }
    }
    new ToCloudFormationHook(this, 'ToCloudFormationHook');
  }
```

このフックには欠点がいくつかあります。
- `CfnElement#_toCloudFormation`は内部メソッドであり変更されるかもしれない。
- 私の実験では、`ToCloudFormationHook#_toCloudFormation`が2回呼ばれた(何故かは不明)。

## 結論

このブログ投稿では、CDKのソースコードを眺めました。
OpenAPI定義に使える以下の2つのフックを見つけました。
- [Validatorフック](#Validatorフック)
- [_toCloudFormationフック](#_toCloudFormationフック)

[私のライブラリ](https://github.com/codemonger-io/cdk-rest-api-with-spec)ではシンプルさを優先して「Validatorフック」を選択しました。

## 補足

この節ではCDKで使われているユーティリティ関数をいくつか紹介します。

### visit

定義: [core/lib/private/synthesis.ts#L219-L232](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L219-L232)

```ts
function visit(root: IConstruct, order: 'pre' | 'post', cb: (x: IConstruct) => void) {
  if (order === 'pre') {
    cb(root);
  }

  for (const child of root.node.children) {
    if (Stage.isStage(child)) { continue; }
    visit(child, order, cb);
  }

  if (order === 'post') {
    cb(root);
  }
}
```

この関数は`root`から始まるConstructツリーのすべてのノードを辿って、`cb`に指定される関数をそれぞれに適用します。

### cfnElements

定義: [core/lib/stack.ts#L1279-L1292](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L1279-L1292)

```ts
function cfnElements(node: IConstruct, into: CfnElement[] = []): CfnElement[] {
  if (CfnElement.isCfnElement(node)) {
    into.push(node);
  }

  for (const child of Node.of(node).children) {
    // Don't recurse into a substack
    if (Stack.isStack(child)) { continue; }


    cfnElements(child, into);
  }

  return into;
}
```

この関数は`node`から始まるConstructツリーのすべての[`CfnElement`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CfnElement.html)を再起的に集めます。