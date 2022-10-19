English / [日本語](./README.ja.md)

# codemonger

![codemonger](docs/imgs/codemonger.svg)

This is a repository to maintain the website of `codemonger.io`.

The website is hosted on [AWS](https://aws.amazon.com).

## Managing AWS resources

Please refer to the subfolder [`cdk`](cdk).

## Managing contents

Please refer to the subfolder [`zola`](zola).

## DevOps

The following ["DevOps"](https://en.wikipedia.org/wiki/DevOps) features are also provided,
- Continuous delivery: when the `main` branch of this repository is updated, the workflow to update the codemonger website starts.
- Data warehouse: access logs of the codemonger website are stored in the data warehouse.

Please refer to the subfolder [`cdk-ops`](cdk-ops) for more details.