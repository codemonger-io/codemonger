+++
title = "Dealing with Mapbox hidden symbols (2. Resolving features)"
description = "Series: About development of a library that deals with Mapbox hidden symbols"
date = 2022-09-16
draft = true
[extra]
hashtags = ["Mapbox", "MapboxGLJS"]
thumbnail_name = "thumbnail.png"
+++

I have been working on a utility library for [Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/guides/), that deals with symbols hidden by another symbol on the screen.
This is the second blog post of the series that will walk you through the development of the library.

<!-- more -->

## Background

In the [last blog post of this series](../0009-mapbox-collision-boxes/), we left the following questions unanswered.

> - How can we obtain [`Tile`](../0009-mapbox-collision-boxes/#Tile)s and [`SymbolBucket`](../0009-mapbox-collision-boxes/#SymbolBucket)s?
> - How can we associate recalculated collision boxes with symbol [features](../0009-mapbox-collision-boxes#Feature)?

This blog post answers the above questions and also covers how to calculate the size of an icon, which I overlooked in the [last blog post](../0009-mapbox-collision-boxes/).

The library is available at [https://github.com/codemonger-io/mapbox-collision-boxes](https://github.com/codemonger-io/mapbox-collision-boxes).

I have analyzed [version 2.9.2](https://github.com/mapbox/mapbox-gl-js/tree/v2.9.2)\* of [Mapbox GL JS (`mapbox-gl-js`)](https://docs.mapbox.com/mapbox-gl-js/guides/).

\* The latest version was [2.10.0](https://github.com/mapbox/mapbox-gl-js/tree/v2.10.0) when I was writing this blog post, though I stick to version 2.9.2 for consistency.

## Obtaining Tiles and SymbolBuckets

In the [last blog post](../0009-mapbox-collision-boxes/), we have seen [`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart) plays a crucial role in determining which symbols are to appear on the screen.
If we examine how this method is invoked, we may figure out how to obtain [`Tile`](#Tile)s and [`SymbolBucket`](#SymbolBucket)s.

### Resolving SymbolBucket

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement) repeats calling [`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart) in [style/pauseable_placement.js#L50-L57](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L50-L57):
```ts
        while (this._currentPartIndex < bucketParts.length) {
            const bucketPart = bucketParts[this._currentPartIndex];
            placement.placeLayerBucketPart(bucketPart, this._seenCrossTileIDs, showCollisionBoxes, bucketPart.symbolInstanceStart === 0);
            this._currentPartIndex++;
            if (shouldPausePlacement()) {
                return true;
            }
        }
```

Each item in `bucketParts` that [`Placement#getBucketParts`](#Placement#getBucketParts) creates supplies a [`SymbolBucket`](#SymbolBucket) to be processed ([`BucketPart#parameters`](#BucketPart) &rightarrow; [`TileLayerParameters#bucket`](#TileLayerParameters)).
[`Placement#getBucketParts`](#Placement#getBucketParts) extracts a [`SymbolBucket`](#SymbolBucket) from the [`Tile`](#Tile) given as the third parameter of the method ([symbol/placement.js#L233-L234](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L233-L234)):
```ts
    getBucketParts(results: Array<BucketPart>, styleLayer: StyleLayer, tile: Tile, sortAcrossTiles: boolean) {
        const symbolBucket = ((tile.getBucket(styleLayer): any): SymbolBucket);
```

Thus, **if we have a [`StyleLayer`](#StyleLayer) and a [`Tile`](#Tile), we can also get a [`SymbolBucket`](#SymbolBucket)**.

### Resolving StyleLayer and Tile

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement) repeats calling [`Placement#getBucketParts`](#Placement#getBucketParts) in [style/pauseable_placement.js#L35-L43](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L35-L43):
```ts
        while (this._currentTileIndex < tiles.length) {
            const tile = tiles[this._currentTileIndex];
            placement.getBucketParts(bucketParts, styleLayer, tile, this._sortAcrossTiles);

            this._currentTileIndex++;
            if (shouldPausePlacement()) {
                return true;
            }
        }
```

`tiles` and `styleLayer` in the above snippet are the parameters given to [`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement).
[`PauseablePlacement#continuePlacement`](#PauseablePLacement#continuePlacement) repeats calling [`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement) in [style/pauseable_placement.js#L97-L123](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L97-L123) (`layerTiles[layer.source]` &rightarrow; `tiles`, and `layer` &rightarrow; `styleLayer`):
```ts
        while (this._currentPlacementIndex >= 0) {
            const layerId = order[this._currentPlacementIndex];
            const layer = layers[layerId];
            const placementZoom = this.placement.collisionIndex.transform.zoom;
            if (layer.type === 'symbol' &&
                (!layer.minzoom || layer.minzoom <= placementZoom) &&
                (!layer.maxzoom || layer.maxzoom > placementZoom)) {
                // ... truncated for legibility
                const pausePlacement = this._inProgressLayer.continuePlacement(layerTiles[layer.source], this.placement, this._showCollisionBoxes, layer, shouldPausePlacement);
            // ... truncated for legibility
        }
```

[`PausePlacement#continuePlacement`](#PauseablePlacement#continuePlacement) applies [`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement) only to "symbol" layers, as you can see the following condition at [style/pauseable_placement.js#L101](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L101):
```ts
            if (layer.type === 'symbol' &&
```

`order`, `layers`, and `layerTiles` in the above snippet are the parameters given to [`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement).
[`Style#_updatePlacement`](#Style#_updatePlacement) calls [`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement) at [style/style.js#L1740](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1740):
```ts
            this.pauseablePlacement.continuePlacement(this._order, this._layers, layerTiles);
```

[`Style#_updatePlacement`](#Style#_updatePlacement) prepares `layerTiles` in [style/style.js#L1696-L1712](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1696-L1712):
```ts
        const layerTiles = {};

        for (const layerID of this._order) {
            const styleLayer = this._layers[layerID];
            if (styleLayer.type !== 'symbol') continue;

            if (!layerTiles[styleLayer.source]) {
                const sourceCache = this._getLayerSourceCache(styleLayer);
                if (!sourceCache) continue;
                layerTiles[styleLayer.source] = sourceCache.getRenderableIds(true)
                    .map((id) => sourceCache.getTileByID(id))
                    .sort((a, b) => (b.tileID.overscaledZ - a.tileID.overscaledZ) || (a.tileID.isLessThan(b.tileID) ? -1 : 1));
            }
            // ... truncated for legibility
        }
```

So by mocking the above code, **we can obtain the [`StyleLayer`](#StyleLayer) and all the [`Tile`](#Tile)s corresponding to a given layer ID**.

### Listing Tiles and SymbolBuckets on a layer

To summarize, the outline of the code to list [`Tile`](#Tile)s and [`SymbolBucket`](#SymbolBucket)s on a specific layer will be similar to the following,
```ts
// suppose we have map: mapboxgl.Map, and layerId: string
const style = map.style;
const layer = style._layers[layerId];
const sourceCache = style._getLayerSourceCache(layer);
const layerTiles = sourceCache.getRenderableIds(true).map(id => sourceCache.getTileByID(id));
for (const tile of layerTiles) {
    const bucket = tile.getBucket(layer);
    // process tile and bucket ...
}
```

You can find complete code on [my GitHub repository](https://github.com/codemonger-io/mapbox-collision-boxes/blob/3379090e3945ed2850e1fc882be60a9e6b25eea2/src/index.ts#L57-L144) that includes additional checks.

## Resolving symbol features

In the [last blog post](../0009-mapbox-collision-boxes/), I briefly mentioned that [`FeatureIndex` is important for resolving symbol features](../0009-mapbox-collision-boxes/#FeatureIndex).
I have reasoned it by looking into [`Map#queryRenderedFeatures`](#Map#queryRenderedFeatures).

### Overview of how Map#queryRenderedFeatures works

[`Map#queryRenderedFeatures`](#Map#queryRenderedFeatures) calls [`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures) at [ui/map.js#L1719](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L1719):
```ts
        return this.style.queryRenderedFeatures(geometry, options, this.transform);
```

[`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures) calls [`queryRenderedSymbols`](#query_features.queryRenderedSymbols) in [style/style.js#L1384-L1391](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1384-L1391):
```ts
                queryRenderedSymbols(
                    this._layers,
                    this._serializedLayers,
                    this._getLayerSourceCache.bind(this),
                    queryGeometryStruct.screenGeometry,
                    params,
                    this.placement.collisionIndex,
                    this.placement.retainedQueryData)
```

[`queyrRenderedSymbols`](#query_features.queryRenderedSymbols) calls [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures) in [source/query_features.js#L95-L103](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L95-L103) to obtain features associated with symbols:
```ts
        const bucketSymbols = queryData.featureIndex.lookupSymbolFeatures(
                renderedSymbols[queryData.bucketInstanceId],
                serializedLayers,
                queryData.bucketIndex,
                queryData.sourceLayerIndex,
                params.filter,
                params.layers,
                params.availableImages,
                styleLayers);
```

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures) resolves and loads [GeoJSON](https://geojson.org) features associated with the first argument `renderedSymbols[queryData.bucketInstanceId]`.

So **we can resolve features by supplying proper parameters to [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)**.

### Preparing parameters for FeatureIndex#lookupSymbolFeatures

We have to provide the following parameters to reproduce the results of a [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures) call in [source/query_features.js#L95-L103](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L95-L103),
- [`queryData`](#Parameter:_queryData)
- [`serializedLayers`](#Parameter:_serializedLayers)
- [`params.filter`](#Parameter:_params.filter)
- [`params.layers`](#Parameter:_params.layers)
- [`params.availableImages`](#Parameter:_params.availableImages)
- [`styleLayers`](#Parameter:_styleLayers)

Please note that we do not have to reproduce the first parameter `renderedSymbols[queryData.bucketInstanceId]` because we need all the features in a [`SymbolBucket`](#SymbolBucket) rather than features intersecting a specific bounding box.
Please refer to the [section "Listing all the feature indices in a SymbolBucket"](#Listing_all_the_feature_indices_in_a_SymbolBucket) for how to substitute this parameter.

#### Parameter: queryData

`queryData` is bound to a [`RetainedQueryData`](#RetainedQueryData) in the loop in [source/query_features.js#L94-L132](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L94-L132):
```ts
    for (const queryData of bucketQueryData) {
        const bucketSymbols = queryData.featureIndex.lookupSymbolFeatures(
        // ... truncated for legibility
    }
```

`bucketQueryData` is an array of [`RetainedQueryData`](#RetainedQueryData)s and initialized in [source/query_features.js#L88-L92](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L88-L92):
```ts
    const bucketQueryData = [];
    for (const bucketInstanceId of Object.keys(renderedSymbols).map(Number)) {
        bucketQueryData.push(retainedQueryData[bucketInstanceId]);
    }
    bucketQueryData.sort(sortTilesIn);
```

`retainedQueryData` is [`Placement#retainedQueryData`](#Placement#retainedQueryData).

[`queryRenderedSymbols`](#query_features.queryRenderedSymbols) initializes `renderedSymbols` at [source/query_features.js#L87](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L87):
```ts
    const renderedSymbols = collisionIndex.queryRenderedSymbols(queryGeometry);
```

[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols) returns an object that maps a `bucketInstanceId` to indices of features in the [`SymbolBucket`](#SymbolBucket) associated with the `bucketInstanceId` and intersect a given bounding box.
We do not rely on [`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols), because it covers only visible symbols.

Since [we have a list of `SymbolBucket`s](#Listing_Tiles_and_SymbolBuckets_on_a_layer), **we can obtain the [`RetainedQueryData`](#RetainedQueryData) for each [`SymbolBucket#bucketInstanceId`](#SymbolBucket#bucketInstanceId) through [`Placement#retainedQueryData`](#Placement#retainedQueryData)**:
```ts
// suppose we have placement: Placement, and bucket: SymbolBucket
const queryData = placement.retainedQueryData[bucket.bucketInstanceId];
```

#### Parameter: serializedLayers

This parameter is [`Style#_serializedLayers`](#Style#_serializedLayers).

#### Parameter: params.filter

[`Map#queryRenderedFeatures`](#Map#queryRenderedFeatures) specifies an empty object to the `params` parameter of [`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures) by default (`options` &rightarrow; `params` in [ui/map.js#L1716-L1719](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L1716-L1719)):
```ts
        options = options || {};
        geometry = geometry || [[0, 0], [this.transform.width, this.transform.height]];

        return this.style.queryRenderedFeatures(geometry, options, this.transform);
```

So this parameter may be `undefined`.

#### Parameter: params.layers

Like [`params.filter`](#Parameter:_params.filter), this parameter may be `undefined` too.

#### Parameter: params.availableImages

[`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures) specifies [`Style#_availableImages`](#Style#_availableImages) to this parameter at [style/style.js#L1354](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1354):
```ts
        params.availableImages = this._availableImages;
```

#### Parameter: styleLayers

This parameter is [`Style#_layers`](#Style#_layers).

#### Listing all the feature indices in a SymbolBucket

What are feature indices that [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures) takes as its first argument (`symbolFeatureIndexes`)?
Although we do not use [`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols), seeing what it does should help us to figure out legitimate inputs to [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures).

I show you the conclusion first because the following analysis is intensive.
To list all the feature indices in a [`SymbolBucket`](#SymbolBucket), **we can take the `featureIndex` property from every item in [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances), or the `iconFeatureIndex` property from every item in [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)**:
```ts
// suppose we have bucket: SymbolBucket
// please note that SymbolBucket#symbolInstances is not an ordinary array
for (let i = 0; i < bucket.symbolInstances.length; ++i>) {
    const featureIndex = bucket.symbolInstances.get(i).featureIndex;
    // ... process the feature index
    // ... the collision box can be calculated with bucket.collisionArrays[i]
}
```

Associating the feature with the collision box is straightforward because `featureIndex` in the above code corresponds to `bucket.collisionArrays[i]`: [a parameter for collision box recalculation](../0009-mapbox-collision-boxes/#Parameter:_collisionBox).
You may skip the rest of this section to the [next section "Calculating the size of an icon"](#Calculating_the_size_of_an_icon).

##### What does CollisionIndex#queryRenderedSymbols do?

[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols) calls [`GridIndex#query`](#GridIndex#query) to list features intersecting a given bounding box in [symbol/collision_index.js#L360-L361](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L360-L361):
```ts
        const features = this.grid.query(minX, minY, maxX, maxY)
            .concat(this.ignoredGrid.query(minX, minY, maxX, maxY));
```

Then it processes every item of `features` in the loop in [symbol/collision_index.js#L366-L396](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L366-L396):
```ts
        for (const feature of features) {
            const featureKey = feature.key;
            // ... truncated for legibility
            result[featureKey.bucketInstanceId].push(featureKey.featureIndex);
        }
```

[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols) eventually returns `result` updated in the above code.
So what are `features` that [`GridIndex#query`](#GridIndex#query) returns?
[`GridIndex#query`](#GridIndex#query) returns an array of [`GridItem`](#GridItem)s intersecting a given bounding box.
[`GridIndex#query`](#GridIndex#query) constructs these [`GridItem`](#GridItem)s from the information of boxes and circles that [`GridIndex`](#GridIndex) stores along with feature keys in [`GridIndex#bboxes`](#GridIndex#bboxes), [`GridIndex#circles`](#GridIndex#circles), [`GridIndex#boxKeys`](#GridIndex#boxKeys), and [`GridIndex#circleKeys`](#GridIndex#circleKeys).
Thus, if we track down the origin of [`GridIndex#boxKeys`](#GridIndex#boxKeys) (let's forget about circles), we should be able to figure out how to get all the feature indices in a [`SymbolBucket`](#SymbolBucket).

##### The origin of GridIndex#boxKeys

[`GridIndex#insert`](#GridIndex#insert) pushes a `key` to [`GridIndex#boxKeys`](#GridIndex#boxKeys) at [symbol/grid_index.js#L73](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L73):
```ts
        this.boxKeys.push(key);
```

[`CollisionIndex#insertCollisionBox`](#CollisionIndex#insertCollisionBox) defined in [symbol/collision_index.js#L401-L406](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L401-L406) prepares a `key` and passes it to [`GridIndex#insert`](#GridIndex#insert):
```ts
    insertCollisionBox(collisionBox: Array<number>, ignorePlacement: boolean, bucketInstanceId: number, featureIndex: number, collisionGroupID: number) {
        const grid = ignorePlacement ? this.ignoredGrid : this.grid;

        const key = {bucketInstanceId, featureIndex, collisionGroupID};
        grid.insert(key, collisionBox[0], collisionBox[1], collisionBox[2], collisionBox[3]);
    }
```

Now our concern shifts to the origin of `featureIndex` that makes up the `key` in the above snippet.

##### The origin of featureIndex

In terms of symbol icons, [`Placement#placeLayerBucketPart.placeSymbol` (`placeSymbol`)](#Placement#placeLayerBucketPart.placeSymbol) calls [`CollisionIndex#insertCollisionBox`](#CollisionIndex#insertCollisionBox) in [symbol/placement.js#L748-L749](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L748-L749):
```ts
                this.collisionIndex.insertCollisionBox(placedIconBoxes.box, layout.get('icon-ignore-placement'),
                        bucket.bucketInstanceId, iconFeatureIndex, collisionGroup.ID);
```

[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol) sets `iconFeatureIndex` at [symbol/placement.js#L698](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L698):
```ts
                iconFeatureIndex = collisionArrays.iconFeatureIndex;
```

`collisionArrays` is a [`CollisionArrays`](#CollisionArrays) and the third argument of [`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol).
Then we pursue the origin of [`CollisionArrays`](#CollisionArrays).
[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart) calls [`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol) at [symbol/placement.js#L791](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L791) or [symbol/placement.js#L795](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L795):
```ts
                placeSymbol(bucket.symbolInstances.get(symbolIndex), symbolIndex, bucket.collisionArrays[symbolIndex]);
```

```ts
                placeSymbol(bucket.symbolInstances.get(i), i, bucket.collisionArrays[i]);
```

So `CollisionArrays` is an item of [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays).
[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart) calls [`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes) at [symbol/placement.js#L432](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L432) to initialize and fill [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays):
```ts
            bucket.deserializeCollisionBoxes(collisionBoxArray);
```

[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes) calls [`SymbolBucket#_deserializeCollisionBoxesForSymbol`](#SymbolBucket#_deserializeCollisionBoxesForSymbol) that actually sets [`CollisionArrays#iconFeatureIndex`](#CollisionArrays) in [data/bucket/symbol_bucket.js#L962-L968](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L962-L968):
```ts
        for (let k = iconStartIndex; k < iconEndIndex; k++) {
            // An icon can only have one box now, so this indexing is a bit vestigial...
            const box: CollisionBox = (collisionBoxArray.get(k): any);
            collisionArrays.iconBox = {x1: box.x1, y1: box.y1, x2: box.x2, y2: box.y2, padding: box.padding, projectedAnchorX: box.projectedAnchorX, projectedAnchorY: box.projectedAnchorY, projectedAnchorZ: box.projectedAnchorZ, tileAnchorX: box.tileAnchorX, tileAnchorY: box.tileAnchorY};
            collisionArrays.iconFeatureIndex = box.featureIndex;
            break; // Only one box allowed per instance
        }
```

So what is `collisionBoxArray` given to [`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes) at [symbol/placement.js#L432](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L432)?

##### The origin of collisionBoxArray

`collisionBoxArray` is included in [`TileLayerParameters`](#TileLayerParameters), and [`Placement#getBucketParts`](#Placement#getBucketParts) obtains it from [`Tile#collisionBoxArray`](#Tile#collisionBoxArray) at [symbol/placement.js#L242](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L242):
```ts
        const collisionBoxArray = tile.collisionBoxArray;
```

[`Tile#loadVectorData`](#Tile#loadVectorData) sets [`Tile#collisionBoxArray`](#Tile#collisionBoxArray) at [source/tile.js#L245](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L245):
```ts
        this.collisionBoxArray = data.collisionBoxArray;
```

[`Tile#loadVectorData`](#Tile#loadVectorData) is called at [source/geojson_source.js#L372](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/geojson_source.js#L372) and [source/vector_tile_source.js#L320](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_source.js#L320):
```ts
            tile.loadVectorData(data, this.map.painter, message === 'reloadTile');
```

```ts
            tile.loadVectorData(data, this.map.painter);
```

Above calls happen as a result of [`VectorTileWorkerSource#loadTile`](#VectorTileWorkerSource#loadTile) or [`VectorTileWorkerSource#reloadTile`](#VectorTileWorkerSource#reloadTile).
Both [`VectorTileWorkerSource#loadTile`](#VectorTileWorkerSource#loadTile) and [`VectorTileWorkerSource#reloadTile`](#VectorTileWorkerSource#reloadTile) call [`WorkerTile#parse`](#WorkerTile#parse) to parse the raw vector tile data.
[`WorkerTile#parse`](#WorkerTile#parse) outputs the parsed data in [source/worker_tile.js#L261-L272](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L261-L272):
```ts
                callback(null, {
                    buckets: values(buckets).filter(b => !b.isEmpty()),
                    featureIndex,
                    collisionBoxArray: this.collisionBoxArray,
                    glyphAtlasImage: glyphAtlas.image,
                    lineAtlas,
                    imageAtlas,
                    // Only used for benchmarking:
                    glyphMap: this.returnDependencies ? glyphMap : null,
                    iconMap: this.returnDependencies ? iconMap : null,
                    glyphPositions: this.returnDependencies ? glyphAtlas.positions : null
                });
```

`collisionBoxArray` (=[`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray)) in the above code eventually goes to [`Tile#collisionBoxArray`](#Tile#collisionBoxArray).
In terms of symbol icons, [`WorkerTile#parse`](#WorkerTile#parse) calls [`performSymbolLayout`](#symbol_layout.performSymbolLayout) in [source/worker_tile.js#L239-L248](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L239-L248) to update [`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray):
```ts
                        performSymbolLayout(bucket,
                            glyphMap,
                            glyphAtlas.positions,
                            iconMap,
                            imageAtlas.iconPositions,
                            this.showCollisionBoxes,
                            availableImages,
                            this.tileID.canonical,
                            this.tileZoom,
                            this.projection);
```

Please note that `bucket` is a [`SymbolBucket`](#SymbolBucket) in this context, and [`SymbolBucket#collisionBoxArray`](#SymbolBucket#collisionBoxArray) points to [`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray) as it is given to the bucket creation function in [source/worker_tile.js#L155-L168](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L155-L168):
```ts
                const bucket = buckets[layer.id] = layer.createBucket({
                    index: featureIndex.bucketLayerIDs.length,
                    layers: family,
                    zoom: this.zoom,
                    canonical: this.canonical,
                    pixelRatio: this.pixelRatio,
                    overscaling: this.overscaling,
                    collisionBoxArray: this.collisionBoxArray,
                    sourceLayerIndex,
                    sourceID: this.source,
                    enableTerrain: this.enableTerrain,
                    projection: this.projection.spec,
                    availableImages
                });
```

[`performSymbolLayout`](#symbol_layout.performSymbolLayout) lists features in `bucket` and calls [`addFeature`](#symbol_layout.addFeature) at [symbol/symbol_layout.js#L322](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L322):
```ts
            addFeature(bucket, feature, shapedTextOrientations, shapedIcon, imageMap, sizes, layoutTextSize, layoutIconSize, textOffset, isSDFIcon, availableImages, canonical, projection);
```

[`addFeature`](#symbol_layout.addFeature) (its internal function `addSymbolAtAnchor`) calls [`addSymbol`](#symbol_layout.addSymbol) in [symbol/symbol_layout.js#L438-L442](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L438-L442):
```ts
        addSymbol(bucket, anchor, globe, line, shapedTextOrientations, shapedIcon, imageMap, verticallyShapedIcon, bucket.layers[0],
            bucket.collisionBoxArray, feature.index, feature.sourceLayerIndex,
            bucket.index, textPadding, textAlongLine, textOffset,
            iconBoxScale, iconPadding, iconAlongLine, iconOffset,
            feature, sizes, isSDFIcon, availableImages, canonical);
```

In terms of symbol icons, [`addSymbol`](#symbol_layout.addSymbol) calls [`evaluateBoxCollisionFeature`](#symbol_layout.evaluateBoxCollisionFeature) at [symbol/symbol_layout.js#L731](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L731):
```ts
        iconBoxIndex = evaluateBoxCollisionFeature(collisionBoxArray, collisionFeatureAnchor, anchor, featureIndex, sourceLayerIndex, bucketIndex, shapedIcon, iconPadding, iconRotate);
```

[`evaluateBoxCollisionFeature`](#symbol_layout.evaluateBoxCollisionFeature) appends an item to `collisionBoxArray` at [symbol/symbol_layout.js#L634](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L634):
```ts
    collisionBoxArray.emplaceBack(projectedAnchor.x, projectedAnchor.y, projectedAnchor.z, tileAnchor.x, tileAnchor.y, x1, y1, x2, y2, padding, featureIndex, sourceLayerIndex, bucketIndex);
```

Please note that `collisionBoxArray` here is identical to [`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray).

##### SymbolBucket#symbolInstances vs SymbolBucket#collisionArrays

According to lines [symbol/placement.js#L791](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L791) and [symbol/placement.js#L795](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L795), **items of [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) match those of [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)**.
```ts
                placeSymbol(bucket.symbolInstances.get(symbolIndex), symbolIndex, bucket.collisionArrays[symbolIndex]);
```

```ts
                placeSymbol(bucket.symbolInstances.get(i), i, bucket.collisionArrays[i]);
```


And [`addSymbol`](#symbol_layout.addSymbol) also appends an item to [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) in [symbol/symbol_layout.js#L854-L884](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L854-L884):
```ts
    bucket.symbolInstances.emplaceBack(
        projectedAnchor.x,
        projectedAnchor.y,
        projectedAnchor.z,
        anchor.x,
        anchor.y,
        placedTextSymbolIndices.right >= 0 ? placedTextSymbolIndices.right : -1,
        placedTextSymbolIndices.center >= 0 ? placedTextSymbolIndices.center : -1,
        placedTextSymbolIndices.left >= 0 ? placedTextSymbolIndices.left : -1,
        placedTextSymbolIndices.vertical  >= 0 ? placedTextSymbolIndices.vertical : -1,
        placedIconSymbolIndex,
        verticalPlacedIconSymbolIndex,
        key,
        textBoxIndex !== undefined ? textBoxIndex : bucket.collisionBoxArray.length,
        textBoxIndex !== undefined ? textBoxIndex + 1 : bucket.collisionBoxArray.length,
        verticalTextBoxIndex !== undefined ? verticalTextBoxIndex : bucket.collisionBoxArray.length,
        verticalTextBoxIndex !== undefined ? verticalTextBoxIndex + 1 : bucket.collisionBoxArray.length,
        iconBoxIndex !== undefined ? iconBoxIndex : bucket.collisionBoxArray.length,
        iconBoxIndex !== undefined ? iconBoxIndex + 1 : bucket.collisionBoxArray.length,
        verticalIconBoxIndex ? verticalIconBoxIndex : bucket.collisionBoxArray.length,
        verticalIconBoxIndex ? verticalIconBoxIndex + 1 : bucket.collisionBoxArray.length,
        featureIndex,
        numHorizontalGlyphVertices,
        numVerticalGlyphVertices,
        numIconVertices,
        numVerticalIconVertices,
        useRuntimeCollisionCircles,
        0,
        textOffset0,
        textOffset1,
        collisionCircleDiameter);
```

Thus, matching items in [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) and [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays) have the **same feature index `featureIndex` and `iconFeatureIndex`** respectively.

##### What does FeatureIndex#lookupSymbolFeatures do?

What does [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures) actually do?
Does it make sense to specify feature indices (`featureIndex`) taken from [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) to the first parameter (`symbolFeatureIndexes`)?

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures) repeats calling [`FeatureIndex#loadMatchingFeature`](#FeatureIndex#loadMatchingFeature) in [data/feature_index.js#L257-L272](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L257-L272) (`symbolFeatureIndex` &rightarrow; `featureIndexData.featureIndex`):
```ts
        for (const symbolFeatureIndex of symbolFeatureIndexes) {
            this.loadMatchingFeature(
                result, {
                    bucketIndex,
                    sourceLayerIndex,
                    featureIndex: symbolFeatureIndex,
                    layoutVertexArrayOffset: 0
                },
                filter,
                filterLayerIDs,
                availableImages,
                styleLayers,
                serializedLayers
            );

        }
```

[`FeatureIndex#loadMatchingFeature`](#FeatureIndex#loadMatchingFeature) uses `featureIndex` to load the feature in [data/feature_index.js#L188-L190](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L188-L190):
```ts
        const sourceLayerName = this.sourceLayerCoder.decode(sourceLayerIndex);
        const sourceLayer = this.vtLayers[sourceLayerName];
        const feature = sourceLayer.feature(featureIndex);
```

On the other hand, [`performSymbolLayout`](#symbol_layout.performSymbolLayout) enumerates features in [`SymbolBucket#features`](#SymbolBucket#features) and passes them to [`addFeature`](#symbol_layout.addFeature) one by one in [symbol/symbol_layout.js#L197-L324](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L197-L324):
```ts
    for (const feature of bucket.features) {
        // ... truncated for legibility
        if (shapedText || shapedIcon) {
            addFeature(bucket, feature, shapedTextOrientations, shapedIcon, imageMap, sizes, layoutTextSize, layoutIconSize, textOffset, isSDFIcon, availableImages, canonical, projection);
        }
    }
```

So where does [`SymbolBucket#features`](#SymbolBucket#features) come from?
[`SymbolBucket#populate`](#SymbolBucket#populate) initializes and fills [`SymbolBucket#features`](#SymbolBucket#features) ([data/bucket/symbol_bucket.js#L475-L626](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L475-L626)):
```ts
    populate(features: Array<IndexedFeature>, options: PopulateParameters, canonical: CanonicalTileID, tileTransform: TileTransform) {
        // ... truncated for legibility
        this.features = [];
        // ... truncated for legibility
        for (const {feature, id, index, sourceLayerIndex} of features) {
            // ... truncated for legibility
            const symbolFeature: SymbolFeature = {
                id,
                text,
                icon,
                index,
                sourceLayerIndex,
                geometry: evaluationFeature.geometry,
                properties: feature.properties,
                type: vectorTileFeatureTypes[feature.type],
                sortKey
            };
            this.features.push(symbolFeature);
            // ... truncated for legibility
        }
        // ... truncated for legibility
    }
```

[`WorkerTile#parse`](#WorkerTile#parse) calls [`SymbolBucket#populate`](#SymbolBucket#populate) at [source/worker_tile.js#L171](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L171) just after creating a bucket:
```ts
                bucket.populate(features, options, this.tileID.canonical, this.tileTransform);
```

And [`WorkerTile#parse`](#WorkerTile#parse) prepares the first argument `features` in [source/worker_tile.js#L137-L142](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L137-L142):
```ts
            const features = [];
            for (let index = 0; index < sourceLayer.length; index++) {
                const feature = sourceLayer.feature(index);
                const id = featureIndex.getId(feature, sourceLayerId);
                features.push({feature, id, index, sourceLayerIndex});
            }
```

So `index` in the above code eventually becomes `featureIndex` in [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) along with the other related feature information.

Now we are sure that **`featureIndex` properties in [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) are consistent with the first parameter `symbolFeatureIndexes` of [`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)**.

## Calculating the size of an icon

In the [last blog post](../0009-mapbox-collision-boxes/), I concluded that [we could reproduce the `scale` parameter for icons](../0009-mapbox-collision-boxes/#Parameter:_scale).
However, I found that the function [`evaluateSizeForZoom`](#symbol_size.evaluateSizeForZoom) to calculate `partiallyEvaluatedIconSize` was not exported from `mapbox-gl-js` afterward.
So I had to clone [`evaluateSizeForZoom`](#symbol_size.evaluateSizeForZoom) from `mapbox-gl-js` to implement my library.

To make [`evaluateSizeForZoom`](#symbol_size.evaluateSizeForZoom) work, I also had to clone the following types and functions,
- [`SizeData`](#symbol_size.SizeData)
- [`InterpolatedSize`](#symbol_size.InterpolatedSize)
- [`InterpolationType`](#interpolate.InterpolationType)
- [`interpolationFactor`](#Interpolate.interpolationFactor)
- [`exponentialInterpolation`](#interpolate.exponentialInterpolation)
- [`interpolate`](#util.interpolate)
- [`clamp`](#util.clamp)

You can find these clones in [my GitHub repository](https://github.com/codemonger-io/mapbox-collision-boxes/blob/v0.1.0/src/private/symbol-size.ts).

## Wrap up

In this blog post, I have shown you how to list [`Tile`](#Tile)s and [`SymbolBucket`](#SymbolBucket)s and resolve symbol features.
The final loops will look like the following:
```ts
// suppose we have map: mapboxgl.Map, and layerId: string
const style = map.style;
const layer = style._layers[layerId];
const sourceCache = style._getLayerSourceCache(layer);
const layerTiles = sourceCache.getRenderableIds(true).map(id => sourceCache.getTileByID(id));
for (const tile of layerTiles) {
    const bucket = tile.getBucket(layer);
    for (let i = 0; i < bucket.symbolInstances.length; ++i>) {
        const featureIndex = bucket.symbolInstances.get(i).featureIndex;
        // ... recalculate the collision box and associate it with the feature
    }
}
```

I also have covered how to calculate the size of an icon.

While implementing the library, I faced a TypeScript-specific issue where internal types of `mapbox-gl-js` were not available for TypeScript.
In an upcoming blog post, I will share how I have addressed the issue.

Please also check out the library on [my GitHub repository](https://github.com/codemonger-io/mapbox-collision-boxes)!

## Appendix

### Source code reference

#### Map

Definition: [ui/map.js#L326-L3677](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L326-L3677)

##### Map#queryRenderedFeatures

Definition: [ui/map.js#L1697-L1720](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L1697-L1720)

This method implements the [`Map#queryRenderedFeatures` API](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#queryrenderedfeatures).

#### Style

Definition: [style/style.js#L135-L1860](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L135-L1860)

##### Style#_layers

Definition: [style/style.js#L148](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L148)
```ts
    _layers: {[_: string]: StyleLayer};
```

##### Style#_serializedLayers

Definition: [style/style.js#L152](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L152)
```ts
    _serializedLayers: {[_: string]: Object};
```

##### Style#_availableImages

Definition: [style/style.js#L168](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L168)
```ts
    _availableImages: Array<string>;
```

##### Style#queryRenderedFeatures

Definition: [style/style.js#L1330-L1396](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1330-L1396)

##### query_features.queryRenderedSymbols

Definition: [source/query_features.js#L79-L149](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L79-L149)

##### Style#_updatePlacement

Definition: [src/style/style.js#L1692-L1766](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1692-L1766)

This method calls [`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement).

#### Tile

Definition: [source/tile.js#L95-L799](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L95-L799)

##### Tile#tileID

Definition: [source/tile.js#L96](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L96)
```ts
    tileID: OverscaledTileID;
```

##### Tile#collisionBoxArray

Definition: [source/tile.js#L115](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L115)
```ts
    collisionBoxArray: ?CollisionBoxArray;
```

##### Tile#loadVectorData

Definition: [source/tile.js#L221-L290](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L221-L290)

#### VectorTileWorkerSource

Definition: [source/vector_tile_worker_source.js#L140-L309](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_worker_source.js#L140-L309)

##### VectorTileWorkerSource#loadTile

Definition: [source/vector_tile_worker_source.js#L177-L238](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_worker_source.js#L177-L238)

This method runs on a worker thread.

##### VectorTileWorkerSource#reloadTile

Definition: [source/vector_tile_worker_source.js#L244-L275](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_worker_source.js#L244-L275)

This method runs on a worker thread.

#### WorkerTile

Definition: [source/worker_tile.js#L36-L277](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L36-L277)

##### WorkerTile#collisionBoxArray

Definition: [source/worker_tile.js#L57](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L57)
```ts
    collisionBoxArray: CollisionBoxArray;
```

##### WorkerTile#parse

Definition: [source/worker_tile.js#L83-L276](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L83-L276)

##### symbol_layout.performSymbolLayout

Definition: [symbol/symbol_layout.js#L152-L329](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L152-L329)

[`WorkerTile#parse`](#WorkerTile#parse) calls this function in [source/worker_tile.js#L239-L248](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L239-L248):
```ts
                        performSymbolLayout(bucket,
                            glyphMap,
                            glyphAtlas.positions,
                            iconMap,
                            imageAtlas.iconPositions,
                            this.showCollisionBoxes,
                            availableImages,
                            this.tileID.canonical,
                            this.tileZoom,
                            this.projection);
```

##### symbol_layout.addFeature

Definition: [symbol/symbol_layout.js#L367-L500](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L367-L500)

In terms of symbol icons, [`symbol_layout.performSymbolLayout`](#symbol_layout.performSymbolLayout) calls this function at [symbol/symbol_layout.js#L322](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L322):
```ts
            addFeature(bucket, feature, shapedTextOrientations, shapedIcon, imageMap, sizes, layoutTextSize, layoutIconSize, textOffset, isSDFIcon, availableImages, canonical, projection);
```

##### symbol_layout.addSymbol

Definition: [symbol/symbol_layout.js#L657-L885](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L657-L885)

This function updates [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances) in [symbol/symbol_layout.js#L854-L884](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L854-L884):
```ts
    bucket.symbolInstances.emplaceBack(
        projectedAnchor.x,
        projectedAnchor.y,
        projectedAnchor.z,
        anchor.x,
        anchor.y,
        placedTextSymbolIndices.right >= 0 ? placedTextSymbolIndices.right : -1,
        placedTextSymbolIndices.center >= 0 ? placedTextSymbolIndices.center : -1,
        placedTextSymbolIndices.left >= 0 ? placedTextSymbolIndices.left : -1,
        placedTextSymbolIndices.vertical  >= 0 ? placedTextSymbolIndices.vertical : -1,
        placedIconSymbolIndex,
        verticalPlacedIconSymbolIndex,
        key,
        textBoxIndex !== undefined ? textBoxIndex : bucket.collisionBoxArray.length,
        textBoxIndex !== undefined ? textBoxIndex + 1 : bucket.collisionBoxArray.length,
        verticalTextBoxIndex !== undefined ? verticalTextBoxIndex : bucket.collisionBoxArray.length,
        verticalTextBoxIndex !== undefined ? verticalTextBoxIndex + 1 : bucket.collisionBoxArray.length,
        iconBoxIndex !== undefined ? iconBoxIndex : bucket.collisionBoxArray.length,
        iconBoxIndex !== undefined ? iconBoxIndex + 1 : bucket.collisionBoxArray.length,
        verticalIconBoxIndex ? verticalIconBoxIndex : bucket.collisionBoxArray.length,
        verticalIconBoxIndex ? verticalIconBoxIndex + 1 : bucket.collisionBoxArray.length,
        featureIndex,
        numHorizontalGlyphVertices,
        numVerticalGlyphVertices,
        numIconVertices,
        numVerticalIconVertices,
        useRuntimeCollisionCircles,
        0,
        textOffset0,
        textOffset1,
        collisionCircleDiameter);
```

An internal function `addSymbolAtAnchor` of [`symbol_layout.addFeature`](#symbol_layout.addFeature) calls this function in [symbol/symbol_layout.js#L438-L442](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L438-L442):
```ts
        addSymbol(bucket, anchor, globe, line, shapedTextOrientations, shapedIcon, imageMap, verticallyShapedIcon, bucket.layers[0],
            bucket.collisionBoxArray, feature.index, feature.sourceLayerIndex,
            bucket.index, textPadding, textAlongLine, textOffset,
            iconBoxScale, iconPadding, iconAlongLine, iconOffset,
            feature, sizes, isSDFIcon, availableImages, canonical);
```

##### symbol_layout.evaluateBoxCollisionFeature

Definition: [symbol/symbol_layout.js#L580-L637](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L580-L637)

This function updates `collisionBoxArray` at [symbol/symbol_layout.js#L634](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L634):
```ts
    collisionBoxArray.emplaceBack(projectedAnchor.x, projectedAnchor.y, projectedAnchor.z, tileAnchor.x, tileAnchor.y, x1, y1, x2, y2, padding, featureIndex, sourceLayerIndex, bucketIndex);
```

In terms of symbol icons, [`symbol_layout.addSymbol`](#symbol_layout.addSymbol) calls this function at [symbol/symbol_layout.js#L731](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L731):
```ts
        iconBoxIndex = evaluateBoxCollisionFeature(collisionBoxArray, collisionFeatureAnchor, anchor, featureIndex, sourceLayerIndex, bucketIndex, shapedIcon, iconPadding, iconRotate);
```

#### StyleLayer

Definition: [style/style_layer.js#L39-L323](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style_layer.js#L39-L323)

#### SymbolBucket

Definition: [data/bucket/symbol_bucket.js#L352-L1119](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L352-L1119)

##### SymbolBucket#bucketInstanceId

Definition: [data/bucket/symbol_bucket.js#L368](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L368)
```ts
    bucketInstanceId: number;
```

##### SymbolBucket#features

Definition: [data/bucket/symbol_bucket.js#L378](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L378)
```ts
    features: Array<SymbolFeature>;
```

##### SymbolBucket#collisionArrays

Definition: [data/bucket/symbol_bucket.js#L380](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L380)
```ts
    collisionArrays: Array<CollisionArrays>;
```

Items in this property match those in [`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances).

[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes) initializes and fills this property.

##### SymbolBucket#symbolInstances

Definition: [data/bucket/symbol_bucket.js#L379](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L379)
```ts
    symbolInstances: SymbolInstanceArray;
```

Items in this property match those in [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays).

##### SymbolBucket#collisionBoxArray

Definition: [data/bucket/symbol_bucket.js#L356](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L356)

##### SymbolBucket#populate

Definition: [data/bucket/symbol_bucket.js#L475-L626](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L475-L626)

##### SymbolBucket#deserializeCollisionBoxes

Definition: [data/bucket/symbol_bucket.js#L979-L995](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L979-L995)

This method initializes and fills [`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays).

##### SymbolBucket#_deserializeCollisionBoxesForSymbol

Definition: [data/bucket/symbol_bucket.js#L943-L977](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L943-L977)

#### FeatureIndex

Definition: [data/feature_index.js#L54-L312](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L54-L312)

##### FeatureIndex#lookupSymbolFeatures

Definition: [data/feature_index.js#L244-L274](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L244-L274)

This method calls [`FeatureIndex#loadMatchingFeature`](#FeatureIndex#loadMatchingFeature) in [data/feature_index.js#L258-L270](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L258-L270):
```ts
            this.loadMatchingFeature(
                result, {
                    bucketIndex,
                    sourceLayerIndex,
                    featureIndex: symbolFeatureIndex,
                    layoutVertexArrayOffset: 0
                },
                filter,
                filterLayerIDs,
                availableImages,
                styleLayers,
                serializedLayers
            );
```

##### FeatureIndex#loadMatchingFeature

Definition: [data/feature_index.js#L172-L240](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L172-L240)

This method loads the GeoJSON feature(s) of a symbol from the vector tile data.

#### CollisionIndex

Definition: [symbol/collision_index.js#L64-L465](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L64-L465)

##### CollisionIndex#queryRenderedSymbols

Definition: [symbol/collision_index.js#L341-L399](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L341-L399)

##### CollisionIndex#insertCollisionBox

Definition: [symbol/collision_index.js#L401-L406](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L401-L406)
```ts
    insertCollisionBox(collisionBox: Array<number>, ignorePlacement: boolean, bucketInstanceId: number, featureIndex: number, collisionGroupID: number) {
        const grid = ignorePlacement ? this.ignoredGrid : this.grid;

        const key = {bucketInstanceId, featureIndex, collisionGroupID};
        grid.insert(key, collisionBox[0], collisionBox[1], collisionBox[2], collisionBox[3]);
    }
```

#### GridIndex

Definition: [symbol/grid_index.js#L24-L341](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L24-L341)

##### GridIndex#bboxes

Definition: [symbol/grid_index.js#L29](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L29)
```ts
    bboxes: Array<number>;
```

Please see also [`GridIndex#boxKeys`](#GridIndex#boxKeys).

##### GridIndex#boxKeys

Definition: [symbol/grid_index.js#L26](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L26)
```ts
    boxKeys: Array<any>;
```

This property stores the feature key associated with the box at the same index in [`GridIndex#bboxes`](#GridIndex#bboxes).

[`GridIndex#insert`](#GridIndex#insert) updates this property.

##### GridIndex#circles

Definition: [symbol/grid_index.js#L30](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L30)
```ts
    circles: Array<number>;
```

Please see also [`GridIndex#circleKeys`](#GridIndex#circleKeys).

##### GridIndex#circleKeys

Definition: [symbol/grid_index.js#L25](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L25)
```ts
    circleKeys: Array<any>;
```

This property stores the feature key associated with the circle at the same index in [`GridIndex#circles`](#GridIndex#circles).

##### GridIndex#insert

Definition: [symbol/grid_index.js#L71-L78](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L71-L78)

This method pushes a given `key` to [`GridIndex#boxKeys`](#GridIndex#boxKeys) at [symbol/grid_index.js#L73](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L73):
```ts
        this.boxKeys.push(key);
```

##### GridIndex#query

Definition: [symbol/grid_index.js#L163-L165](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L163-L165)
```ts
    query(x1: number, y1: number, x2: number, y2: number, predicate?: any): Array<GridItem> {
        return (this._query(x1, y1, x2, y2, false, predicate): any);
    }
```

Please see also [`GridIndex#_query`](#GridIndex#_query).

##### GridIndex#_query

Definition: [symbol/grid_index.js#L98-L137](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L98-L137)

This method calls [`GridIndex#_forEachCell`](#GridIndex#_forEachCell) at [symbol/grid_index.js#L134](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L134):
```ts
            this._forEachCell(x1, y1, x2, y2, this._queryCell, result, queryArgs, predicate);
```

##### GridIndex#_forEachCell

Definition: [symbol/grid_index.js#L291-L303](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L291-L303)
```ts
    _forEachCell(x1: number, y1: number, x2: number, y2: number, fn: any, arg1: any, arg2?: any, predicate?: any) {
        const cx1 = this._convertToXCellCoord(x1);
        const cy1 = this._convertToYCellCoord(y1);
        const cx2 = this._convertToXCellCoord(x2);
        const cy2 = this._convertToYCellCoord(y2);

        for (let x = cx1; x <= cx2; x++) {
            for (let y = cy1; y <= cy2; y++) {
                const cellIndex = this.xCellCount * y + x;
                if (fn.call(this, x1, y1, x2, y2, cellIndex, arg1, arg2, predicate)) return;
            }
        }
    }
```

This method applies `fn` to every cell intersecting a given bounding box.

In the context of [`GridIndex#query`](#GridIndex#query), `fn` is [`GridIndex#_queryCell`](#GridIndex#_queryCell).

##### GridIndex#_queryCell

Definition: [symbol/grid_index.js#L175-L240](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L175-L240)

This method collects boxes and circles in a specified cell intersecting a given bounding box.

#### GridItem

Definition: [symbol/grid_index.js#L3-L9](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L3-L9)
```ts
type GridItem = {
    key: any,
    x1: number,
    y1: number,
    x2: number,
    y2: number
};
```

#### Placement

Definition: [symbol/placement.js#L192-L1184](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L192-L1184)

##### Placement#retainedQueryData

Definition: [symbol/placement.js#L205](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L205)
```ts
    retainedQueryData: {[_: number]: RetainedQueryData};
```

Please see also [`RetainedQueryData`](#RetainedQueryData).

##### Placement#getBucketParts

Definition: [symbol/placement.js#L233-L333](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L233-L333)

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement) calls this method at [style/pauseable_placement.js#L37](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L37):
```ts
            placement.getBucketParts(bucketParts, styleLayer, tile, this._sortAcrossTiles);
```

Please see also the [corresponding section in the previous blog post](../0009-mapbox-collision-boxes/#Placement#getBucketParts).

##### Placement#placeLayerBucketPart

Definition: [symbol/placement.js#L386-L808](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L386-L808)

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement) calls this method at [style/pauseable_placement.js#L52](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L52):
```ts
            placement.placeLayerBucketPart(bucketPart, this._seenCrossTileIDs, showCollisionBoxes, bucketPart.symbolInstanceStart === 0);
```

Please see also the [corresponding section in the previous blog post](../0009-mapbox-collision-boxes/#Placement#placeLayerBucketPart).

##### Placement#placeLayerBucketPart.placeSymbol

Definition: [symbol/placement.js#L439-L784](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L439-L784)

#### RetainedQueryData

Definition: [symbol/placement.js#L87-L105](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L87-L105)
```ts
export class RetainedQueryData {
    bucketInstanceId: number;
    featureIndex: FeatureIndex;
    sourceLayerIndex: number;
    bucketIndex: number;
    tileID: OverscaledTileID;
    featureSortOrder: ?Array<number>
    // ... truncated for legibility
}
```

#### BucketPart

Definition: [symbol/placement.js#L183-L188](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L183-L188)
```ts
export type BucketPart = {
    sortKey?: number | void,
    symbolInstanceStart: number,
    symbolInstanceEnd: number,
    parameters: TileLayerParameters
};
```

Please see also [`TileLayerParameters`](#TileLayerParameters).

#### TileLayerParameters

Definition: [symbol/placement.js#L169-L181](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L169-L181)
```ts
type TileLayerParameters = {
    bucket: SymbolBucket,
    layout: any,
    posMatrix: Mat4,
    textLabelPlaneMatrix: Mat4,
    labelToScreenMatrix: ?Mat4,
    scale: number,
    textPixelRatio: number,
    holdingForFade: boolean,
    collisionBoxArray: ?CollisionBoxArray,
    partiallyEvaluatedTextSize: any,
    collisionGroup: any
};
```

#### PauseablePlacement

Definition: [style/pauseable_placement.js#L62-L132](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L62-L132)

##### PauseablePlacement#continuePlacement

Definition: [style/pauseable_placement.js#L89-L126](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L89-L126)

This method calls [`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement).

[`Style#_updatePlacement`](#Style#_updatePlacement) calls this method at [style/style.js#L1740](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1740):
```ts
            this.pauseablePlacement.continuePlacement(this._order, this._layers, layerTiles);
```

#### LayerPlacement

Definition: [style/pauseable_placement.js#L15-L60](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L15-L60)

##### LayerPlacement#continuePlacement

Definition: [style/pauseable_placement.js#L32-L59](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L32-L59)

This method calls
- [`Placement#getBucketParts`](#Placement#getBucketParts)
- [`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)

[`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement) calls this method at [style/pauseable_placement.js#L109](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L109):
```ts
                const pausePlacement = this._inProgressLayer.continuePlacement(layerTiles[layer.source], this.placement, this._showCollisionBoxes, layer, shouldPausePlacement);
```

#### symbol_size.SizeData

Definition: [symbol/symbol_size.js#L15-L32](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_size.js#L15-L32)
```ts
export type SizeData = {
    kind: 'constant',
    layoutSize: number
} | {
    kind: 'source'
} | {
    kind: 'camera',
    minZoom: number,
    maxZoom: number,
    minSize: number,
    maxSize: number,
    interpolationType: ?InterpolationType
} | {
    kind: 'composite',
    minZoom: number,
    maxZoom: number,
    interpolationType: ?InterpolationType
};
```

#### symbol_size.InterpolatedSize

Definition: [symbol/symbol_size.js#L34-L37](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_size.js#L34-L37)
```ts
export type InterpolatedSize = {|
    uSize: number,
    uSizeT: number
|};
```

#### symbol_size.evaluateSizeForZoom

Definition: [symbol/symbol_size.js#L92-L118](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_size.js#L92-L118)

#### interpolate.InterpolationType

Definition: [style-spec/expression/definitions/interpolate.js#L17-L20](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/expression/definitions/interpolate.js#L17-L20)
```ts
export type InterpolationType =
    { name: 'linear' } |
    { name: 'exponential', base: number } |
    { name: 'cubic-bezier', controlPoints: [number, number, number, number] };
```

#### Interpolate.interpolationFactor

Definition: [style-spec/expression/definitions/interpolate.js#L45-L57](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/expression/definitions/interpolate.js#L45-L57)

#### interpolate.exponentialInterpolation

Definition: [style-spec/expression/definitions/interpolate.js#L255-L266](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/expression/definitions/interpolate.js#L255-L266)

#### util.interpolate

Definition: [style-spec/util/interpolate.js#L5-L7](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/util/interpolate.js#L5-L7)
```ts
export function number(a: number, b: number, t: number): number {
    return (a * (1 - t)) + (b * t);
}
```

#### util.clamp

Definition: [util/util.js#L211-L213](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/util/util.js#L211-L213)
```ts
export function clamp(n: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, n));
}
```

#### SymbolInstanceArray

Definition: [data/array_types.js#L1188-L1198](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/array_types.js#L1188-L1198)

Each item in this array is [`SymbolInstanceStruct`](#SymbolInstanceStruct).

#### SymbolInstanceStruct

Definition: [data/array_types.js#L1146-L1179](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/array_types.js#L1146-L1179)

#### CollisionArrays

Definition: [data/bucket/symbol_bucket.js#L90-L99](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L90-L99)
```ts
export type CollisionArrays = {
    textBox?: SingleCollisionBox;
    verticalTextBox?: SingleCollisionBox;
    iconBox?: SingleCollisionBox;
    verticalIconBox?: SingleCollisionBox;
    textFeatureIndex?: number;
    verticalTextFeatureIndex?: number;
    iconFeatureIndex?: number;
    verticalIconFeatureIndex?: number;
};
```