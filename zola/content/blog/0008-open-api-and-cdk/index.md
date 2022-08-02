+++
title = "AWS APIGateway × OpenAPI (3. Output)"
description = "This is a series of blog posts that will walk you through the development of a library that integrates an OpenAPI definition with a REST API definition on the CDK"
date = 2022-08-02
draft = false
[extra]
hashtags = ["AWS", "CDK", "APIGateway", "OpenAPI"]
thumbnail_name = "thumbnail.png"
+++

I have been working on a [library](https://github.com/codemonger-io/cdk-rest-api-with-spec) that integrates an [OpenAPI](https://www.openapis.org) definition with a REST API definition on the [CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html).
This is the third blog post of the series that will walk you through the development of the library.

<!-- more -->

## Background

In the [first blog post of this series](../0006-open-api-and-cdk/), we left the following challenge,

> When should the library actually output the OpenAPI definition file?
> - Should a user explicitly call a function to save?
> - Or, can we magically save the OpenAPI definition file like the CDK does to the [CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) template?

In this blog post, we tackle the latter case; i.e., make the library output an OpenAPI definition without an explicit call by a user.

## When does the CDK output a CloudFormation template?

If we can trap the timing when the [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html) outputs a CloudFormation template, we may output an OpenAPI definition without an explicit call by a user.
So we are going to walk through the CDK source code\* to locate hooks we can utilize to write an OpenAPI definition.
Let's look into the `cdk` command first.
If you want to skip the extensive code review, you can jump to the ["Hooks" section](#Hooks).

\* I have analyzed the then latest [version `2.34.2` of the CDK](https://github.com/aws/aws-cdk/tree/v2.34.2).
Things may be different in other CDK versions.

### Where is the cdk command defined?

The `cdk` command is included in the [`packages/aws-cdk` folder in the CDK repository](https://github.com/aws/aws-cdk/tree/v2.34.2/packages/aws-cdk).
Since the [repository of the CDK](https://github.com/aws/aws-cdk/tree/v2.34.2) is huge, it was not that obvious to me where the `cdk` command was defined.
In this blog post, I abbreviate the `packages/aws-cdk` folder to `aws-cdk`.

#### What do the synth and deploy subcommands do?

In terms of the CloudFormation template generation, the following two `cdk` subcommands are our concern,
- [`cdk synth`](https://github.com/aws/aws-cdk/tree/v2.34.2/packages/aws-cdk#cdk-synthesize)
- [`cdk deploy`](https://github.com/aws/aws-cdk/tree/v2.34.2/packages/aws-cdk#cdk-deploy)

The command line interface of the `cdk` command is defined in [`aws-cdk/lib/cli.ts`](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts).
In the long lines of [`yargs`](https://github.com/yargs/yargs) settings, you can find definitions of `synth` and `deploy` subcommands.
- `synth`
    - options: [aws-cdk/lib/cli.ts#L86-L89](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L86-L89)
    - handler: [aws-cdk/lib/cli.ts#L528-L534](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L528-L534)
        - Ends up with a call to [`CdkToolkit#synth`](#CdkToolkit#synth).
- `deploy`
    - options: [aws-cdk/lib/cli.ts#L107-L150](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L107-L150)
    - handler: [aws-cdk/lib/cli.ts#L454-L483](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L454-L483)
        - Ends up with a call to [`CdkToolkit#deploy`](#CdkToolkit#deploy).

The `cdk` subcommands eventually call corresponding methods of `CdkToolkit` defined in [`aws-cdk/lib/cdk-toolkit.ts`](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts).

##### CdkToolkit#synth

Definition: [aws-cdk/lib/cdk-toolkit.ts#L517-L545](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L517-L545)

It calls `CdkToolkit#selectStacksForDiff` at [aws-cdk/lib/cdk-toolkit.ts#L518](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L518):
```ts
    const stacks = await this.selectStacksForDiff(stackNames, exclusively, autoValidate);
```

Although it is not clear from the method name, `CdkToolkit#selectionStacksForDiff` does essential work for the CloudFormation template generation.
It eventually calls [`CdkToolkit#assembly`](#CdkToolkit#assembly) at [aws-cdk/lib/cdk-toolkit.ts#L621](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L621):
```ts
    const assembly = await this.assembly();
```

##### CdkToolkit#deploy

Definition: [aws-cdk/lib/cdk-toolkit.ts#L126-L282](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L126-L282)

It calls `CdkToolkit#selectStacksForDeploy` at [aws-cdk/lib/cdk-toolkit.ts#L140](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L140):
```ts
    const stacks = await this.selectStacksForDeploy(options.selector, options.exclusively, options.cacheCloudAssembly);
```

Like [`CdkToolkit#synth`](#CdkToolkit#synth), `CdkToolkit#selectStacksForDeploy` does essential work for the CloudFormation template generation.
It also ends up with a call to [`CdkToolkit#assembly`](#CdkToolkit#assembly) at [aws-cdk/lib/cdk-toolkit.ts#L608](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L608):
```ts
    const assembly = await this.assembly(cacheCloudAssembly);
```

##### CdkToolkit#assembly

Definition: [aws-cdk/lib/cdk-toolkit.ts#L690-L692](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cdk-toolkit.ts#L690-L692)
```ts
  private assembly(cacheCloudAssembly?: boolean): Promise<CloudAssembly> {
    return this.props.cloudExecutable.synthesize(cacheCloudAssembly);
  }
```

It is equivalent to a call to [`CloudExecutable#synthesize`](#CloudExecutable#synthesize).
`CloudExecutable` is defined in [`aws-cdk/lib/api/cxapp/cloud-executable`](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts).

##### CloudExecutable#synthesize

Definition: [aws-cdk/lib/api/cxapp/cloud-executable.ts#L63-L68](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L63-L68)

It calls [`CloudExecutable#doSynthesize`](#CloudExecutable#doSynthesize) at [aws-cdk/lib/api/cxapp/cloud-executable.ts#L65](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L65):
```ts
      this._cloudAssembly = await this.doSynthesize();
```

##### CloudExecutable#doSynthesize

Definition: [aws-cdk/lib/api/cxapp/cloud-executable.ts#L70-L124](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L70-L124)

The actual synthesis is done at [aws-cdk/lib/api/cxapp/cloud-executable.ts#L79](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L79):
```ts
      const assembly = await this.props.synthesizer(this.props.sdkProvider, this.props.configuration);
```

`this.props.synthesizer` is a `Synthesizer` defined at [aws-cdk/lib/api/cxapp/cloud-executable.ts#L14](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/cloud-executable.ts#L14):
```ts
type Synthesizer = (aws: SdkProvider, config: Configuration) => Promise<cxapi.CloudAssembly>;
```

In the context of `aws-cdk/lib/cli.ts`, `this.props.synthesizer` is always `execProgram` as it is initialized in [aws-cdk/lib/cli.ts#L305-L309](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/cli.ts#L305-L309).
```ts
  const cloudExecutable = new CloudExecutable({
    configuration,
    sdkProvider,
    synthesizer: execProgram,
  });
```

`execProgram` is defined in [aws-cdk/lib/api/cxapp/exec.ts#L12-L136](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L12-L136).
According to the following lines, it runs the command specified to the `app` option of the `cdk` command (([aws-cdk/lib/api/cxapp/exec.ts#L54](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L54), [aws-cdk/lib/api/cxapp/exec.ts#L65](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L65), and [aws-cdk/lib/api/cxapp/exec.ts#L86](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L86)) respectively):

```ts
  const app = config.settings.get(['app']);
```

```ts
  const commandLine = await guessExecutable(appToArray(app));
```

```ts
  await exec(commandLine.join(' '));
```

You may think you have never specified the `app` option to the `cdk` command.
If you initialize your CDK project with the `cdk init` command, the command creates the `cdk.json` file and saves the default `app` option value in it.
If you look into your `cdk.json` file, you will find a line similar to the following:
```json
  "app": "npx ts-node --prefer-ts-exts bin/cdk.ts",
```

This command (`npx ts-node --prefer-ts-exts bin/cdk.ts`) is what `execProgram` executes.

After running the command given to the `app` option, `execProgram` loads the artifacts from the output folder specified to the `output` option of the `cdk` command ([aws-cdk/lib/api/cxapp/exec.ts#L67](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L67), [aws-cdk/lib/api/cxapp/exec.ts#L78](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L78), and [aws-cdk/lib/api/cxapp/exec.ts#L88](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/api/cxapp/exec.ts#L88) respectively):

```ts
  const outdir = config.settings.get(['output']);
```

```ts
  env[cxapi.OUTDIR_ENV] = outdir;
```

```ts
  return createAssembly(outdir);
```

The `output` option is `"cdk.out"` by default ([aws-cdk/lib/settings.ts#L75-L79](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/aws-cdk/lib/settings.ts#L75-L79)):
```ts
  public readonly defaultConfig = new Settings({
    versionReporting: true,
    pathMetadata: true,
    output: 'cdk.out',
  });
```

Thus, our next focus is what our `bin/cdk.ts` does.

### When does App output a CloudFormation template?

In our `bin/cdk.ts`, we usually create an instance of [`App`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.App.html).
So when does `App` output a CloudFormation template?
Let's look into the source code of `App`.

`App` is defined in [core/lib/app.ts#L94-L155](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/app.ts#L94-L155).
In this blog post, I abbreviate the `packages/@aws-cdk/core` folder to `core`.

In the constructor of `App`, there is an interesting line at [core/lib/app.ts#L131](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/app.ts#L131):
```ts
      process.once('beforeExit', () => this.synth());
```

It makes the process running `App` call `App#synth` at exit.
So we can anticipate the answer would be in `App#synth`.
Since `App` extends [`Stage`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.Stage.html), `App#synth` is equivalent to [`Stage#synth`](#Stage#synth).

#### Stage#synth

Definition: [core/lib/stage.ts#L174-L183](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stage.ts#L174-L183)

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

It calls `synthesize` defined at [core/lib/private/synthesis.ts#L23-L50](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L23-L50).

I have found that the following two lines in `synthesize` lead to two possible hooks we can count on,
- [core/lib/private/synthesis.ts#L36](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L36)
    ```ts
        validateTree(root);
    ```

  [`validateTree`](#validateTree) leads to a ["validator hook"](#Validator_hook).
- [core/lib/private/synthesis.ts#L47](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L47)
    ```ts
      synthesizeTree(root, builder, options.validateOnSynthesis);
    ```

  [`synthesizeTree`](#synthesizeTree) leads to a ["_toCloudFormation hook"](#_toCloudFormation_hook).

#### validateTree

Definition: [core/lib/private/synthesis.ts#L201-L214](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L201-L214)

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

`validateTree` traverses ([visits](#visit)) all the nodes in the constructs tree starting from `root` and applies [`Node#validate`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html#validate) to each of them.
`Node#validate` calls [`IValidation#validate`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.IValidation.html#validate) of [`IValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.IValidation.html)s attached to the node with [`Node#addValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html#addwbrvalidationvalidation).

So **`IValidation` can be a hook to output an OpenAPI definition**.
Please refer to ["Validator hook"](#Validator_hook) for how to use it.

#### synthesizeTree

Definition: [core/lib/private/synthesis.ts#L174-L191](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L174-L191)

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

`synthesizeTree` traverses ([visits](#visit)) all the nodes in the constructs tree starting from `root` and processes each construct.
The important line is at [core/lib/private/synthesis.ts#L183](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L183):
```ts
      construct.synthesizer.synthesize(session);
```

Here `construct` is an instance of [`Stack`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.Stack.html), and [`Stack#synthesizer`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.Stack.html#synthesizer-1) is [`DefaultStackSynthesizer`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.DefaultStackSynthesizer.html) by default.
So the above line usually becomes a call to [DefaultStackSynthesizer#synthesize](#DefaultStackSynthesizer#synthesize).

#### DefaultStackSynthesizer#synthesize

Definition: [core/lib/stack-synthesizers/default-synthesizer.ts#L387-L424](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack-synthesizers/default-synthesizer.ts#L387-L424)

`DefaultStackSynthesizer#synthesize` calls `DefaultStackSynthesizer#synthesizeStackTemplate` at [core/lib/stack-synthesizers/default-synthesizer.ts#L400](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack-synthesizers/default-synthesizer.ts#L400):
```ts
    this.synthesizeStackTemplate(this.stack, session);
```

`DefaultStackSynthesizer#synthesizeStackTemplate` is equivalent to a call to [`Stack#_synthesizeTemplate`](#Stack#_synthesizeTemplate) ([core/lib/stack-synthesizers/default-synthesizer.ts#L380-L382](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack-synthesizers/default-synthesizer.ts#L380-L382)):
```ts
  protected synthesizeStackTemplate(stack: Stack, session: ISynthesisSession) {
    stack._synthesizeTemplate(session, this.lookupRoleArn);
  }
```

#### Stack#_synthesizeTemplate

Definition: [core/lib/stack.ts#L770-L804](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L770-L804)

This method calls [`Stack#_toCloudFormation`](#Stack#_toCloudFormation) at [core/lib/stack.ts#L779](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L779):
```ts
    const template = this._toCloudFormation();
```

#### Stack#_toCloudFormation

Definition: [core/lib/stack.ts#L1007-L1045](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L1007-L1045)

Please pay attention to the following two lines ([core/lib/stack.ts#L1031-L1032](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L1031-L1032)):
```ts
    const elements = cfnElements(this);
    const fragments = elements.map(e => this.resolve(e._toCloudFormation()));
```

This method collects all the child [`CfnElement`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CfnElement.html)s with [`cfnElements`](#cfnElements), and applies `CfnElement#_toCloudFormation` to each of them.
`CfnElement` is the base class of every [L1 construct](https://docs.aws.amazon.com/cdk/v2/guide/constructs.html#constructs_l1_using), and `CfnElement#_toCloudFormation` is an internal method defined at [core/lib/cfn-element.ts#L161](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/cfn-element.ts#L161).

So the **`CfnElement#_toCloudFormation` method can be another hook** to output an OpenAPI definition.
Please refer to ["_toCloudFormation hook"](#_toCloudFormation_hook) for how to use it.

## Hooks

According to the above analysis, there may be two hooks we can utilize to output an OpenAPI definition.
- [Validator hook](#Validator_hook)
- [_toCloudFormation hook](#_toCloudFormation_hook)

### Validator hook

A "validator hook" utilizes [`IValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.IValidation.html) that we can attach to [`Node`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html)s with [`Node#addValidation`](https://docs.aws.amazon.com/cdk/api/v2/docs/constructs.Node.html#addwbrvalidationvalidation).
Please refer to the [section "validateTree"](#validateTree) for more detailed analysis.

I **have chosen this hook** to implement [my library](https://github.com/codemonger-io/cdk-rest-api-with-spec) so far because of its simplicity.
The following code is an excerpt from the constructor of `RestApiWithSpec`.
You can find the full definition on [my GitHub repository](https://github.com/codemonger-io/cdk-rest-api-with-spec).

```ts
  constructor(scope: Construct, id: string, readonly props: RestApiWithSpecProps) {
    // ... other initialization steps
    Node.of(this).addValidation({
      validate: () => this.synthesizeOpenApi(), // synthesizeOpenApi writes the OpenAPI definition
    });
  }
```

A drawback is that it does not work if validation is disabled.

### _toCloudFormation hook

A "_toCloudFormation hook" utilizes an internal method `CfnElement#_toCloudFormation` that we can override.
Please refer to the [section "synthesizeTree"](#synthesizeTree) for more detailed analysis.

If I used this hook in [my library](https://github.com/codemonger-io/cdk-rest-api-with-spec), the constructor of `RestApiWithSpec` could become something similar to the following:

```ts
  constructor(scope: Construct, id: string, readonly props: RestApiWithSpecProps) {
    // ... other initialization steps
    class ToCloudFormationHook extends CfnElement {
      constructor(private scope: RestApiWithSpec, id: string) {
        super(scope, id);
      }

      _toCloudFormation() {
        this.scope.synthesizeOpenApi(); // synthesizeOpenApi writes the OpenAPI definition
        return {}; // no CloudFormation resource is actually added
      }
    }
    new ToCloudFormationHook(this, 'ToCloudFormationHook');
  }
```

There are some disadvantages to this hook.
- `CfnElement#_toCloudFormation` is an internal method that may be subject to change.
- In my experiment, `ToCloudFormationHook#_toCloudFormation` was called twice (I have not figured out why).

## Conclusion

In this blog post, we have walked through the source code of the CDK.
We have located the following two hooks we can use to output an OpenAPI definition,
- [Validator hook](#Validator_hook)
- [_toCloudFormation hook](#_toCloudFormation_hook)

I have chosen "Validator hook" for [my library](https://github.com/codemonger-io/cdk-rest-api-with-spec) because of its simplicity.

## Appendix

This section introduces some utility functions used in the CDK.

### visit

Definition: [core/lib/private/synthesis.ts#L219-L232](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/private/synthesis.ts#L219-L232)

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

This function traverses all the nodes in the constructs tree starting from `root`, and applies a function specified to `cb` to each of them.

### cfnElements

Definition: [core/lib/stack.ts#L1279-L1292](https://github.com/aws/aws-cdk/blob/7abcbc6df6e4a37b3b1ef6c26328d4ecaff56fa6/packages/%40aws-cdk/core/lib/stack.ts#L1279-L1292)

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

This function recursively collects every [`CfnElement`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.CfnElement.html) in the constructs tree starting from `node`.