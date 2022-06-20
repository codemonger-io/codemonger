+++
title = "Serving contents from S3 via CloudFront"
date = 2022-06-20
draft = false
[extra]
hashtags = ["aws", "cloudfront"]
+++

This website is generated with [Zola](https://www.getzola.org) and delivered from [Amazon S3](https://aws.amazon.com/s3/) via [Amazon CloudFront](https://aws.amazon.com/cloudfront/).
This blog post shows what I have done to successfully deliver the contents in this configuration.

<!-- more -->

## Plan for contents delivery

I intended to deploy my website to an [S3 bucket](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-buckets-s3.html) and deliver it through a [CloudFront distribution](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-working-with.html).
This idea itself should be very straightforward.

## How Zola locates contents

Zola locates the contents of individual sections and pages at a path like `/{parent section path}/{section or page title}/index.html`; e.g., `/blog/0002-serving-contents-from-s3-via-cloudfront/index.html` for this page.
And when it refers to the contents, it omits `/index.html` from the path like `/{parent section path}/{section or page title}` that is supposed to be expanded with trailing `/index.html` by a server; e.g., `/blog/0002-serving-contents-from-s3-via-cloudfront` for this page.
Unfortunately, this, expanding a subdirectory with `index.html`, is not an easy\* task for a CloudFront distribution.
(\*It turned out not easy at all!)

## Introducing CloudFront Functions

To address the above issue, we can use [CloudFront Functions](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-functions.html).
There is an exact [use case of a CloudFront Function for this situation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example-function-add-index.html) in the guide provided by AWS.
However, this seemingly easy task turned out not that easy at all.
I had to carefully deal with the URI specifications, and my findings were,
- A URI may end with an anchor ID; i.e., followed by a hash (`#`).
    - You may have to insert `[/]index.html` between the last URI segment and the hash.
- An anchor ID may contain any symbols including dots (see [_Difficulties in anchor IDs_](/blog/0001-introducing-zola#Difficulties_in_anchor_IDs) in the past post).
    - You cannot simply determine that a file extension is specified when you just find a dot in the URI as the [above use case](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/example-function-add-index.html) does.
- An anchor ID may even contain hashes and slashes because any symbols in a markdown section title are kept.
    - You have to first locate the first hash in a URI to separate an actual path and an anchor ID.
      This processing should be legal if I correctly understand the [syntax of a URI](https://datatracker.ietf.org/doc/html/rfc3986#section-3.5).
- As far as I tested, a section or page title may not contain dots because Zola recognizes it as a language code delimiter as soon as Zola finds one.
  So you should not supply `/index.html` if the last path segment of a URI excluding an anchor ID contains a dot because it should be a resource other than a section or page.
- A URI may contain a query part starting with a question mark (`?`).
    - You may have to insert `[/]index.html` between the last URI segment and the question mark.

Thus, my algorithm was,
1. A URI is given &rightarrow; `uri`.
2. Locate a first optional hash (`#`) in `uri` and separate a fragment (substring starting from `#` or empty) from it &rightarrow; [`uri`, `fragment`].
3. Locate a first optional question mark (`?`) in `uri` and separate a query (substring starting from `?` or empty) from it &rightarrow; [`uri`, `query`].
4. Locate the last slash (`/`) in `uri` and separate the last path segment (substring starting from `/`) from it &rightarrow; [`uri`, `last path segment`].
5. If `last path segment` contains no dots (`.`), expand `last path segment` with,
    - `"index.html"` if `last path segment` ends with `/`,
    - `"/index.html"` otherwise
6. Return a new URI = `uri` + `last path segment` + `query` + `fragment`

The `handler` function I implemented can be viewed [here](https://github.com/codemonger-io/codemonger/blob/c681d9c928a3e02dc2efcaa89f4b4d9f93a6eeaa/cdk/cloudfront-fn/expand-index.js).

By the way, the [JavaScript engine for CloudFront Functions is based on ECMA v5.1](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/functions-javascript-runtime-features.html) and you may feel it is outdated.

## Unit testing CloudFront Functions

Unit testing CloudFront Functions was also challenging.
I found [this article](https://www.uglydirtylittlestrawberry.co.uk/posts/unit-testing-cloudfront-functions/) useful.
The problem is that the CloudFront Functions runtime allows neither the `module.exports` idiom nor the `export` modifier.
So there was no standard manner where I could export any function from a CloudFront Functions script.
A workaround suggested by the [above article](https://www.uglydirtylittlestrawberry.co.uk/posts/unit-testing-cloudfront-functions/) was to use [`babel-plugin-rewire`](https://www.npmjs.com/package/babel-plugin-rewire) which injects functions to access internal variables and functions in an imported script.

When I tried `babel-plugin-rewire`, I faced an [issue of `babel-plugin-rewire`](https://github.com/speedskater/babel-plugin-rewire/issues/109#issuecomment-202526786) that an unused internal function was removed.
This was problematic because the `handler` function itself that is invoked from the runtime was not called inside the source file.
As I mentioned earlier, neither the `module.exports` idiom nor the `export` modifier worked.
My workaround was to add another function `handlerImpl` and make `handler` simply call it, then I could test `handlerImpl` instead.

```js
function handler(event) {
  return handlerImpl(event);
}
function handlerImpl(event) {
  // actual implementation...
}
```

I configured Jest to process `*.js` files in a specific folder with [Babel](https://babeljs.io) + `babel-plugin-rewire`.
My `jest.config.js` file can be viewed [here](https://github.com/codemonger-io/codemonger/blob/c681d9c928a3e02dc2efcaa89f4b4d9f93a6eeaa/cdk/babel.config.js).