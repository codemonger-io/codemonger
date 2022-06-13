English / [日本語](./README.ja.md)

# Zola project for codemonger

This Zola project generates contents of the codemonger website.

## Generating contents

The following command will output contents of the codemonger website in a `public` folder.

```sh
zola build
```

To deploy to the development stage, you have to add the `--base-url` option.

```sh
zola build --base-url https://$CONTENTS_DISTRIBUTION_DOMAIN_NAME
```

Please replace `$CONTENTS_DISTRIBUTION_DOMAIN_NAME` with the domain name of the CloudFront distribution of the development stage.
Please refer to the instructions in the [`../cdk`](../cdk) folder for how to provision the CloudFront distribution.

## Deploying contents

After [generating contents](#generating-contents), copy the contents in the `public` folder to the S3 bucket for contents.

```sh
aws s3 cp --recursive ./public s3://$CONTENTS_BUCKET_NAME/
```

Please replace `CONTENTS_BUCKET_NAME` with the name of the S3 bucket for contents.
Please refer to the instructions in the [`../cdk`](../cdk) folder for how to provision the S3 bucket.