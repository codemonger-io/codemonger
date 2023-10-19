+++
title = "FlechasDB"
description = "Serverless-friendly vector database"
date = 2023-10-19
draft = false
weight = 1
[extra]
hashtags = ["FlechasDB", "vector-database", "serverless"]
thumbnail_name = "flechasdb-brand.png"
+++

A serverless-friendly vector database in your hands

<!-- more -->

**FlechasDB** is a [serverless](https://aws.amazon.com/serverless/)-friendly [vector database](https://www.pinecone.io/learn/vector-database/)[^1].

[^1]: _What is a Vector Database?_ by [Pinecone](https://www.pinecone.io). It surprised me that there seemed no [Wikipedia](https://www.wikipedia.org) page exists for vector databases.

## Features

1. Save/Load database files to/from [Amazon S3](https://aws.amazon.com/s3/) buckets
2. Run on [Amazon Linux 2](https://aws.amazon.com/amazon-linux-2/?amazon-linux-whats-new.sort-by=item.additionalFields.postDateTime&amazon-linux-whats-new.sort-order=desc)[^2]

More features are coming!

[^2]: Amazon Linux 2 is the standard operating system of [AWS Lambda](https://aws.amazon.com/lambda/) instances as of this writing.

## How to get started

The core library `flechasdb` and its Amazon S3 extension `flechasdb-s3` are available from the following GitHub repositories respectively:
- <https://github.com/codemonger-io/flechasdb>
- <https://github.com/codemonger-io/flechasdb-s3>

You can use `flechasdb` and `flechasdb-s3` on [AWS Lambda](https://aws.amazon.com/lambda/) by integrating them into a [custom Lambda runtime](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html) for [Amazon Linux 2](https://aws.amazon.com/amazon-linux-2/?amazon-linux-whats-new.sort-by=item.additionalFields.postDateTime&amazon-linux-whats-new.sort-order=desc).
Since both `flechasdb` and `flechasdb-s3` are written in [Rust](https://www.rust-lang.org), [`cargo-lambda`](https://www.cargo-lambda.info) may be helpful.
You can find some examples of deploying Lambda functions using `flechasdb` and `flechasdb-s3` with [AWS Cloud Development Kit (CDK)](https://aws.amazon.com/cdk/) in the following GitHub repositories,
- <https://github.com/codemonger-io/mumble/tree/main/cdk>
- <https://github.com/codemonger-io/mumble-embedding/tree/main/cdk>

## FlechasDB in action

[Mumble](../mumble/) uses FlechasDB to power its search feature.
It builds the FlechasDB database from [OpenAI's embeddings](https://platform.openai.com/docs/models/embeddings) calculated for posts (*mumblings*) and stores the database files in an [Amazon S3](https://aws.amazon.com/s3/) bucket.
You can try it on [Kikuo's Mumble profile](https://mumble.codemonger.io/viewer/users/kemoto/).

![similarity search demo](./similarity-search-demo.gif)

## Background

There are better products and services out there: [Pinecone](https://www.pinecone.io), [Milvus](https://milvus.io), etc.
[`Faiss`](https://github.com/facebookresearch/faiss) is a de facto library for vector search and is much more performant and reliable than `flechasdb`.

To be honest, I, Kikuo, reinvented this wheel just out of my curiosity:
- how IVFPQ indexing works[^3]
- how to utilize auto-vectorization by [Rust](https://www.rust-lang.org)'s optimizer[^4]
- how to write async [Rust](https://www.rust-lang.org)

However, I believe FlechasDB may be one of the cheapest solutions for small projects.
So why not consider **FlechasDB for your feasibility study** of vector databases?

[^3]: _Product Quantizers for k-NN Tutorial Part 2_ - <https://mccormickml.com/2017/10/22/product-quantizer-tutorial-part-2/>

[^4]: _Taking Advantage of Auto-Vectorization in Rust_ - <https://www.nickwilcox.com/blog/autovec/>