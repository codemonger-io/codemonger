English / [日本語](./README.ja.md)

# Common library for CDK stacks

Provides types and functions shared among CDK stacks in this repository.

## How to use this library

This library is inteded to be locally linked from CDK stacks in this repository.
The following stacks link this library so far,
- [`../cdk`](../cdk)
- [`../cdk-ops`](../cdk-ops)

The above CDK stacks import the contents of the `dist` folder.

### Updating this library

If you change the code of this library, you have to run the following in this folder,

```sh
npm run build
```

You will find the `dist` folder updated.