+++
title = "Handling binary responses with a custom AWS Lambda runtime in Rust"
date = 2022-10-14
draft = false
hashtags = ["AWS", "Lambda", "Rust"]
+++

This blog post shares how I handle binary responses with a custom AWS Lambda runtime written in Rust.

<!-- more -->

## Background

We can make any dynamic responses from an [Amazon API Gateway REST API (REST API)](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-rest-api.html) with a [Lambda integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-integrations.html).
I decided to implement an [AWS Lambda (Lambda)](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html) function that produces dynamic binary data for my REST API.
As I have been learning [Rust](https://www.rust-lang.org), I have decided to implement a Lambda function with Rust\*.
Please note this blog post deals with a Lambda function for [Lambda non-proxy integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started-lambda-non-proxy-integration.html).

\* I believe that [Python](https://www.python.org) and [Node.js (JavaScript)](https://nodejs.org/en/) are not very good at processing binary data.
[Go](https://go.dev) may be a good choice for binary data handling, and AWS provides an [official Lambda runtime for Go](https://docs.aws.amazon.com/lambda/latest/dg/lambda-golang.html), though I want to learn Rust anyway.

## Lambda runtime for Rust

Although [AWS is seemingly enthusiastic about Rust](https://aws.amazon.com/blogs/opensource/why-aws-loves-rust-and-how-wed-like-to-help/), they provide [no official Lambda runtime for Rust](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html).
So we have to implement a [custom Lambda runtime](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-custom.html) in Rust or create a [container](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-package.html#gettingstarted-package-images).
If you look around for how to implement a Lambda function in Rust, you will likely come across the library [`aws-lambda-rust-runtime`](https://github.com/awslabs/aws-lambda-rust-runtime).
It does the heavy lifting for us when we implement a custom Lambda runtime in Rust.

Thanks to `aws-lambda-rust-runtime`, implementing a Lambda function in Rust is fairly easy.
There is a [simple tutorial on the GitHub repository of `aws-lambda-rust-runtime`](https://github.com/awslabs/aws-lambda-rust-runtime#getting-started).
I do not repeat it here but show an excerpt from the tutorial below, the actual Rust code you have to write:
```rust
use lambda_runtime::{service_fn, LambdaEvent, Error};
use serde_json::{json, Value};

#[tokio::main]
async fn main() -> Result<(), Error> {
    let func = service_fn(func);
    lambda_runtime::run(func).await?;
    Ok(())
}

async fn func(event: LambdaEvent<Value>) -> Result<Value, Error> {
    let (event, _context) = event.into_parts();
    let first_name = event["firstName"].as_str().unwrap_or("world");

    Ok(json!({ "message": format!("Hello, {}!", first_name) }))
}
```

### Dealing with binary data with aws-lambda-rust-runtime

`aws-lambda-rust-runtime` works very well as long as our output is [JSON](https://www.json.org/json-en.html)-encodable.

#### Returning Vec\<u8\> does not work

The [`run`](https://docs.rs/lambda_runtime/0.6.1/lambda_runtime/fn.run.html) function of the core module [`lambda_runtime`](https://docs.rs/lambda_runtime/0.6.1/lambda_runtime/index.html) accepts any service that returns a value implementing [`serde::Serialize`](https://docs.rs/serde/1.0.145/serde/trait.Serialize.html).
To output binary, I first thought my service function could simply return a `Vec<u8>` and tried to do so.
It turned out that `lambda_runtime` produced a JSON representation of an array instead of a [BLOB](https://en.wikipedia.org/wiki/Binary_large_object).
For instance, when I provided `lambda_runtime` with a `Vec<u8>` of `[0x61, 0x62, 0x63]`, I got
```json
[
  97,
  98,
  99
]
```
instead of `abc`\*.

\* `0x61`, `0x62`, and `0x63` represent `'a'`, `'b'`, and `'c'` on [ASCII](https://en.wikipedia.org/wiki/ASCII) respectively.

#### How does lambda_runtime handle results?

[`lambda_runtime::run`](https://github.com/awslabs/aws-lambda-rust-runtime/tree/main/lambda-runtime) converts any service function outputs into JSON, and this behavior is hard-coded in [lambda-runtime/src/requests.rs#L77-L85](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/requests.rs#L77-L85) where you can find `serde_json::to_vec(&self.body)`:
```rust
    fn into_req(self) -> Result<Request<Body>, Error> {
        let uri = format!("/2018-06-01/runtime/invocation/{}/response", self.request_id);
        let uri = Uri::from_str(&uri)?;
        let body = serde_json::to_vec(&self.body)?;
        let body = Body::from(body);

        let req = build_request().method(Method::POST).uri(uri).body(body)?;
        Ok(req)
    }
```

#### Any solution?

There was a [discussion about binary responses](https://github.com/awslabs/aws-lambda-rust-runtime/issues/69) on GitHub, which suggested using the [`lambda_http`](https://docs.rs/lambda_http/0.6.1/lambda_http/) module.
As far as I looked into it, `lambda_http` was designed for [Lambda proxy integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html).
So it could not simply produce a plain BLOB.

Then I came up with the following two workarounds,
1. Embed a [Base64](https://en.wikipedia.org/wiki/Base64)-encoded binary as a field value in a JSON object, extract it with a [mapping template for integration responses](https://docs.aws.amazon.com/apigateway/latest/developerguide/models-mappings.html#models-mappings-mappings), and apply [`CONVERT_TO_BINARY`](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-payload-encodings-workflow.html).
2. Tweak `lambda_runtime` so that it can handle a raw binary output.

The easier pathway should have been the first one.
However, I took the second one\* as it was an **opportunity to practice Rust**.

\* Later, I found my efforts were unnecessary.
You can jump to the [Section "Simpler solution"](#Simpler_solution) for a much simpler and easier way.

### Tweak for lambda_runtime

While the primary goal of the tweak was to support binary responses, I set a secondary one: make sure that existing programs that output a JSON-serializable object continue to work (backward compatibility).

This section introduces
1. [`IntoRequest` trait that is the outlet of function responses](#IntoRequest_trait)
2. [My workaround: introduction of `IntoBytes` and `RawBytes`](#Introduction_of_IntoBytes_and_RawBytes)

#### IntoRequest trait

`IntoRequest` ([lambda-runtime/src/requests.rs#L8-L10](https://github.com/awslabs/aws-lambda-rust-runtime/blob/b1c5dfd1a09c62f77e91c03f278f73b7e2ecfd30/lambda-runtime/src/requests.rs#L8-L10)) serializes every successful output from your service function and creates a request object to send to the [invocation response endpoint for the Lambda function](https://docs.aws.amazon.com/lambda/latest/dg/runtimes-api.html#runtimes-api-response)\*:
```rust
pub(crate) trait IntoRequest {
    fn into_req(self) -> Result<Request<Body>, Error>;
}
```

While `IntoRequest` plays a key role in `lambda_runtime`, you do not directly implement it\*2 for your function outputs.
There is a "bridge" between a function result and `IntoRequest`: `EventCompletionRequest<T>` where `T` is the type of your function output ([lambda-runtime/src/requests.rs#L68-L71](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/requests.rs#L68-L71)):
```rust
pub(crate) struct EventCompletionRequest<'a, T> {
    pub(crate) request_id: &'a str,
    pub(crate) body: T,
}
```

`lambda_runtime` wraps your function output with `EventCompletionRequest<T>` and processes it as `IntoRequest` ([lambda-runtime/src/lib.rs#L164-L168](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/lib.rs#L164-L168)):
```rust
                                EventCompletionRequest {
                                    request_id,
                                    body: response,
                                }
                                .into_req()
```

`IntoRequest` is implemented for `EventCompletionRequest<T>` such that `T` is `serde::Serialize` ([lambda-runtime/src/requests.rs#L73-L75](https://github.com/awslabs/aws-lambda-rust-runtime/blob/bd8896a21d8bef6f1f085ec48660a5b727669dc5/lambda-runtime/src/requests.rs#L73-L75)):
```rust
impl<'a, T> IntoRequest for EventCompletionRequest<'a, T>
where
    T: for<'serialize> Serialize,
```

That is why a `Serialize` that your service function outputs becomes a JSON object.

\* The word "Request" in the name `IntoRequest` while representing a function response may confuse you, but "Request" here stands for a request sent to an invocation response endpoint for a custom Lambda runtime.

\*2 `IntoRequest` is not exported anyway.

#### Introduction of IntoBytes and RawBytes

We have to somehow generalize the [`serde_json::to_vec` call in `IntoRequest::into_req`](#How_does_lambda_runtime_handle_results?).
We can consider it a conversion from a service output to a byte sequence (`Vec<u8>`).
So how about to specialize `IntoRequest` for `EventCompletionRequest<'a, Vec<u8>>`?
Unfortunately, this does not work because we cannot make `lambda_runtime::run` accept both `Serialize` and `Vec<u8>` as a service output.
```rust
pub async fn run<A, B, F>(handler: F) -> Result<(), Error>
where
    F: Service<LambdaEvent<A>>,
    F::Future: Future<Output = Result<B, F::Error>>,
    F::Error: fmt::Debug + fmt::Display,
    A: for<'de> Deserialize<'de>,
    B: Serialize | Vec<u8>, // Error: we cannot do something like this!
```

We need a new type that can be translated into either `Serialize` or a raw byte sequence.
Well, how about to introduce a new trait `IntoBytes` and specialize `IntoRequest` for `EventCompletionRequest<'a, IntoBytes>` instead of `EventCompletionRequest<'a, Serialize>` as follows?
```rust
pub trait IntoBytes {
    fn to_bytes(self) -> Result<Vec<u8>, Error>;
}

impl<'a, T> IntoRequest for EventCompletionRequest<'a, T>
where
    T: IntoBytes,
{
    fn into_req(self) -> Result<Request<Body>, Error> {
        let uri = format!("/2018-06-01/runtime/invocation/{}/response", self.request_id);
        let uri = Uri::from_str(&uri)?;
        let body = self.body.to_bytes()?;
        let body = Body::from(body);

        let req = build_request().method(Method::POST).uri(uri).body(body)?;
        Ok(req)
    }
}
```

Then, we have to rewrite the signature of `lambda_runtime::run`.
How about the following?
```rust
pub async fn run<A, B, F>(handler: F) -> Result<(), Error>
where
    F: Service<LambdaEvent<A>>,
    F::Future: Future<Output = Result<B, F::Error>>,
    F::Error: fmt::Debug + fmt::Display,
    A: for<'de> Deserialize<'de>,
    B: IntoBytes, // does not accept Serialize
```

If we do like the above, we will lose the backward compatibility; i.e., the service function can no longer simply return a `Serialize`.
To work around this, I have introduced another struct `IntoBytesBridge`:
```rust
pub struct IntoBytesBridge<T>(pub T);
```

`IntoBytes` is specialized for `IntoBytesBridge<Serialize>` as follows:
```rust
impl<T> IntoBytes for IntoBytesBridge<T>
where
    T: Serialize,
{
    fn to_bytes(self) -> Result<Vec<u8>, Error> {
        let bytes = serde_json::to_vec(&self.0)?;
        Ok(bytes)
    }
}
```

Thanks to `IntoBytesBridge`, we can rewrite the signature of `lambda_runtime::run` into:
```rust
pub async fn run<A, B, F>(handler: F) -> Result<(), Error>
where
    F: Service<LambdaEvent<A>>,
    F::Future: Future<Output = Result<B, F::Error>>,
    F::Error: fmt::Debug + fmt::Display,
    A: for<'de> Deserialize<'de>,
    IntoBytesBridge<B>: IntoBytes, // requires that IntoBytes is implemented for IntoBytesBridge<B>
```

It works with `Serialize` because `IntoByte` is implemented for `IntoBytesBridge<Serialize>` (see above).

Now we introduce a new data type `RawBytes` to tell our intention to output a raw byte sequence and specialize `IntoBytes` for `IntoBytesBridge<RawBytes>`.
```rust
pub struct RawBytes(pub Vec<u8>);

impl IntoBytes for IntoBytesBridge<RawBytes> {
    fn to_bytes(self) -> Result<Vec<u8>, Error> {
        Ok(self.0.0)
    }
}
```

Then we can output a raw byte sequence by wrapping the output from our service function with `RawBytes`.
The following example outputs a raw string `abc` rather than a JSON array `[97, 98, 99]`:
```rust
use lambda_runtime::{service_fn, LambdaEvent, Error, RawBytes};
use serde_json::Value;

#[tokio::main]
async fn main() -> Result<(), Error> {
    let func = service_fn(func);
    lambda_runtime::run(func).await?;
    Ok(())
}

async fn func(event: LambdaEvent<Value>) -> Result<RawBytes, Error> {
    Ok(RawBytes(vec![0x61, 0x62, 0x63]))
}
```

### Limitation of the Lambda integration?

A strange thing happened when I tried the [new feature developed in the previous section](#Introduction_of_IntoBytes_and_RawBytes) to implement my REST API.
My API outputted byte sequences slightly different from what I had returned as service responses.
I realized that my API occasionally produced a triple `(0xE, 0xBF, 0xBD)`.
After looking into the problem, it turned out the triple substituted a byte supposed to have its most significant bit `1`; in other words, bitwise AND with `0x80` was not zero.
The triple `(0xEF, 0xBF, 0xBD)` was indeed a UTF-8 representation of a [replacement character (`U+FFFD`)](https://www.compart.com/en/unicode/U+FFFD), and it meant **someone expecting a valid UTF-8 sequence had replaced unwanted bytes in my API output**.
So who was responsible for that?
The endpoint for Lambda invocation responses?
Or the [Lambda integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-integrations.html) of the Amazon API Gateway?
Or even the Rust dependencies?

When I directly invoked my Lambda function with the AWS CLI command [`aws lambda invoke`](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/lambda/invoke.html), I got an exact byte sequence as I expected.
So the Lambda invocation response endpoint and Rust dependencies were in the clear, and the **Lambda integration was the cause**.
I knew Lambda proxy integration expects JSON, a subset of a valid UTF-8 sequence, as the output.
But I had not realized **Lambda non-proxy integration also expects a UTF-8 sequence as the output**\*.

\* I have not confirmed this in a legitimate source yet.

#### Workaround

My workaround was to encode the service output into Base64 and specify `CONVERT_TO_BINARY` to `contentHandling`.
But one question arises; if we have to encode a binary into a Base64 text, have we really needed the extension of `lambda_runtime`?
This question leads to a much simpler solution described in the [next section](#Simpler_solution).

### Simpler solution

In the [last section](#Limitation_of_the_Lambda_integration?), we learned Lambda non-proxy integration does not allow a service to output an arbitrary byte sequence.
Thus, we have to Base64-encode our service outputs anyway.
It means that the benefits of tweaking `lambda_runtime` are half-lost.
In the [Section "Any solutions?"](#Any_solution?), I have suggested another solution that requires no tweaks on `lambda_runtime`.

> 1. Embed a [Base64](https://en.wikipedia.org/wiki/Base64)-encoded binary as a field value in a JSON object, extract it with a [mapping template for integration responses](https://docs.aws.amazon.com/apigateway/latest/developerguide/models-mappings.html#models-mappings-mappings), and apply [`CONVERT_TO_BINARY`](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-payload-encodings-workflow.html).

However, I feel it is a bit awkward because we have to write a mapping template only to extract a field value.
So, how about **directly outputting a Base64-encoded [`String`](https://doc.rust-lang.org/std/string/struct.String.html) and serializing it as JSON**?
Since `Serialize` is implemented for `String`, our service functions can output it without any tweaks:
```rust
use lambda_runtime::{service_fn, LambdaEvent, Error};
use serde_json::Value;

#[tokio::main]
async fn main() -> Result<(), Error> {
    let func = service_fn(func);
    lambda_runtime::run(func).await?;
    Ok(())
}

async fn func(event: LambdaEvent<Value>) -> Result<String, Error> {
    Ok(base64::encode([0x61, 0x62, 0x63]))
}
```

I initially thought it did not work because the output would be enclosed by extra double quotations (`"`) and become an invalid Base64 text.

But, **it turned out to work**!

When I got an output via `aws lambda invoke`, it actually included enclosing double quotations.
But Lambda integration somehow recognized how to deal with it and correctly decoded an intended Base64 text.

## Wrap up

In this blog post, we have seen [`aws-lambda-rust-runtime`](https://github.com/awslabs/aws-lambda-rust-runtime) helps us to implement a custom Lambda runtime in Rust.
Then I have shown you my tweaks on `aws-lambda-rust-runtime` to handle binary data.
However, we have found that simply returning a Base64-encoded `String` is the easiest way to deal with binary outputs with Lambda integration for Amazon API Gateway.

While it turned out not very useful, you can find my tweaks on `aws-lambda-rust-runtime` on [my GitHub fork](https://github.com/codemonger-io/aws-lambda-rust-runtime/tree/binary-support).

## Appendix

### Building a Rust Lambda runtime with CDK

I found [`rust.aws-cdk-lambda`](https://github.com/rnag/rust.aws-cdk-lambda/tree/main) helpful when we build a Lambda function in Rust with the [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html).