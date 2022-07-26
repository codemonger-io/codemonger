+++
title = "AWS APIGateway × OpenAPI (2. Proxy)"
description = "This is a series of blog posts that will walk you through the development of a library that integrates an OpenAPI definition with a REST API definition on the CDK"
date = 2022-07-26
draft = false
[extra]
hashtags = ["AWS", "CDK", "APIGateway", "OpenAPI", "Proxy"]
thumbnail_name = "thumbnail.png"
+++

I have been working on a [library](https://github.com/codemonger-io/cdk-rest-api-with-spec) that integrates an [OpenAPI](https://www.openapis.org) definition with a REST API definition on the [CDK](https://docs.aws.amazon.com/cdk/v2/guide/home.html).
This is the second blog post of the series that will walk you through the development of the library.

<!-- more -->

## Background

In the [first blog post of this series](../0006-open-api-and-cdk/), we left the following challenge,

> How can we achieve compatibility with [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)?
> - If we write a subclass or a wrapper for [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html), we cannot directly manipulate what [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html) instantiates as subsidiaries; e.g., [Resource](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html)s, [Method](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Method.html)s.
>   How can we extend the subsidiary entities?
> - If we do not reuse [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html), it will be really tough to achieve compatibility.

Since it is too hard not to reuse [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html), I am going to write a subclass for it.

## Defining interfaces

Before extending the [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html) API, let us define minimal interfaces.
Please note that I have excerpted and modified the interfaces and code shown in the following sections from my library for simplicity.
You can find their full definitions in [my GitHub repository](https://github.com/codemonger-io/cdk-rest-api-with-spec).

### IRestApiWithSpec

`IRestApiWithSpec` is the extension of [`IRestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IRestApi.html).

```ts
interface IRestApiWithSpec extends IRestApi {
  readonly root: IResourceWithSpec;
  // ... other more properties
}
```

### IResourceWithSpec

`IResourceWithSpec` is the extension of [`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html)\*.

```ts
interface IResourceWithSpec extends Resource {
  addResource(pathPart: string, options?: ResourceOptionsWithSpec): IResourceWithSpec;
  addMethod(httpMethod: string, target?: Integration, options?: MethodOptionsWithSpec): Method;
  // ... other more properties
}
```

\* To correctly extend [`IResource.addResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html#addwbrresourcepathpart-options), `IResourceWithSpec` has to implement [`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html) rather than [`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html).
On the other hand, `IRestApiWithSpec.root` has to implement [`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html) instead of [`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html), so the definition `root: IResourceWithSpec` in `IRestApiWithSpec` is too specific.
However, it should not matter because the public interface of [`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html), and [`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html) are the same as far as I know.

### ResourceOptionsWithSpec

`ResourceOptionsWithSpec` is the extension of [`ResourceOptions`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.ResourceOptions.html).

```ts
interface ResourceOptionsWithSpec extends ResourceOptions {
  defaultMethodOptions?: MethodOptionsWithSpec;
}
```

### MethodOptionsWithSpec

`MethodOptionsWithSpec` is the extension of [`MethodOptions`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.MethodOptions.html).

```ts
interface MethodOptionsWithSpec extends MethodOptions {
  requestParameterSchemas?: { [key: string]: BaseParameterObject };
  // ... other more properties
}
```

`BasePrameterObject` is borrowed from an external library [OpenApi3-TS](https://github.com/metadevpro/openapi3-ts)[\[1\]](#Reference).

I initially intended to override the definition of [`MethodOptions.requestParameters`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.MethodOptions.html#requestparameters) like the following (see the [example in the last blog post](../0006-open-api-and-cdk/#OpenAPI_and_REST_API_side_by_side)),

```ts
requestParameters?: { [key: string]: boolean | BaseParameterObject };
```

But this attempt has failed because it would make `MethodOptionsWithSpec` unassignable to [`MethodOptions`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.MethodOptions.html).
So I have introduced a new property `requestParameterSchemas` as a workaround.

## Extending RestApi

Extending [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html) is straightforward.
Just use the language feature (`extends`) and override properties of [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html).

```ts
class RestApiWithSpec extends RestApi implements IRestApiWithSpec {
  readonly root: IResourceWithSpec;

  constructor(scope: Construct, id: string, props: RestApiWithSpecProps) {
    super(scope, id, props);
    // how do we implement `root`?
  }
}
```

I omit the details of `RestApiWithSpecProps` for simplicity.
Please refer to [my GitHub repository](https://github.com/codemonger-io/cdk-rest-api-with-spec) if you are interested in it.

Here, the question is how to implement `root`.
Wrapping `root` of the superclass ([`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)) sounds good.
So how do we wrap it?
Write a wrapper class that just forwards most requests to `root` of [`RestApi`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.RestApi.html)?
That will involve a lot of boilerplate.
Then [`Proxy`](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Proxy) should better meet our needs.

### Proxying root

Writing a `Proxy` for `root` is fairly easy.
All you have to do is implement the [`get`](https://devdocs.io/javascript/global_objects/proxy/proxy/get) function of a handler object.

```ts
// root: IResource
const rootWithSpec: IResourceWithSpec = new Proxy(root, {
  get: (target, prop, receiver) => {
    switch (prop) {
      case 'addResource':
        return (pathPart, options) => {
          // ... create and wrap again a new resource
        };
      case 'addMethod':
        return (httpMethod, target, options) => {
          // ... process options
        };
      default:
        return Reflect.get(target, prop, receiver);
          // TypeScript complained if I did `Reflect.get(...arguments)`
    }
  }
});
```

Unfortunately, [TypeScript](https://www.typescriptlang.org) does not recognize the proxied object as `IResourceWithSpec` in the above code and ends up with an error.
Because the [default TypeScript definition of the `Proxy` constructor](https://microsoft.github.io/PowerBI-JavaScript/interfaces/_node_modules_typedoc_node_modules_typescript_lib_lib_es2015_proxy_d_.proxyconstructor.html#constructor) is something like the following,

```ts
declare global {
  interface ProxyConstructor {
    new <T extends object>(target: T, handler: ProxyHandler<T>): T; // Proxy of T is still T
  }
}
```

To address this issue, we can extend the definition of the `Proxy` constructor so that it can produce a type different from that of `target`.
[This StackOverflow post](https://stackoverflow.com/a/50603826)[\[2\]](#Reference) exactly answers it.
So adding the following declaration solves the TypeScript error.

```ts
declare global {
  interface ProxyConstructor {
    new <T extends object, U extends object>(target: T, handler: ProxyHandler<T>): U; // Proxy of T may be U
  }
}
```

## Extending Resource

Every time we create a [`Resource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.Resource.html), we have to wrap it with a `Proxy` as described in the section ["Proxying root."](#Proxying_root)
So I have introduced a factory method `augmentResource` that can wrap any existing [`IResource`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.IResource.html) with the features of `IResourceWithSpec`.
This factory method can also be applied to `root`.

```ts
class ResourceWithSpec {
  static augmentResource(restApi: IRestApiWithSpec, resource: IResource, parent?: IResourceWithSpec): IResourceWithSpec {
    const resourceWithSpec: IResourceWithSpec = new Proxy(resource, {
      get: (target, prop, receiver) => {
        switch (prop) {
          case 'addResource':
            return (pathPart, options) => {
              return augmentResource(
                restApi,
                resource.addResource(pathPart, options),
                resourceWithSpec
              );
            };
          // ... handle other properties
        }
      }
    });
    return resourceWithSpec;
  }
}
```

The above code has been simplified; you can find the actual definition in [my GitHub repository](https://github.com/codemonger-io/cdk-rest-api-with-spec).

## Wrap-up

In this blog post, I have introduced `Proxy` to facilitate the extension of the CDK API.
I also have shown a trick to circumvent a TypeScript error about `Proxy`.
In an upcoming blog post, we will tackle the challenge of when we should output an OpenAPI definition file.

## Reference

1. [OpenApi3-TS](https://github.com/metadevpro/openapi3-ts)

   TypeScript bindings of the OpenAPI 3 specification itself.
2. [How to use Proxy<T> with a different type than T as argument? - Answer](https://stackoverflow.com/questions/50602903/how-to-use-proxyt-with-a-different-type-than-t-as-argument/50603826#50603826)