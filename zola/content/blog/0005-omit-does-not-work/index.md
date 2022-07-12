+++
title = "When Omit<Type, Keys> breaks (my expectation)"
description = "This blog post will share with you what I have learned from reasoning why Omit has not worked."
date = 2022-07-12
draft = false
[extra]
hashtags = ["TypeScript"]
thumbnail_name = "thumbnail.png"
+++

I have scratched my head when [`Omit<Type, Keys>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#omittype-keys) in [TypeScript](https://www.typescriptlang.org) has not worked as I intended.
This blog post will share with you what I have learned from reasoning why `Omit` has not worked.

<!-- more -->

## What is Omit<Type, Keys>?

[`Omit<Types, Keys>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#omittype-keys) is a utility type provided by [TypeScript](https://www.typescriptlang.org).
It defines a new type that has all the properties of `Type` but omits properties specified to `Keys`.
We can see it as a type operator that removes `Keys` from `Type`.

Suppose you have the following definitions,

```ts
interface IdentifiedPerson {
  id: number;
  name: string;
}
type Person = Omit<IdentifiedPerson, 'id'>;
```

The derived type `Person` will be equivalent to

```ts
interface Person {
  name: string;
}
```

## When Omit<Type, Keys> breaks

Suppose I have the types similar to the following defined outside of my project.

```ts
interface IElement {
  [extensionName: string]: any;
}

interface InfoObject extends IElement {
  title: string;
  version: string;
  description?: string;
}
```

I want to make the `title` property of `InfoObject` optional.
So I derive a new type from `InfoObject` by using `Omit`.

```ts
type InfoObjectOmittingTitle = Omit<InfoObject, 'title'> & {
  title?: string; // it is now optional
};
```

Now I can omit the `title` property to initialize an instance of `InfoObjectOmittingTitle`.

```ts
const info: InfoObject = {
  version: '0.0.1',
}; // ERROR! error TS2741: Property 'title' is missing in type '{ version: string; }' but required in type 'InfoObject'.

const info2: InfoObjectOmittingTitle = {
  version: '0.0.1',
}; // WORKS!
```

But a **strange thing happens**.
The `version` property also has become optional contrary to my expectation.

```ts
const info3: InfoObjectOmittingTitle = {}; // WORKS!?
```

Additionally, even the following can be compiled!

```ts
const info4: InfoObjectOmittingTitle = {
  version: 123,
}; // WORKS!?
```

## How Omit<Type, Keys> works

You can find the definition of `Omit` itself [here](https://github.com/microsoft/TypeScript/blob/28dc248e5c500c7be9a8c3a7341d303e026b023f/src/lib/es5.d.ts#L1574) in the source code of TypeScript.
The following is an excerpt of the code.

```ts
type Omit<T, K extends keyof any> = Pick<T, Exclude<keyof T, K>>;
```

`Omit` is actually a composition of other utility types [`Pick`](https://www.typescriptlang.org/docs/handbook/utility-types.html#picktype-keys) and [`Exclude`](https://www.typescriptlang.org/docs/handbook/utility-types.html#excludeuniontype-excludedmembers).

### What is Pick<Type, Keys>?

`Pick` is the opposite of `Omit`.
It defines a new type that has properties of `Type` included in `Keys`.
The definition of `Pick` itself is [here](https://github.com/microsoft/TypeScript/blob/28dc248e5c500c7be9a8c3a7341d303e026b023f/src/lib/es5.d.ts#L1550-L1552).
The following is an excerpt of the code.

```ts
type Pick<T, K extends keyof T> = {
    [P in K]: T[P];
};
```

### What is Exclude<UnionType, ExcludedMembers>?

`Exclude` defines a new union type that includes all the members of `UnionType` but excludes members in `ExcludedMembers`.
The definition of `Exclude` itself is [here](https://github.com/microsoft/TypeScript/blob/28dc248e5c500c7be9a8c3a7341d303e026b023f/src/lib/es5.d.ts#L1564).
The following is an excerpt of the code.

```ts
type Exclude<T, U> = T extends U ? never : T;
```

### What is going on in my failed attempt?

We are going to dissect the following part in the [previous section](#When_Omit<Type,_Keys>_breaks).

```ts
Omit<InfoObject, 'title'>
```

This will be

```ts
Pick<InfoObject, Exclude<keyof InfoObject, 'title'>>
```

`keyof InfoObject` is equivalent to the following union type.
Please refer to [this page](https://www.typescriptlang.org/docs/handbook/2/keyof-types.html) for how `keyof` works.

```ts
'title' | 'version' | 'description' | string;
```

`string` comes from the [index signature](https://www.typescriptlang.org/docs/handbook/2/objects.html#index-signatures) `[extensionName: string]: any` of the base interface `IElement`.

So the `Omit` part will further become

```ts
Pick<InfoObject, Exclude<'title' | 'version' | 'description' | string, 'title'>>
```

The following table shows the evaluation of `Exclude<T, 'title'>` for each member `T` of `'title' | 'version' | 'description' | string`.
We have to understand ["Distributive Conditional Types"](https://www.typescriptlang.org/docs/handbook/2/conditional-types.html#distributive-conditional-types) to see what happens to the part `Exclude<'title' | 'version' | 'description' | string, 'title'>`.

| `T` | `T extends 'title' ?` | `Exclude<T, 'title'>` |
|-|-|-|
| `'title'` | `true` | `never` |
| `'version'` | `false` | `'version'` |
| `'description'` | `false` | `'description'` |
| `string` | `false` | `string` |

Thus the `Exclude<'title' | 'version' | 'description' | string, 'title'>` will be

```ts
'version' | 'description' | string
```

And the `Omit` part will become

```ts
Pick<InfoObject, 'version' | 'description' | string>
```

What happens to the final `Pick`?
Here what I can do is **only guessing** from the consequence.
I think the most inclusive member `string` would win at `K extends keyof T` or `P in K` during the expansion of `Pick<T, K>` and suppress other specific members `'version'` and `'description'`.

```ts
{
  [p: string]: InfoObject[string];
}
```

And the `Pick` would end up with

```ts
{
  [extensionsName: string]: any;
}
```

However, I have not confirmed any legitimate literature that backs up my guess yet.

## Workaround

According to [this article](https://javascript.plainenglish.io/how-to-make-certain-properties-optional-in-typescript-9b4f8e85c5de), the following can be a workaround.

```ts
type InfoObjectWithOptionalTitle = Partial<InfoObject> & Pick<InfoObject, 'version'>;
```

[`Partial<Type>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#partialtype) defines a new type that has every property of `Type` as optional.
Intersection with `Pick<InfoObject, 'version'>` keeps the `version` property mandatory.

The major drawback is that it requires an exhaustive list of mandatory properties.

## Conclusion

[`Omit<Type, Keys>`](https://www.typescriptlang.org/docs/handbook/utility-types.html#omittype-keys) may not work if `Type` contains an [index signature](https://www.typescriptlang.org/docs/handbook/2/objects.html#index-signatures).
I have not confirmed in the TypeScript specification why this happens.
But I have found a [workaround](#Workaround).

## Reference

- [_How to Make Certain Properties Optional in TypeScript_](https://javascript.plainenglish.io/how-to-make-certain-properties-optional-in-typescript-9b4f8e85c5de)