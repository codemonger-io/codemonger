+++
title = "Dealing with Mapbox hidden symbols (3. Augmenting types)"
description = "Series: About development of a library that deals with Mapbox hidden symbols"
date = 2022-09-23
draft = true
[extra]
hashtags = ["Mapbox", "MapboxGLJS", "TypeScript"]
thumbnail_name = "thumbnail.png"
+++

I have been working on a utility library for [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/guides/), that deals with symbols hidden by another symbol on the screen.
This is the third blog post of the series that will walk you through the development of the library.

<!-- more -->

## Background

In the last two blog posts of this series, I showed,
- [How to recalculate collision boxes of symbols](../0009-mapbox-collision-boxes/)
- [How to associate symbol features with recalculated collision boxes](../0010-mapbox-collision-boxes/)

In this blog post, we tackle a remaining issue that some types in [Mapbox GL JS (`mapbox-gl-js`)](https://docs.mapbox.com/mapbox-gl-js/guides/) were not available for [TypeScript](https://www.typescriptlang.org).

The library (`mapbox-collision-boxes`) is available on [my GitHub repository](https://github.com/codemonger-io/mapbox-collision-boxes).

## TypeScript?

TypeScript is a variant of [JavaScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript), which provides powerful typing features.
Please refer to the [official website of TypeScript](https://www.typescriptlang.org) for more details.
[This page](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html)[\[1\]](#Reference) can help understand the difference between TypeScript and JavaScript.
I have chosen TypeScript for the implementation language of `mapbox-collision-boxes`.

## Is mapbox-gl-js typed?

Yes, but `mapbox-gl-js` is typed with [Flow](https://flow.org) which is another flavor of JavaScript for typing.
Unfortunately, type definitions on Flow are not compatible with TypeScript.
So we need external type definitions of `mapbox-gl-js` for TypeScript.
Thanks to the hard work of contributors from the TypeScript community, these types are available as [`@types/mapbox-gl`](https://www.npmjs.com/package/@types/mapbox-gl)\*.

\* The latest version of `@types/mapbox-gl` was 2.7.5 when I was writing this blog post, and it was based on `mapbox-gl-js` version 2.7 while the then latest version was 2.10.
However, I have not faced any issues related to the version difference so far.

## What @types/mapbox-gl missing

`@types/mapbox-gl` does not expose some properties and types on which `mapbox-collision-boxes` depends.
For instance, the class `Map` ([@types/mapbox-gl/index.d.ts#L201-L602](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/482d94eee7b27c478034e188bbeb64e2f995bbd8/types/mapbox-gl/index.d.ts#L201-L602)) omits the property `style: Style`.
`@types/mapbox-gl` neither defines the class `Bucket` nor `SymbolBucket`.

### How can we circumvent it?

One may be inclined to give up type checks, but this should be a last resort.

We can use [module augmentation](https://www.typescriptlang.org/docs/handbook/declaration-merging.html#module-augmentation) to enhance existing type definitions of `mapbox-gl-js`.
"Module augmentation" is a slightly advanced TypeScript feature.
Please refer to the [TypeScript documentation](https://www.typescriptlang.org/docs/handbook/declaration-merging.html#module-augmentation) for more details.

For instance, the following snippet adds the property `style: Style` to the class `Map`:
```ts
import { Map, Style } from 'mapbox-gl';

declare module 'mapbox-gl' {
    interface Map {
        style: Style;
    }
}
```

After the above declaration, you can access `Map#style` in a type-safe manner.

For `Bucket` and `SymbolBucket`, we can just add interfaces for them since they are simply missing in `@types/mapbox-gl`:
```ts
export interface Bucket {}

export interface SymbolBucket extends Bucket {
  bucketInstanceId: number;
  // ... other properties
}
```

I also have introduced a utility function that tests if a given `Bucket` is a `SymbolBucket` ([mapbox-collision-boxes/private/mapbox-types.ts#L232-L234](https://github.com/codemonger-io/mapbox-collision-boxes/blob/b48e39231ef328815ef9ad276fd230de2ccfcaab/src/private/mapbox-types.ts#L232-L234)), which uses another TypeScript feature ["type predicates"](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#using-type-predicates).
```ts
export function isSymbolBucket(bucket: Bucket): bucket is SymbolBucket {
  return (bucket as SymbolBucket).symbolInstances !== undefined;
}
```

You can find minimum definitions necessary to implement `mapbox-collision-boxes` on [my GitHub repository](https://github.com/codemonger-io/mapbox-collision-boxes/blob/db7812e7c874df1f59ea6264e027ac0eeeb95875/src/private/mapbox-types.ts).

## Wrap-up

In this short blog post, I have shown how to extend existing types in `mapbox-gl-js` (`@types/mapbox-gl`) while introducing the following TypeScript features,
- [Module augmentation](https://www.typescriptlang.org/docs/handbook/declaration-merging.html#module-augmentation)
- [Type predicates](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#using-type-predicates)

`mapbox-collision-boxes` is available on [my GitHub repository](https://github.com/codemonger-io/mapbox-collision-boxes).

## Reference

1. [_TypeScript for the New Programmer_ - https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html](https://www.typescriptlang.org/docs/handbook/typescript-from-scratch.html)