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
Here is a command for development:

```sh
CONTENTS_DISTRIBUTION_DOMAIN_NAME=`AWS_PROFILE=codemonger-jp aws cloudformation describe-stacks --stack-name codemonger-development --query "Stacks[0].Outputs[?OutputKey=='ContentsDistributionDomainName']|[0].OutputValue" --output text`
```

## Deploying contents

After [generating contents](#generating-contents), copy the contents in the `public` folder to the S3 bucket for contents.

```sh
aws s3 sync --delete --exclude "*.DS_Store" ./public s3://$CONTENTS_BUCKET_NAME/
```

Please replace `CONTENTS_BUCKET_NAME` with the name of the S3 bucket for contents.
Please refer to the instructions in the [`../cdk`](../cdk) folder for how to provision the S3 bucket.
Here is a command for development:

```sh
CONTENTS_BUCKET_NAME=`AWS_PROFILE=codemonger-jp aws cloudformation describe-stacks --stack-name codemonger-development --query "Stacks[0].Outputs[?OutputKey=='ContentsBucketName']|[0].OutputValue" --output text`
```

## Writing blogs

### Adding hashtags for the Tweet button

The [front matter](https://www.getzola.org/documentation/content/page/#front-matter) of every blog page can include a `hashtags` option in the `extra` data.
This option accepts an array of hashtag strings you want to add to the Tweet button attached to the blog post.
The following example adds `"hashtags=aws,cloudfront"` to the Tweet button.

```
+++
title = "Serving contents from S3 via CloudFront"
date = 2022-06-20
[extra]
hashtags = ["aws", "cloudfront"]
+++
```

### Adding the thumbnail image

The [front matter](https://www.getzola.org/documentation/content/page/#front-matter) of every blog page can include a `thumbnail_name` option in the `extra` data.
This option accepts the name of the image file to be shown at the beginning of the blog post and appear as social thumbnails; e.g., twitter card.
The following example shows the image file `"thumbnail.png"` in the same folder as the `index.md` file of the blog page as the thumbnail.

```
+++
title = "When Omit<Type, Keys> breaks (my expectation)"
date = 2022-07-12
[extra]
thumbnail_name = "thumbnail.png"
+++
```

To add the thumbnail image to a blog post, create a folder of the blog page and put the thumbnail image file in it.
The image file should be in the same folder as the `index.md` file of the blog page, or social thumbnails may not work.