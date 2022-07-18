+++
title = "AWS APIGateway × OpenAPI (1. Motivation)"
description = "This is a series of blog posts that will walk you through the development of a library that integrates an OpenAPI definition with a REST API definition on the CDK"
date = 2022-07-18
draft = false
[extra]
hashtags = ["AWS", "CDK", "APIGateway", "OpenAPI"]
thumbnail_name = "thumbnail.png"
+++

I have been working on a [library](https://github.com/codemonger-io/cdk-rest-api-with-spec) that integrates an [OpenAPI](https://www.openapis.org) definition with a REST API definition on the [CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html).
This is the first blog post of the series that will walk you through the development of the library.

<!-- more -->

## Motivation

Recently, I have been urged to write the OpenAPI definitions of my REST APIs on [Amazon API Gateway (API Gateway)](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html) that I have described with the [Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html).
As far as I know, there are two options to deal with the OpenAPI definition of a REST API on API Gateway.
1. [Exporting the OpenAPI definition from an existing REST API](#1._Exporting_the_OpenAPI_definition_from_an_existing_REST_API)
2. [Creating a REST API by importing an existing OpenAPI definition](#2._Creating_a_REST_API_by_importing_an_existing_OpenAPI_definition)

### 1. Exporting the OpenAPI definition from an existing REST API

On API Gateway, you can [export the OpenAPI definition from an existing REST API](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-export-api.html).
You have to [add separate documentation to your REST API](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-documenting-api.html) to export a meaningful OpenAPI definition.
There is an [L1 construct `CfnDocumentationPart`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.CfnDocumentationPart.html) on the CDK that allows you to document an API entity; see the example in ["OpenAPI and REST API side by side."](#OpenAPI_and_REST_API_side_by_side)
However, separation of the documentation and an actual API entity definition may be disadvantageous to you to keep the documentation up-to-date.
I think it would be nice if we could describe a REST API entity and its documentation side by side.

### 2. Creating a REST API by importing an existing OpenAPI definition

If you already have an OpenAPI definition and AWS-specific extensions in it, you can [build a REST API on API Gateway by importing it](https://docs.aws.amazon.com/apigateway/latest/developerguide/import-edge-optimized-api.html).
The CDK also provides a [dedicated construct `SpecRestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.SpecRestApi.html) to import an existing OpenAPI definition.
However, if I build a REST API from scratch I prefer the CDK building blocks, e.g., [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html) and subsidiaries, for the following reasons,
- Simply, I am familiar with them.
- The CDK building blocks may reduce tedious [IAM](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html) configurations and security vulnerabilities.
- Writing AWS-specific extensions in an OpenAPI definition may be tiresome.\*
- Writing a plain OpenAPI definition may involve a lot of repetition.\*

\* As I have never tried this option, I might be wrong.

### Third option

Thus, I want a third option that enables me to **write a REST API and the OpenAPI definition side by side** on top of the CDK building blocks.

## Design goals

[This blog post](https://dev.to/aws-builders/openapi-specs-from-cdk-stack-without-deploying-first-4g83?utm_source=dormosheio&utm_campaign=dormosheio)[\[1\]](#Reference) introduced a similar work and inspired me.
But my goal is not to utilize the power of [TypeScript](https://www.typescriptlang.org).
I have two goals,

1. [OpenAPI and REST API side by side](#OpenAPI_and_REST_API_side_by_side)
2. [Compatibility with RestApi](#Compatibility_with_RestApi)

### OpenAPI and REST API side by side

With my library, we will be able to describe the OpenAPI definition beside a REST API entity rather than in a separate documentation resource.

For instance, we will be able to do

```ts
const pet = api.root.addResource('pet');
const findByStatus = pet.addResource('findByStatus');
findByStatus.addMethod(
  'GET',
  new MockIntegration({
    // ... integration settings
  }),
  {
    operationName: 'findPetsByStatus',
    summary: 'Finds Pets by status',
    description: 'Multiple status values can be provided with comma separated strings',
    requestParameters: {
      'method.request.querystring.status': {
        description: 'Status values that need to be considered to filter',
        required: false,
        explode: true,
        schema: {
          type: 'string',
          enum: ['available', 'pending', 'sold'],
          default: 'available'
        }
      }
    },
    methodResponses: [
      {
        statusCode: '200',
        description: 'successful operation',
        responseModel: {
          'application/json': petArrayModel
        }
      }
    ]
  }
);
```

rather than

```ts
const pet = api.root.addResource('pet');
const findByStatus = pet.addResource('findByStatus');
findByStatus.addMethod(
  'GET',
  new MockIntegration({
    // ... integration settings
  }),
  {
    operationName: 'findPetsByStatus',
    requestParameters: {
      'method.request.querystring.status': true
    },
    methodResponses: [
      {
        statusCode: '200',
        responseModel: {
          'application/json': petArrayModel
        }
      }
    ]
  }
);
new CfnDocumentationPart(this, 'FindPetsByStatusDocPart', {
  location: {
    type: 'METHOD',
    path: '/pet/findByStatus',
    method: 'GET'
  },
  properties: {
    summary: 'Finds Pets by status',
    description: 'Multiple status values can be provided with comma separated strings'
  },
  restApiId: api.restApiId
});
new CfnDocumentationPart(this, 'FindPetsByStatusParamsDocPart', {
  location: {
    type: 'QUERY_PARAMETER',
    path: '/pet/findByStatus',
    method: 'GET',
    name: 'status'
  },
  properties: {
    description: 'Status values that need to be considered to filter',
    required: false,
    explode: true,
    schema: {
        type: 'string',
        enum: ['available', 'pending', 'sold'],
        default: 'available'
    }
  },
  restApiId: api.restApiId
});
new CfnDocumentationPart(this, 'FindPetsByStatus200ResponseDocPart', {
  location: {
    type: 'RESPONSE',
    path: '/pet/findByStatus',
    method: 'GET',
    statusCode: '200'
  },
  properties: {
    description: 'successful operation'
  }
});
```

### Compatibility with RestApi

With my library, we will be able to have an experience similar to what we have with [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html).

All you have to do will be just instantiate an extended construct `RestApiWithSpec` instead of [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html).

```ts
const api = new RestApiWithSpec(this, 'example-api', {
  description: 'Example of RestApiWithSpec',
  openApiInfo: {
    version: '1.0.0'
  },
  openApiOutputPath: 'openapi.json',
  deploy: true,
  deployOptions: {
    stageName: 'staging',
    description: 'Default stage'
  }
});
```

After you get an instance of `RestApiWithSpec`, you will be able to use it exactly like [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html).
Of course, it will also provide extensions to describe the OpenAPI definition; see the example in ["OpenAPI and REST API side by side."](#OpenAPI_and_REST_API_side_by_side)

## Challenges

There are some challenges.
- How can we achieve compatibility with [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)?
    - If we write a subclass or a wrapper for [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html), we cannot directly manipulate what [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html) instantiates as subsidiaries; e.g, [Resource](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)s, [Method](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Method.html)s.
      How can we extend the subsidiary entities?
    - If we do not reuse [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html), it will be really tough to achieve compatibility.
- When should the library actually output the OpenAPI definition file?
    - Should a user explicitly call a function to save?
    - Or, can we magically save the OpenAPI definition file like the CDK does to the [CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) template?
- Can we support [Lambda proxies](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html)?

We are going to tackle these challenges in subsequent blog posts.

## Wrap-up

What I have been developing is available on my [GitHub repository](https://github.com/codemonger-io/cdk-rest-api-with-spec).
In an upcoming blog post, we will tackle the challenge of how we can achieve compatibility with [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html).

## Reference

1. [_OpenAPI Specs from CDK Stack WITHOUT Deploying First_](https://dev.to/aws-builders/openapi-specs-from-cdk-stack-without-deploying-first-4g83?utm_source=dormosheio&utm_campaign=dormosheio)