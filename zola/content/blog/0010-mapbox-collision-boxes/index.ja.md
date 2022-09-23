+++
title = "Mapboxの非表示シンボルを扱う (2. Featureの解決編)"
description = "シリーズ:Mapboxで非表示になっているシンボルを扱うライブラリの開発について"
date = 2022-09-16
updated = 2022-09-23
draft = false
[extra]
hashtags = ["Mapbox", "MapboxGLJS"]
thumbnail_name = "thumbnail.png"
+++

[Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/guides/)の画面上で別のシンボルに隠されたシンボルを扱うユーティリティライブラリを開発中です。
これはライブラリの開発過程を紹介するシリーズのブログ投稿第2弾です。

<!-- more -->

## 背景

[このシリーズの前回の投稿](../0009-mapbox-collision-boxes/)で、以下の疑問が残りました。

> - [`Tile`](../0009-mapbox-collision-boxes/#Tile)と[`SymbolBucket`](../0009-mapbox-collision-boxes/#SymbolBucket)はどうやって取得するのか?
> - 再計算した衝突ボックスとシンボルの[Feature](../0009-mapbox-collision-boxes/#Feature)をどうやって対応づけるのか?

このブログ投稿では上記の疑問に答え、[前回のブログ投稿](../0009-mapbox-collision-boxes/)で見落としていたアイコンの大きさを計算する方法についてもカバーします。

このライブラリは[https://github.com/codemonger-io/mapbox-collision-boxes](https://github.com/codemonger-io/mapbox-collision-boxes)で手に入ります。

[Mapbox GL JS (`mapbox-gl-js`)](https://docs.mapbox.com/mapbox-gl-js/guides/)の[バージョン2.9.2](https://github.com/mapbox/mapbox-gl-js/tree/v2.9.2)\*を分析しました。

\* このブログを書いている段階で最新バージョンは[2.10.0](https://github.com/mapbox/mapbox-gl-js/tree/v2.10.0)でしたが、一貫性を保つためにバージョン2.9.2で続けます。

## TileとSymbolBucketを取得する

[前回のブログ投稿](../0009-mapbox-collision-boxes/)で、どのシンボルを画面に表示するかを決定するのに[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)が重要な役割を果たしていることがわかりました。
このメソッドがどのように呼び出されているかを調べれば、[`Tile`](#Tile)と[`SymbolBucket`](#SymbolBucket)をどうやって取得するかがわかるかもしれません。

### SymbolBucketを解決する

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)は[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)を繰り返し呼び出します([style/pauseable_placement.js#L50-L57](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L50-L57))。
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

[`Placement#getBucketParts`](#Placement#getBucketParts)によって作成される`bucketParts`の各要素は処理の対象となる[`SymbolBucket`](#SymbolBucket)を提供します([`BucketPart#parameters`](#BucketPart) &rightarrow; [`TileLayerParameters#bucket`](#TileLayerParameters))。
[`Placement#getBucketParts`](#Placement#getBucketParts)は当該メソッド3番目の引数の[`Tile`](#Tile)から[`SymbolBucket`](#SymbolBucket)を取り出します([symbol/placement.js#L233-L234](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L233-L234))。
```ts
    getBucketParts(results: Array<BucketPart>, styleLayer: StyleLayer, tile: Tile, sortAcrossTiles: boolean) {
        const symbolBucket = ((tile.getBucket(styleLayer): any): SymbolBucket);
```

つまり、**[`StyleLayer`](#StyleLayer)と[`Tile`](#Tile)があれば、[`SymbolBucket`](#SymbolBucket)も手に入ります**。

### StyleLayerとTileを解決する

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)は[`Placement#getBucketParts`](#Placement#getBucketParts)を繰り返し呼び出します([style/pauseable_placement.js#L35-L43](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L35-L43))。
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

上記スニペットの`tiles`と`styleLayer`は[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)に対する引数です。
[`PauseablePlacement#continuePlacement`](#PauseablePLacement#continuePlacement)は[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)を繰り返し呼び出します([style/pauseable_placement.js#L97-L123](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L97-L123),  `layerTiles[layer.source]` &rightarrow; `tiles`, `layer` &rightarrow; `styleLayer`)。
```ts
        while (this._currentPlacementIndex >= 0) {
            const layerId = order[this._currentPlacementIndex];
            const layer = layers[layerId];
            const placementZoom = this.placement.collisionIndex.transform.zoom;
            if (layer.type === 'symbol' &&
                (!layer.minzoom || layer.minzoom <= placementZoom) &&
                (!layer.maxzoom || layer.maxzoom > placementZoom)) {
                // ... 可読性のため割愛
                const pausePlacement = this._inProgressLayer.continuePlacement(layerTiles[layer.source], this.placement, this._showCollisionBoxes, layer, shouldPausePlacement);
            // ... 可読性のため割愛
        }
```

以下の条件判定([style/pauseable_placement.js#L101](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L101))からわかるとおり、[`PausePlacement#continuePlacement`](#PauseablePlacement#continuePlacement)は[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)を"Symbol"レイヤーにのみ適用します。
```ts
            if (layer.type === 'symbol' &&
```

上記スニペットの`order`, `layers`, `layerTiles`は[`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement)に対する引数です。
[`Style#_updatePlacement`](#Style#_updatePlacement)は[`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement)を呼び出します([style/style.js#L1740](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1740))。
```ts
            this.pauseablePlacement.continuePlacement(this._order, this._layers, layerTiles);
```

[`Style#_updatePlacement`](#Style#_updatePlacement)は[style/style.js#L1696-L1712](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1696-L1712)で`layerTiles`を用意しています。
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
            // ... 可読性のため割愛
        }
```

ということで上記コードを真似すれば、**与えたレイヤーIDに対応する[`StyleLayer`](#StyleLayer)とすべての[`Tile`](#Tile)を取得することができます**。

### レイヤーのTileとSymbolBucketをリストする

まとめると、指定したレイヤーの[`Tile`](#Tile)と[`SymbolBucket`](#SymbolBucket)をリストするコードのアウトラインは以下のようになります。
```ts
// 仮定 map: mapboxgl.Map, layerId: string
const style = map.style;
const layer = style._layers[layerId];
const sourceCache = style._getLayerSourceCache(layer);
const layerTiles = sourceCache.getRenderableIds(true).map(id => sourceCache.getTileByID(id));
for (const tile of layerTiles) {
    const bucket = tile.getBucket(layer);
    // tileとbucketの処理 ...
}
```

追加のチェックを含む完成したコードは[私のGitHubレポジトリ](https://github.com/codemonger-io/mapbox-collision-boxes/blob/3379090e3945ed2850e1fc882be60a9e6b25eea2/src/index.ts#L57-L144)にあります。

## シンボルのFeatureを解決する

[前回の投稿](../0009-mapbox-collision-boxes/)で、[`FeatureIndex`はシンボルのFeatureを解決する上で重要である](../0009-mapbox-collision-boxes/#FeatureIndex)ことに軽く触れました。
[`Map#queryRenderedFeatures`](#Map#queryRenderedFeatures)を調べることでそれがわかりました。

### 概要:Map#queryRenderedFeaturesがどのように機能するか

[`Map#queryRenderedFeatures`](#Map#queryRenderedFeatures)は[`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures)を呼び出します([ui/map.js#L1719](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L1719))。
```ts
        return this.style.queryRenderedFeatures(geometry, options, this.transform);
```

[`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures)は[`queryRenderedSymbols`](#query_features.queryRenderedSymbols)を呼び出します([style/style.js#L1384-L1391](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1384-L1391))。
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

[`queyrRenderedSymbols`](#query_features.queryRenderedSymbols)は[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)を呼び出し、シンボルに対応するFeatureを取得します([source/query_features.js#L95-L103](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L95-L103))。
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

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)は最初のパラメータ`renderedSymbols[queryData.bucketInstanceId]`に対応する[GeoJSON](https://geojson.org)形式のFeatureを解決し、読み込みます。

なので、**[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)に適切なパラメータを与えることでFeatureを解決することができます**。

### FeatureIndex#lookupSymbolFeaturesに対するパラメータを用意する

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)の呼び出し結果([source/query_features.js#L95-L103](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L95-L103))を再現するには以下のパラメータを提供する必要があります。
- [`queryData`](#パラメータ:_queryData)
- [`serializedLayers`](#パラメータ:_serializedLayers)
- [`params.filter`](#パラメータ:_params.filter)
- [`params.layers`](#パラメータ:_params.layers)
- [`params.availableImages`](#パラメータ:_params.availableImages)
- [`styleLayers`](#パラメータ:_styleLayers)

ちなみに最初のパラメータ`renderedSymbols[queryData.bucketInstanceId]`を再現する必要はありません。なぜなら[`SymbolBucket`](#SymbolBucket)で特定のバウンディングボックスと重なるFeatureではなくすべてのFeatureが必要だからです。
このパラメータをどのように置き換えるかについては[節「SymbolBucketのすべてのFeatureのインデックスをリストする」](#SymbolBucketのすべてのFeatureのインデックスをリストする)を参照ください。

#### パラメータ: queryData

`queryData`はループ変数で[`RetainedQueryData`](#RetainedQueryData)が代入されます([source/query_features.js#L94-L132](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L94-L132))。
```ts
    for (const queryData of bucketQueryData) {
        const bucketSymbols = queryData.featureIndex.lookupSymbolFeatures(
        // ... 可読性のため割愛
    }
```

`bucketQueryData`は[`RetainedQueryData`](#RetainedQueryData)の配列で[source/query_features.js#L88-L92](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L88-L92)で初期化されます。
```ts
    const bucketQueryData = [];
    for (const bucketInstanceId of Object.keys(renderedSymbols).map(Number)) {
        bucketQueryData.push(retainedQueryData[bucketInstanceId]);
    }
    bucketQueryData.sort(sortTilesIn);
```

`retainedQueryData`は[`Placement#retainedQueryData`](#Placement#retainedQueryData)です。

[`queryRenderedSymbols`](#query_features.queryRenderedSymbols)は`renderedSymbols`を初期化します([source/query_features.js#L87](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L87))。
```ts
    const renderedSymbols = collisionIndex.queryRenderedSymbols(queryGeometry);
```

[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols)は`bucketInstanceId`を[`SymbolBucket`](#SymbolBucket)内でその`bucketInstanceId`に対応し指定のバウンディングボックスと重なるFeatureのインデックス列にマップするオブジェクトを返します。
表示されているシンボルのみを扱うのでライブラリでは[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols)は使いません。

[`SymbolBucket`のリストは持っている](#レイヤーのTileとSymbolBucketをリストする)ので、**各[`SymbolBucket#bucketInstanceId`](#SymbolBucket#bucketInstanceId)に対応する[`RetainedQueryData`](#RetainedQueryData)を[`Placement#retainedQueryData`](#Placement#retainedQueryData)から得ることができます**。
```ts
// 仮定 placement: Placement, bucket: SymbolBucket
const queryData = placement.retainedQueryData[bucket.bucketInstanceId];
```

#### パラメータ: serializedLayers

このパラメータは[`Style#_serializedLayers`](#Style#_serializedLayers)です。

#### パラメータ: params.filter

[`Map#queryRenderedFeatures`](#Map#queryRenderedFeatures)はデフォルトで空のオブジェクトを[`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures)の`params`引数に指定します(`options` &rightarrow; `params`, [ui/map.js#L1716-L1719](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L1716-L1719))。
```ts
        options = options || {};
        geometry = geometry || [[0, 0], [this.transform.width, this.transform.height]];

        return this.style.queryRenderedFeatures(geometry, options, this.transform);
```

なのでこのパラメータは`undefined`でよいです。

#### パラメータ: params.layers

[`params.filter`](#パラメータ:_params.filter)と同様に、このパラメータも`undefined`でよいです。

#### パラメータ: params.availableImages

[`Style#queryRenderedFeatures`](#Style#queryRenderedFeatures)は[`Style#_availableImages`](#Style#_availableImages)をこのパラメータに指定しています([style/style.js#L1354](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1354))。
```ts
        params.availableImages = this._availableImages;
```

#### パラメータ: styleLayers

このパラメータは[`Style#_layers`](#Style#_layers)です。

#### SymbolBucketのすべてのFeatureのインデックスをリストする

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)が最初の引数(`symbolFeatureIndexes`)として受け取るFeatureのインデックスとは何でしょうか?
[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols)は使いませんが、それが何をしているのかを調べれば[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)の正しい入力を理解するのに役立つはずです。

この後に続く分析は大変なので先に結論からお伝えします。
[`SymbolBucket`](#SymbolBucket)のすべてのFeatureのインデックスをリストするには、**[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)のすべての要素から`featureIndex`プロパティを取り出す、もしくは[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)のすべての要素から`iconFeatureIndex`プロパティを取り出します**。
```ts
// 仮定 bucket: SymbolBucket
// SymbolBucket#symbolInstancesは通常の配列ではないので注意
for (let i = 0; i < bucket.symbolInstances.length; ++i>) {
    const featureIndex = bucket.symbolInstances.get(i).featureIndex;
    // ... Featureのインデックスを処理
    // ... 衝突ボックスはbucket.collisionArrays[i]から計算可能
}
```

Featureを衝突ボックスに対応づけるのは単純です。なぜなら上記コードの`featureIndex`は`bucket.collisionArrays[i]`([衝突ボックス再計算のためのパラメータ](../0009-mapbox-collision-boxes/#パラメータ:_collisionBox))に対応しているからです。
この節の残りは[次の節「アイコンの大きさを計算する」](#アイコンの大きさを計算する)まで飛ばして構いません。

##### CollisionIndex#queryRenderedSymbolsは何をしているのか?

[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols)は[`GridIndex#query`](#GridIndex#query)を呼び出し、指定したバウンディングボックスと重なるFeatureをリストします([symbol/collision_index.js#L360-L361](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L360-L361))。
```ts
        const features = this.grid.query(minX, minY, maxX, maxY)
            .concat(this.ignoredGrid.query(minX, minY, maxX, maxY));
```

それから`features`のすべての要素を[symbol/collision_index.js#L366-L396](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L366-L396)のループで処理します。
```ts
        for (const feature of features) {
            const featureKey = feature.key;
            // ... 可読性のため割愛
            result[featureKey.bucketInstanceId].push(featureKey.featureIndex);
        }
```

[`CollisionIndex#queryRenderedSymbols`](#CollisionIndex#queryRenderedSymbols)は最終的に上記コードで更新された`result`を返します。
では[`GridIndex#query`](#GridIndex#query)が返す`features`とは何でしょうか?
[`GridIndex#query`](#GridIndex#query)は指定したバウンディングボックスと重なる[`GridItem`](#GridItem)の配列を返します。
[`GridIndex#query`](#GridIndex#query)はこれらの[`GridItem`](#GridItem)を[`GridIndex`](#GridIndex)がFeatureキーと一緒に格納しているボックスとサークルの情報([`GridIndex#bboxes`](#GridIndex#bboxes), [`GridIndex#circles`](#GridIndex#circles), [`GridIndex#boxKeys`](#GridIndex#boxKeys), [`GridIndex#circleKeys`](#GridIndex#circleKeys))から構築します。
ということで、[`GridIndex#boxKeys`](#GridIndex#boxKeys)(サークルのことは忘れましょう)の起源を追跡すれば、[`SymbolBucket`](#SymbolBucket)のすべてのFeatureのインデックスを取得する方法がわかるはずです。

##### GridIndex#boxKeysの起源

[`GridIndex#insert`](#GridIndex#insert)は[`GridIndex#boxKeys`](#GridIndex#boxKeys)に`key`を追加します([symbol/grid_index.js#L73](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L73))。
```ts
        this.boxKeys.push(key);
```

[`CollisionIndex#insertCollisionBox`](#CollisionIndex#insertCollisionBox)が`key`を用意し[`GridIndex#insert`](#GridIndex#insert)に渡します([symbol/collision_index.js#L401-L406](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L401-L406))。
```ts
    insertCollisionBox(collisionBox: Array<number>, ignorePlacement: boolean, bucketInstanceId: number, featureIndex: number, collisionGroupID: number) {
        const grid = ignorePlacement ? this.ignoredGrid : this.grid;

        const key = {bucketInstanceId, featureIndex, collisionGroupID};
        grid.insert(key, collisionBox[0], collisionBox[1], collisionBox[2], collisionBox[3]);
    }
```

ここで上記スニペットの`key`を構成する`featureIndex`の起源に関心が移ります。

##### featureIndexの起源

シンボルのアイコンに絞ると、[`Placement#placeLayerBucketPart.placeSymbol` (`placeSymbol`)](#Placement#placeLayerBucketPart.placeSymbol)は[symbol/placement.js#L748-L749](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L748-L749)で[`CollisionIndex#insertCollisionBox`](#CollisionIndex#insertCollisionBox)を呼び出しています。
```ts
                this.collisionIndex.insertCollisionBox(placedIconBoxes.box, layout.get('icon-ignore-placement'),
                        bucket.bucketInstanceId, iconFeatureIndex, collisionGroup.ID);
```

[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)は[symbol/placement.js#L698](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L698)で`iconFeatureIndex`を設定しています。
```ts
                iconFeatureIndex = collisionArrays.iconFeatureIndex;
```

`collisionArrays`は[`CollisionArrays`](#CollisionArrays)であり[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)の3番目の引数です。
今度は[`CollisionArrays`](#CollisionArrays)の起源を追いかけます。
[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)を[symbol/placement.js#L791](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L791)または[symbol/placement.js#L795](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L795)で呼び出しています。
```ts
                placeSymbol(bucket.symbolInstances.get(symbolIndex), symbolIndex, bucket.collisionArrays[symbolIndex]);
```

```ts
                placeSymbol(bucket.symbolInstances.get(i), i, bucket.collisionArrays[i]);
```

よって`CollisionArrays`は[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)の要素です。
[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes)を呼び出して[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)を初期化して埋めます([symbol/placement.js#L432](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L432))。
```ts
            bucket.deserializeCollisionBoxes(collisionBoxArray);
```

[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes)は[`CollisionArrays#iconFeatureIndex`](#CollisionArrays)を実際に設定する[`SymbolBucket#_deserializeCollisionBoxesForSymbol`](#SymbolBucket#_deserializeCollisionBoxesForSymbol)を呼び出します([data/bucket/symbol_bucket.js#L962-L968](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L962-L968))。
```ts
        for (let k = iconStartIndex; k < iconEndIndex; k++) {
            // An icon can only have one box now, so this indexing is a bit vestigial...
            const box: CollisionBox = (collisionBoxArray.get(k): any);
            collisionArrays.iconBox = {x1: box.x1, y1: box.y1, x2: box.x2, y2: box.y2, padding: box.padding, projectedAnchorX: box.projectedAnchorX, projectedAnchorY: box.projectedAnchorY, projectedAnchorZ: box.projectedAnchorZ, tileAnchorX: box.tileAnchorX, tileAnchorY: box.tileAnchorY};
            collisionArrays.iconFeatureIndex = box.featureIndex;
            break; // Only one box allowed per instance
        }
```

では[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes)に与える`collisionBoxArray`とは何者でしょうか([symbol/placement.js#L432](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L432))?

##### collisionBoxArrayの起源

`collisionBoxArray`は[`TileLayerParameters`](#TileLayerParameters)に含まれており、[`Placement#getBucketParts`](#Placement#getBucketParts)はそれを[`Tile#collisionBoxArray`](#Tile#collisionBoxArray)から取得します([symbol/placement.js#L242](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L242))。
```ts
        const collisionBoxArray = tile.collisionBoxArray;
```

[`Tile#loadVectorData`](#Tile#loadVectorData)は[`Tile#collisionBoxArray`](#Tile#collisionBoxArray)を設定します([source/tile.js#L245](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L245))。
```ts
        this.collisionBoxArray = data.collisionBoxArray;
```

[`Tile#loadVectorData`](#Tile#loadVectorData)は[source/geojson_source.js#L372](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/geojson_source.js#L372)と[source/vector_tile_source.js#L320](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_source.js#L320)で呼び出されています。
```ts
            tile.loadVectorData(data, this.map.painter, message === 'reloadTile');
```

```ts
            tile.loadVectorData(data, this.map.painter);
```

上記呼び出しは[`VectorTileWorkerSource#loadTile`](#VectorTileWorkerSource#loadTile)もしくは[`VectorTileWorkerSource#reloadTile`](#VectorTileWorkerSource#reloadTile)の結果として発生します。
[`VectorTileWorkerSource#loadTile`](#VectorTileWorkerSource#loadTile)と[`VectorTileWorkerSource#reloadTile`](#VectorTileWorkerSource#reloadTile)のいずれも生のVector Tileデータを解析するのに[`WorkerTile#parse`](#WorkerTile#parse)を呼び出します。
[`WorkerTile#parse`](#WorkerTile#parse)は解析したデータを[source/worker_tile.js#L261-L272](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L261-L272)で出力します。
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

上記コードの`collisionBoxArray` (=[`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray))は結果的に[`Tile#collisionBoxArray`](#Tile#collisionBoxArray)になります。
シンボルのアイコンに絞ると、[`WorkerTile#parse`](#WorkerTile#parse)は[source/worker_tile.js#L239-L248](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L239-L248)で[`performSymbolLayout`](#symbol_layout.performSymbolLayout)を呼び出し、[`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray)を更新します。
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

このコンテキストでは`bucket`は[`SymbolBucket`](#SymbolBucket)であり、また[`SymbolBucket#collisionBoxArray`](#SymbolBucket#collisionBoxArray)はBucketを生成する関数([source/worker_tile.js#L155-L168](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L155-L168))に与えられる[`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray)を指していることにご注意ください。
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

[`performSymbolLayout`](#symbol_layout.performSymbolLayout)は`bucket`内のFeatureをリストし、[symbol/symbol_layout.js#L322](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L322)で[`addFeature`](#symbol_layout.addFeature)を呼び出します。
```ts
            addFeature(bucket, feature, shapedTextOrientations, shapedIcon, imageMap, sizes, layoutTextSize, layoutIconSize, textOffset, isSDFIcon, availableImages, canonical, projection);
```

[`addFeature`](#symbol_layout.addFeature)(正確にはその内部関数`addSymbolAtAnchor`)は[`addSymbol`](#symbol_layout.addSymbol)を呼び出します([symbol/symbol_layout.js#L438-L442](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L438-L442))。
```ts
        addSymbol(bucket, anchor, globe, line, shapedTextOrientations, shapedIcon, imageMap, verticallyShapedIcon, bucket.layers[0],
            bucket.collisionBoxArray, feature.index, feature.sourceLayerIndex,
            bucket.index, textPadding, textAlongLine, textOffset,
            iconBoxScale, iconPadding, iconAlongLine, iconOffset,
            feature, sizes, isSDFIcon, availableImages, canonical);
```

シンボルのアイコンに絞ると、[`addSymbol`](#symbol_layout.addSymbol)は[symbol/symbol_layout.js#L731](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L731)で[`evaluateBoxCollisionFeature`](#symbol_layout.evaluateBoxCollisionFeature)を呼び出します。
```ts
        iconBoxIndex = evaluateBoxCollisionFeature(collisionBoxArray, collisionFeatureAnchor, anchor, featureIndex, sourceLayerIndex, bucketIndex, shapedIcon, iconPadding, iconRotate);
```

[`evaluateBoxCollisionFeature`](#symbol_layout.evaluateBoxCollisionFeature)は`collisionBoxArray`に要素を追加します([symbol/symbol_layout.js#L634](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L634))。
```ts
    collisionBoxArray.emplaceBack(projectedAnchor.x, projectedAnchor.y, projectedAnchor.z, tileAnchor.x, tileAnchor.y, x1, y1, x2, y2, padding, featureIndex, sourceLayerIndex, bucketIndex);
```

ここで`collisionBoxArray`は[`WorkerTile#collisionBoxArray`](#WorkerTile#collisionBoxArray)と同一であることにご注意ください。

##### SymbolBucket#symbolInstances vs SymbolBucket#collisionArrays

行[symbol/placement.js#L791](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L791)と行[symbol/placement.js#L795](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L795)によれば、**[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)の要素は[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)の要素に対応しています**。
```ts
                placeSymbol(bucket.symbolInstances.get(symbolIndex), symbolIndex, bucket.collisionArrays[symbolIndex]);
```

```ts
                placeSymbol(bucket.symbolInstances.get(i), i, bucket.collisionArrays[i]);
```


[`addSymbol`](#symbol_layout.addSymbol)は[symbol/symbol_layout.js#L854-L884](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L854-L884)で[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)にも要素を追加しています。
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

つまり、[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)と[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)の対応する要素は、それぞれ **`featureIndex`と`iconFeatureIndex`に全く同じFeatureのインデックス**を持っています。

##### FeatureIndex#lookupSymbolFeaturesは何をしているのか?

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)は実際には何をしているのでしょうか?
[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)から取り出したFeatureのインデックス(`featureIndex`)を最初の引数(`symbolFeatureIndexes`)に指定するのは理にかなっているでしょうか?

[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)は[`FeatureIndex#loadMatchingFeature`](#FeatureIndex#loadMatchingFeature)を繰り返し呼び出しています([data/feature_index.js#L257-L272](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L257-L272), `symbolFeatureIndex` &rightarrow; `featureIndexData.featureIndex`)。
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

[`FeatureIndex#loadMatchingFeature`](#FeatureIndex#loadMatchingFeature)は`featureIndex`を[data/feature_index.js#L188-L190](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L188-L190)でFeatureを読み込むのに使っています。
```ts
        const sourceLayerName = this.sourceLayerCoder.decode(sourceLayerIndex);
        const sourceLayer = this.vtLayers[sourceLayerName];
        const feature = sourceLayer.feature(featureIndex);
```

一方で、[`performSymbolLayout`](#symbol_layout.performSymbolLayout)は[`SymbolBucket#features`](#SymbolBucket#features)内のFeatureを列挙し、ひとつずつ[`addFeature`](#symbol_layout.addFeature)に渡しています([symbol/symbol_layout.js#L197-L324](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L197-L324))。
```ts
    for (const feature of bucket.features) {
        // ... 可読性のため割愛
        if (shapedText || shapedIcon) {
            addFeature(bucket, feature, shapedTextOrientations, shapedIcon, imageMap, sizes, layoutTextSize, layoutIconSize, textOffset, isSDFIcon, availableImages, canonical, projection);
        }
    }
```

では[`SymbolBucket#features`](#SymbolBucket#features)はどこから来るのでしょうか?
[`SymbolBucket#populate`](#SymbolBucket#populate)が[`SymbolBucket#features`](#SymbolBucket#features)を初期化して埋めています([data/bucket/symbol_bucket.js#L475-L626](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L475-L626))。
```ts
    populate(features: Array<IndexedFeature>, options: PopulateParameters, canonical: CanonicalTileID, tileTransform: TileTransform) {
        // ... 可読性のため割愛
        this.features = [];
        // ... 可読性のため割愛
        for (const {feature, id, index, sourceLayerIndex} of features) {
            // ... 可読性のため割愛
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
            // ... 可読性のため割愛
        }
        // ... 可読性のため割愛
    }
```

[`WorkerTile#parse`](#WorkerTile#parse)はBucketを生成した直後に[`SymbolBucket#populate`](#SymbolBucket#populate)を呼び出しています([source/worker_tile.js#L171](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L171))。
```ts
                bucket.populate(features, options, this.tileID.canonical, this.tileTransform);
```

そして[`WorkerTile#parse`](#WorkerTile#parse)は最初の引数の`features`を[source/worker_tile.js#L137-L142](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L137-L142)で用意しています。
```ts
            const features = [];
            for (let index = 0; index < sourceLayer.length; index++) {
                const feature = sourceLayer.feature(index);
                const id = featureIndex.getId(feature, sourceLayerId);
                features.push({feature, id, index, sourceLayerIndex});
            }
```

ということで上記コード内の`index`は最終的に他のFeatureに関する情報と併せて[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)の`featureIndex`となります。

よって **[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)の`featureIndex`プロパティは[`FeatureIndex#lookupSymbolFeatures`](#FeatureIndex#lookupSymbolFeatures)の最初の引数`symbolFeatureIndexes`と整合性がとれている**ことがわかりました。

## アイコンの大きさを計算する

[前回の投稿](../0009-mapbox-collision-boxes/)で、[アイコンの`scale`パラメータを再現できる](../0009-mapbox-collision-boxes/#パラメータ:_scale)と結論づけました。
しかし、`partiallyEvaluatedIconSize`を計算するための[`evaluateSizeForZoom`](#symbol_size.evaluateSizeForZoom)関数が`mapbox-gl-js`からエクスポートされていないことに後から気づきました。
ということでライブラリを実装するためには`mapbox-gl-js`から[`evaluateSizeForZoom`](#symbol_size.evaluateSizeForZoom)の複製を作成しなければなりませんでした。

[`evaluateSizeForZoom`](#symbol_size.evaluateSizeForZoom)が機能するために、以下の型や関数も複製しなければなりませんでした。
- [`SizeData`](#symbol_size.SizeData)
- [`InterpolatedSize`](#symbol_size.InterpolatedSize)
- [`InterpolationType`](#interpolate.InterpolationType)
- [`interpolationFactor`](#Interpolate.interpolationFactor)
- [`exponentialInterpolation`](#interpolate.exponentialInterpolation)
- [`interpolate`](#util.interpolate)
- [`clamp`](#util.clamp)

複製したものは[私のGitHubレポジトリ](https://github.com/codemonger-io/mapbox-collision-boxes/blob/v0.1.0/src/private/symbol-size.ts)にあります。

## まとめ

このブログ投稿では、[`Tile`](#Tile)と[`SymbolBucket`](#SymbolBucket)をリストし、シンボルのFeatureを解決する方法を示しました。
最終的なループは以下のようになります。
```ts
// 仮定 map: mapboxgl.Map, layerId: string
const style = map.style;
const layer = style._layers[layerId];
const sourceCache = style._getLayerSourceCache(layer);
const layerTiles = sourceCache.getRenderableIds(true).map(id => sourceCache.getTileByID(id));
for (const tile of layerTiles) {
    const bucket = tile.getBucket(layer);
    for (let i = 0; i < bucket.symbolInstances.length; ++i>) {
        const featureIndex = bucket.symbolInstances.get(i).featureIndex;
        // ... 衝突ボックスを再計算しFeatureに関連づける
    }
}
```

またアイコンのサイズを計算する方法もカバーしました。

ライブラリを実装している途中、`mapbox-gl-js`の内部タイプが利用できないというTypeScript特有の課題に直面しました。
[今後のブログ投稿](../0011-mapbox-collision-boxes/)で、その課題にどう対処したかを共有するつもりです。

[私のGitHubレポジトリ](https://github.com/codemonger-io/mapbox-collision-boxes)でライブラリもご確認ください!

## 補足

### ソースコードレファレンス

#### Map

定義: [ui/map.js#L326-L3677](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L326-L3677)

##### Map#queryRenderedFeatures

定義: [ui/map.js#L1697-L1720](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L1697-L1720)

このメソッドは[`Map#queryRenderedFeatures` API](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#queryrenderedfeatures)を実装します。

#### Style

定義: [style/style.js#L135-L1860](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L135-L1860)

##### Style#_layers

定義: [style/style.js#L148](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L148)
```ts
    _layers: {[_: string]: StyleLayer};
```

##### Style#_serializedLayers

定義: [style/style.js#L152](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L152)
```ts
    _serializedLayers: {[_: string]: Object};
```

##### Style#_availableImages

定義: [style/style.js#L168](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L168)
```ts
    _availableImages: Array<string>;
```

##### Style#queryRenderedFeatures

定義: [style/style.js#L1330-L1396](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1330-L1396)

##### query_features.queryRenderedSymbols

定義: [source/query_features.js#L79-L149](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/query_features.js#L79-L149)

##### Style#_updatePlacement

定義: [src/style/style.js#L1692-L1766](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1692-L1766)

このメソッドは[`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement)を呼び出します。

#### Tile

定義: [source/tile.js#L95-L799](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L95-L799)

##### Tile#tileID

定義: [source/tile.js#L96](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L96)
```ts
    tileID: OverscaledTileID;
```

##### Tile#collisionBoxArray

定義: [source/tile.js#L115](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L115)
```ts
    collisionBoxArray: ?CollisionBoxArray;
```

##### Tile#loadVectorData

定義: [source/tile.js#L221-L290](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L221-L290)

#### VectorTileWorkerSource

定義: [source/vector_tile_worker_source.js#L140-L309](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_worker_source.js#L140-L309)

##### VectorTileWorkerSource#loadTile

定義: [source/vector_tile_worker_source.js#L177-L238](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_worker_source.js#L177-L238)

このメソッドはWorkerスレッドで実行されます。

##### VectorTileWorkerSource#reloadTile

定義: [source/vector_tile_worker_source.js#L244-L275](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/vector_tile_worker_source.js#L244-L275)

このメソッドはWorkerスレッドで実行されます。

#### WorkerTile

定義: [source/worker_tile.js#L36-L277](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L36-L277)

##### WorkerTile#collisionBoxArray

定義: [source/worker_tile.js#L57](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L57)
```ts
    collisionBoxArray: CollisionBoxArray;
```

##### WorkerTile#parse

定義: [source/worker_tile.js#L83-L276](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L83-L276)

##### symbol_layout.performSymbolLayout

定義: [symbol/symbol_layout.js#L152-L329](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L152-L329)

[`WorkerTile#parse`](#WorkerTile#parse)はこの関数を呼び出します([source/worker_tile.js#L239-L248](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/worker_tile.js#L239-L248))。
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

定義: [symbol/symbol_layout.js#L367-L500](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L367-L500)

シンボルのアイコンに絞ると、[`symbol_layout.performSymbolLayout`](#symbol_layout.performSymbolLayout)は[symbol/symbol_layout.js#L322](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L322)でこの関数を呼び出します。
```ts
            addFeature(bucket, feature, shapedTextOrientations, shapedIcon, imageMap, sizes, layoutTextSize, layoutIconSize, textOffset, isSDFIcon, availableImages, canonical, projection);
```

##### symbol_layout.addSymbol

定義: [symbol/symbol_layout.js#L657-L885](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L657-L885)

この関数は[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)を更新します([symbol/symbol_layout.js#L854-L884](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L854-L884))。
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

[`symbol_layout.addFeature`](#symbol_layout.addFeature)の内部関数`addSymbolAtAnchor`がこの関数を呼び出します([symbol/symbol_layout.js#L438-L442](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L438-L442))。
```ts
        addSymbol(bucket, anchor, globe, line, shapedTextOrientations, shapedIcon, imageMap, verticallyShapedIcon, bucket.layers[0],
            bucket.collisionBoxArray, feature.index, feature.sourceLayerIndex,
            bucket.index, textPadding, textAlongLine, textOffset,
            iconBoxScale, iconPadding, iconAlongLine, iconOffset,
            feature, sizes, isSDFIcon, availableImages, canonical);
```

##### symbol_layout.evaluateBoxCollisionFeature

定義: [symbol/symbol_layout.js#L580-L637](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L580-L637)

この関数は`collisionBoxArray`を更新します([symbol/symbol_layout.js#L634](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L634))。
```ts
    collisionBoxArray.emplaceBack(projectedAnchor.x, projectedAnchor.y, projectedAnchor.z, tileAnchor.x, tileAnchor.y, x1, y1, x2, y2, padding, featureIndex, sourceLayerIndex, bucketIndex);
```

シンボルのアイコンに絞ると、[`symbol_layout.addSymbol`](#symbol_layout.addSymbol)は[symbol/symbol_layout.js#L731](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_layout.js#L731)でこの関数を呼び出します。
```ts
        iconBoxIndex = evaluateBoxCollisionFeature(collisionBoxArray, collisionFeatureAnchor, anchor, featureIndex, sourceLayerIndex, bucketIndex, shapedIcon, iconPadding, iconRotate);
```

#### StyleLayer

定義: [style/style_layer.js#L39-L323](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style_layer.js#L39-L323)

#### SymbolBucket

定義: [data/bucket/symbol_bucket.js#L352-L1119](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L352-L1119)

##### SymbolBucket#bucketInstanceId

定義: [data/bucket/symbol_bucket.js#L368](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L368)
```ts
    bucketInstanceId: number;
```

##### SymbolBucket#features

定義: [data/bucket/symbol_bucket.js#L378](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L378)
```ts
    features: Array<SymbolFeature>;
```

##### SymbolBucket#collisionArrays

定義t: [data/bucket/symbol_bucket.js#L380](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L380)
```ts
    collisionArrays: Array<CollisionArrays>;
```

このプロパティの要素は[`SymbolBucket#symbolInstances`](#SymbolBucket#symbolInstances)の要素に対応します。

[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes)はこのプロパティを初期化して埋めます。

##### SymbolBucket#symbolInstances

定義: [data/bucket/symbol_bucket.js#L379](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L379)
```ts
    symbolInstances: SymbolInstanceArray;
```

このプロパティの要素は[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)の要素に対応します。

##### SymbolBucket#collisionBoxArray

定義: [data/bucket/symbol_bucket.js#L356](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L356)

##### SymbolBucket#populate

定義: [data/bucket/symbol_bucket.js#L475-L626](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L475-L626)

##### SymbolBucket#deserializeCollisionBoxes

定義: [data/bucket/symbol_bucket.js#L979-L995](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L979-L995)

このメソッドは[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)を初期化して埋めます。

##### SymbolBucket#_deserializeCollisionBoxesForSymbol

定義: [data/bucket/symbol_bucket.js#L943-L977](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L943-L977)

#### FeatureIndex

定義: [data/feature_index.js#L54-L312](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L54-L312)

##### FeatureIndex#lookupSymbolFeatures

定義: [data/feature_index.js#L244-L274](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L244-L274)

このメソッドは[`FeatureIndex#loadMatchingFeature`](#FeatureIndex#loadMatchingFeature)を呼び出します([data/feature_index.js#L258-L270](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L258-L270))。
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

定義: [data/feature_index.js#L172-L240](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L172-L240)

このメソッドはシンボルのFeature(GeoJSON形式)をVector Tileデータから読み込みます。

#### CollisionIndex

定義: [symbol/collision_index.js#L64-L465](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L64-L465)

##### CollisionIndex#queryRenderedSymbols

定義: [symbol/collision_index.js#L341-L399](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L341-L399)

##### CollisionIndex#insertCollisionBox

定義: [symbol/collision_index.js#L401-L406](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L401-L406)
```ts
    insertCollisionBox(collisionBox: Array<number>, ignorePlacement: boolean, bucketInstanceId: number, featureIndex: number, collisionGroupID: number) {
        const grid = ignorePlacement ? this.ignoredGrid : this.grid;

        const key = {bucketInstanceId, featureIndex, collisionGroupID};
        grid.insert(key, collisionBox[0], collisionBox[1], collisionBox[2], collisionBox[3]);
    }
```

#### GridIndex

定義: [symbol/grid_index.js#L24-L341](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L24-L341)

##### GridIndex#bboxes

定義: [symbol/grid_index.js#L29](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L29)
```ts
    bboxes: Array<number>;
```

[`GridIndex#boxKeys`](#GridIndex#boxKeys)もご覧ください。

##### GridIndex#boxKeys

定義: [symbol/grid_index.js#L26](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L26)
```ts
    boxKeys: Array<any>;
```

このプロパティは[`GridIndex#bboxes`](#GridIndex#bboxes)内の同じインデックスにあるボックスに対応するFeatureのキーを格納します。

[`GridIndex#insert`](#GridIndex#insert)はこのプロパティを更新します。

##### GridIndex#circles

定義: [symbol/grid_index.js#L30](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L30)
```ts
    circles: Array<number>;
```

[`GridIndex#circleKeys`](#GridIndex#circleKeys)もご覧ください。

##### GridIndex#circleKeys

定義: [symbol/grid_index.js#L25](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L25)
```ts
    circleKeys: Array<any>;
```

このプロパティは[`GridIndex#circles`](#GridIndex#circles)内の同じインデックスにあるサークルに対応するFeatureのキーを格納します。

##### GridIndex#insert

定義: [symbol/grid_index.js#L71-L78](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L71-L78)

このメソッドは指定した`key`を[`GridIndex#boxKeys`](#GridIndex#boxKeys)に追加します([symbol/grid_index.js#L73](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L73))。
```ts
        this.boxKeys.push(key);
```

##### GridIndex#query

定義: [symbol/grid_index.js#L163-L165](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L163-L165)
```ts
    query(x1: number, y1: number, x2: number, y2: number, predicate?: any): Array<GridItem> {
        return (this._query(x1, y1, x2, y2, false, predicate): any);
    }
```

[`GridIndex#_query`](#GridIndex#_query)もご覧ください。

##### GridIndex#_query

定義: [symbol/grid_index.js#L98-L137](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L98-L137)

このメソッドは[`GridIndex#_forEachCell`](#GridIndex#_forEachCell)を呼び出します([symbol/grid_index.js#L134](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L134))。
```ts
            this._forEachCell(x1, y1, x2, y2, this._queryCell, result, queryArgs, predicate);
```

##### GridIndex#_forEachCell

定義: [symbol/grid_index.js#L291-L303](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L291-L303)
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

このメソッドは指定したバウンディングボックスと重なるすべてのセルに`fn`を適用します。

[`GridIndex#query`](#GridIndex#query)のコンテキストでは、`fn`は[`GridIndex#_queryCell`](#GridIndex#_queryCell)です。

##### GridIndex#_queryCell

定義: [symbol/grid_index.js#L175-L240](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L175-L240)

このメソッドは指定したセルで指定したバウンディングボックスと重なるボックスとサークルを集めます。

#### GridItem

定義: [symbol/grid_index.js#L3-L9](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/grid_index.js#L3-L9)
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

定義: [symbol/placement.js#L192-L1184](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L192-L1184)

##### Placement#retainedQueryData

定義: [symbol/placement.js#L205](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L205)
```ts
    retainedQueryData: {[_: number]: RetainedQueryData};
```

[`RetainedQueryData`](#RetainedQueryData)もご覧ください。

##### Placement#getBucketParts

定義: [symbol/placement.js#L233-L333](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L233-L333)

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)はこのメソッドを呼び出します([style/pauseable_placement.js#L37](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L37))。
```ts
            placement.getBucketParts(bucketParts, styleLayer, tile, this._sortAcrossTiles);
```

[前回のブログ投稿の関連する節](../0009-mapbox-collision-boxes/#Placement#getBucketParts)もご覧ください。

##### Placement#placeLayerBucketPart

定義: [symbol/placement.js#L386-L808](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L386-L808)

[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)はこのメソッドを呼び出します([style/pauseable_placement.js#L52](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L52))。
```ts
            placement.placeLayerBucketPart(bucketPart, this._seenCrossTileIDs, showCollisionBoxes, bucketPart.symbolInstanceStart === 0);
```

[前回のブログ投稿の関連する節](../0009-mapbox-collision-boxes/#Placement#placeLayerBucketPart)もご覧ください。

##### Placement#placeLayerBucketPart.placeSymbol

定義: [symbol/placement.js#L439-L784](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L439-L784)

#### RetainedQueryData

定義: [symbol/placement.js#L87-L105](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L87-L105)
```ts
export class RetainedQueryData {
    bucketInstanceId: number;
    featureIndex: FeatureIndex;
    sourceLayerIndex: number;
    bucketIndex: number;
    tileID: OverscaledTileID;
    featureSortOrder: ?Array<number>
    // ... 可読性のため割愛
}
```

#### BucketPart

定義: [symbol/placement.js#L183-L188](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L183-L188)
```ts
export type BucketPart = {
    sortKey?: number | void,
    symbolInstanceStart: number,
    symbolInstanceEnd: number,
    parameters: TileLayerParameters
};
```

[`TileLayerParameters`](#TileLayerParameters)もご覧ください。

#### TileLayerParameters

定義: [symbol/placement.js#L169-L181](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L169-L181)
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

定義: [style/pauseable_placement.js#L62-L132](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L62-L132)

##### PauseablePlacement#continuePlacement

定義: [style/pauseable_placement.js#L89-L126](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L89-L126)

このメソッドは[`LayerPlacement#continuePlacement`](#LayerPlacement#continuePlacement)を呼び出します。

[`Style#_updatePlacement`](#Style#_updatePlacement)はこのメソッドを呼び出します([style/style.js#L1740](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L1740))。
```ts
            this.pauseablePlacement.continuePlacement(this._order, this._layers, layerTiles);
```

#### LayerPlacement

定義: [style/pauseable_placement.js#L15-L60](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L15-L60)

##### LayerPlacement#continuePlacement

定義: [style/pauseable_placement.js#L32-L59](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L32-L59)

このメソッドは以下を呼び出します。
- [`Placement#getBucketParts`](#Placement#getBucketParts)
- [`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)

[`PauseablePlacement#continuePlacement`](#PauseablePlacement#continuePlacement)はこのメソッドを呼び出します([style/pauseable_placement.js#L109](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/pauseable_placement.js#L109))。
```ts
                const pausePlacement = this._inProgressLayer.continuePlacement(layerTiles[layer.source], this.placement, this._showCollisionBoxes, layer, shouldPausePlacement);
```

#### symbol_size.SizeData

定義: [symbol/symbol_size.js#L15-L32](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_size.js#L15-L32)
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

定義: [symbol/symbol_size.js#L34-L37](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_size.js#L34-L37)
```ts
export type InterpolatedSize = {|
    uSize: number,
    uSizeT: number
|};
```

#### symbol_size.evaluateSizeForZoom

定義: [symbol/symbol_size.js#L92-L118](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/symbol_size.js#L92-L118)

#### interpolate.InterpolationType

定義: [style-spec/expression/definitions/interpolate.js#L17-L20](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/expression/definitions/interpolate.js#L17-L20)
```ts
export type InterpolationType =
    { name: 'linear' } |
    { name: 'exponential', base: number } |
    { name: 'cubic-bezier', controlPoints: [number, number, number, number] };
```

#### Interpolate.interpolationFactor

定義: [style-spec/expression/definitions/interpolate.js#L45-L57](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/expression/definitions/interpolate.js#L45-L57)

#### interpolate.exponentialInterpolation

定義: [style-spec/expression/definitions/interpolate.js#L255-L266](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/expression/definitions/interpolate.js#L255-L266)

#### util.interpolate

定義: [style-spec/util/interpolate.js#L5-L7](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style-spec/util/interpolate.js#L5-L7)
```ts
export function number(a: number, b: number, t: number): number {
    return (a * (1 - t)) + (b * t);
}
```

#### util.clamp

定義: [util/util.js#L211-L213](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/util/util.js#L211-L213)
```ts
export function clamp(n: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, n));
}
```

#### SymbolInstanceArray

定義: [data/array_types.js#L1188-L1198](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/array_types.js#L1188-L1198)

この配列の各要素は[`SymbolInstanceStruct`](#SymbolInstanceStruct)です。

#### SymbolInstanceStruct

定義: [data/array_types.js#L1146-L1179](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/array_types.js#L1146-L1179)

#### CollisionArrays

定義: [data/bucket/symbol_bucket.js#L90-L99](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L90-L99)
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