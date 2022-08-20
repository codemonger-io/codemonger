+++
title = "Mapboxの非表示シンボルを扱う (1. 衝突ボックス編)"
description = "シリーズ:Mapboxで非表示になっているシンボルを扱うライブラリの開発について"
date = 2022-08-20
draft = false
[extra]
hashtags = ["Mapbox", "mapbox-gl-js"]
thumbnail_name = "thumbnail.png"
+++

[Mapbox GL JS](https://docs.mapbox.com/mapbox-gl-js/guides/)の画面上で別のシンボルに隠されたシンボルを扱うユーティリティライブラリを開発中です。
これはライブラリの開発過程を紹介するシリーズの最初のブログ投稿です。

<!-- more -->

## 背景

[Mapbox GL JS (`mapbox-gl-js`)](https://docs.mapbox.com/mapbox-gl-js/guides/)は[Mapbox](https://www.mapbox.com)のマップをウェブブラウザ上に表示するためのJavaScriptライブラリです。
`mapbox-gl-js`はMapboxのプロプライエタリなライブラリですが、オープンソース化されており彼らのサービス規約に沿う限り改変することができます。

[Symbol Layer](https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/#symbol)を使用するとマップ上の点に任意のシンボルを表示することができます。
以下の画像は私が開発中のアプリのスクリーンショットで、落とし物のアイコンが「シンボル」です。
![シンボルの例](./symbols-example.png)

シンボルが画面上で重なると、`mapbox-gl-js`は最初のものだけ表示し他の重なっているものは非表示にします。
私の知っている限り、画面上で特定のシンボルに隠されたシンボルを取得するAPIは`mapbox-gl-js`にありません\*。
私のアプリではクリックされた場所のシンボルを非表示のものも含めてすべてリストしたいので、これでは不都合です。
`mapbox-gl-js`に衝突検出をスキップさせてシンボルをもれなく画面上に表示する[オプション](https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/#layout-symbol-icon-allow-overlap)はありますが、重なるシンボルが多い場合はマップがごちゃごちゃし過ぎてしまうでしょう。

ということで**Mapboxのマップ上で特定のシンボルと重なるシンボルを集約することのできるライブラリを開発**することにしました。

\* [`Map#queryRenderedFeatures`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#queryrenderedfeatures)は表示されているシンボル(Feature)だけを返し非表示のものは返しません。
[`"click"`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map.event:click)イベントも非表示のシンボルについては教えてくれません。

## ライブラリに対する要件

私が開発中のライブラリを使うと、**特定のLayerで指定したボックスと交差するシンボルを表示の有無にかかわらず問い合わせることができます**。

上記機能に基づき、**特定のLayerでクリックされたシンボルに隠されているシンボルを問い合わせることができます**。

問題を単純化するため、ラベル(Text)のないシンボルのみ(アイコンのみ)を考えることにします。

## 衝突検出

`mapbox-gl-js`はどのシンボルを画面に描画するか決めるために衝突検出を行います。
[`Map#showCollisionBoxes`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#showcollisionboxes)プロパティを有効にすると、`mapbox-gl-js`は画面上に表示・非表示のシンボルすべての衝突ボックスを可視化します。
以下は衝突ボックス(とサークル)をMapboxのマップ上に表示する例です。
![衝突ボックスの例](./collision-boxes-example.png)

これらの衝突ボックスの位置と寸法をシンボルの[Feature](#Feature)と一緒に取得できれば、ライブラリを実装できます。

## 衝突ボックスを取得する

衝突ボックスを取得できるかどうか調べるために[`mapbox-gl-js`のソースコード](https://github.com/mapbox/mapbox-gl-js/tree/v2.9.2)\*を眺めていきましょう。

\* 当時の最新[バージョン2.9.2](https://github.com/mapbox/mapbox-gl-js/tree/v2.9.2)を分析しました。

### デバッグのための衝突ボックス

[`Map#showCollisionBoxes`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#showcollisionboxes)を有効にしたときに描画される衝突ボックスの情報に[`Map#showCollisionBoxes`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#showcollisionboxes)を`false`にした製品版環境でもアクセスできるでしょうか?
残念ながら、答えは**ノー**です。

[`SymbolBucket#textCollisionBox`](#SymbolBucket#textCollisionBox)と[`SymbolBucket#iconCollisionBox`](#SymbolBucket#iconCollisionBox)がすべての描画された衝突ボックスの情報を含んでいます。
[`SymbolBucket#updateCollisionBuffers`](#SymbolBucket#updateCollisionBuffers)が[`SymbolBucket#textCollisionBox`](#SymbolBucket#textCollisionBox)と[`SymbolBucket#iconCollisionBox`](#SymbolBucket#iconCollisionBox)を更新しており、[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)が[symbol/placement.js#L435-L437](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L435-L437)でそれを呼び出しています:
```js
        if (showCollisionBoxes && updateCollisionBoxIfNecessary) {
            bucket.updateCollisionDebugBuffers(this.transform.zoom, collisionBoxArray);
        }
```

上記コードから分かるとおり、当該メソッドは`showCollisionBoxes`(= [`Map#showCollisionBoxes`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#showcollisionboxes))が`true`の場合のみ呼び出されています。
製品版では[`Map#showCollisionBoxes`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#showcollisionboxes)は`false`のはずなので、[`SymbolBucket#textCollisionBox`](#SymbolBucket#textCollisionBox)と[`SymbolBucket#iconCollisionBox`](#SymbolBucket#iconCollisionBox)に頼ることはできません。
もしこれらを使うことができたとしても、[タイル座標系](#タイル座標系(空間))で表されているので画面座標系に射影しなければなりません。

### 衝突ボックスの別の入手元

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)はシンボルの衝突検出を担っています。
その内部関数[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)が各シンボルを処理しています。
さらにその内部関数の[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)を呼び出してアイコンが画面上で優先するシンボルと衝突しているかどうか判定しています。
[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)は[symbol/placement.js#L709-L710](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L709-L710)で[`CollisionIndex#placeCollisionBox`](#CollisionIndex#placeCollisionBox)を呼び出しており、それが実際の衝突判定を行っています:
```js
                    return this.collisionIndex.placeCollisionBox(bucket, iconScale, iconBox, shiftPoint,
                        iconAllowOverlap, textPixelRatio, posMatrix, collisionGroup.predicate);
```

衝突が検出されなければ、[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)は当該シンボルの衝突ボックスを[`CollisionIndex#insertCollisionBox`](#CollisionIndex#insertCollisionBox)で記憶します。
残念ながら、他の優先する衝突ボックスと衝突するシンボルの衝突ボックスは記録しません。
なのでそれらのシンボルについて衝突ボックスを再計算しなければなりません。

ということで、次の節では画面座標系で衝突ボックスをどのように計算しているか理解するために[`CollisionIndex#placeCollisionBox`](#CollisionIndex#placeCollisionBox)を覗いてみましょう。

### CollisionIndex#placeCollisionBoxの解剖

以下は[`CollisionIndex#placeCollisionBox`](#CollisionIndex#placeCollisionBox)の大まかな流れを示しています。
1. [symbol/collision_index.js#L97-L99](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L97-L99)で、衝突ボックスの位置を[タイル空間](#タイル座標系(空間))で取得:

    ```js
        let anchorX = collisionBox.projectedAnchorX;
        let anchorY = collisionBox.projectedAnchorY;
        let anchorZ = collisionBox.projectedAnchorZ;
    ```
2. [symbol/collision_index.js#L104-L111](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L104-L111)で、標高(Elevation)の処理:

    ```js
        if (elevation && tileID) {
            const up = bucket.getProjection().upVector(tileID.canonical, collisionBox.tileAnchorX, collisionBox.tileAnchorY);
            const upScale = bucket.getProjection().upVectorScale(tileID.canonical, this.transform.center.lat, this.transform.worldSize).metersToTile;

            anchorX += up[0] * elevation * upScale;
            anchorY += up[1] * elevation * upScale;
            anchorZ += up[2] * elevation * upScale;
        }
    ```

   `anchorX`, `anchorY`, `anchorZ`を標高で調整。
3. [symbol/collision_index.js#L114](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L114)で、アンカーを画面座標系に射影:

    ```js
        const projectedPoint = this.projectAndGetPerspectiveRatio(posMatrix, [anchorX, anchorY, anchorZ], collisionBox.tileID, checkOcclusion, bucket.getProjection());
    ```

   概説すると、[`CollisionIndex#projectAndGetPerspectiveRatio`](#CollisionIndex#projectAndGetPerspectiveRatio)は[`posMatrix`](#パラメータ:_posMatrix)を点(`[anchorX, anchorY, anchorZ]`)にかけてパースを修正します。
4. [symbol/collision_index.js#L116-L120](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L116-L120)で、衝突ボックスをスケールして`projectedPoint.point`に移動:

    ```js
        const tileToViewport = textPixelRatio * projectedPoint.perspectiveRatio;
        const tlX = (collisionBox.x1 * scale + shift.x - collisionBox.padding) * tileToViewport + projectedPoint.point.x;
        const tlY = (collisionBox.y1 * scale + shift.y - collisionBox.padding) * tileToViewport + projectedPoint.point.y;
        const brX = (collisionBox.x2 * scale + shift.x + collisionBox.padding) * tileToViewport + projectedPoint.point.x;
        const brY = (collisionBox.y2 * scale + shift.y + collisionBox.padding) * tileToViewport + projectedPoint.point.y;
    ```
5. [symbol/collision_index.js#L125-L142](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L125-L142)で、衝突ボックス(`[tlX, tlY, brX, brY]`)が以前に記録した衝突ボックスと衝突するかどうかを判定。
   このステップはスコープ外です。

上記の計算(ステップ1から4)を模倣するためには、以下のパラメータを用意しなければなりません。
- [`collisionBox`](#パラメータ:_collisionBox)
- [`posMatrix`](#パラメータ:_posMatrix)
- [`elevation`](#パラメータ:_elevation)
- [`textPixelRatio`](#パラメータ:_textPixelRatio)
- [`scale`](#パラメータ:_scale)
- [`shift`](#パラメータ:_shift)

私の分析では、[`Placement`](#Placement), [`Tile`](#Tile), [`SymbolBucket`](#SymbolBucket)が利用できれば、上記パラメータを取得することは可能です。
[`Placement`](#Placement)は[`Style#placement`](#Style#placement)として手に入り、[`Style`](#Style)は[`Map#style`](#Map#style)として手に入ります。
しかし **[`Tile`](#Tile)と[`SymbolBucket`](#SymbolBucket)の取得については更に調査が必要**です。

以下の節では分析の詳細を示します。

#### パラメータ: collisionBox

`collisionBox`は[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)に与えられる`iconBox`引数で[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)は[symbol/placement.js#L717](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L717)(と別の行)でそれを呼び出します:
```js
                    placedIconBoxes = placeIconFeature(collisionArrays.iconBox);
```

では`collisionArrays`とは何でしょうか?
`collisionArrays`は[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)の引数で[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は[symbol/placement.js#L795](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L795)(と別の行)でそれを呼び出します:
```js
                placeSymbol(bucket.symbolInstances.get(i), i, bucket.collisionArrays[i]);
```

したがって`collisionArrays`は[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)のi番目の要素です。
[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes)を[symbol/placement.js#L431-L433](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L431-L433)で呼び出して[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)を初期化していることに留意ください:
```js
        if (!bucket.collisionArrays && collisionBoxArray) {
            bucket.deserializeCollisionBoxes(collisionBoxArray);
        }
```

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は`collisionBoxArray`をメソッドの最初の引数である`bucketPart`から[symbol/placement.js#L388-L401](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L388-L401)で取得しています:
```js
        const {
            // ... 可読性のため割愛
            collisionBoxArray,
            // ... 可読性のため割愛
        } = bucketPart.parameters;
```

`bucketPart.parameters`の`collisionBoxArray`は対応する[マップタイル](#マップタイル)の[`Tile#collisionBoxArray`](#Tile#collisionBoxArray)から来ています。
詳しくは[`Placement#getBucketParts`](#Placement#getBucketParts)を参照ください。

シンボルの配置が終了した後は **[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)を使うことができます**。

#### パラメータ: posMatrix

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は`posMatrix`をメソッドの最初の引数である`bucketPart`から[symbol/placement.js#L388-L401](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L388-L401)で取得しています:
```js
        const {
            // ... 可読性のため割愛
            posMatrix,
            // ... 可読性のため割愛
        } = bucketPart.parameters;
```

[`Placement#getBucketParts`](#Placement#getBucketParts)は`posMatrix`を[symbol/placement.js#L249](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L249)で計算しています:
```js
        const posMatrix = getSymbolPlacementTileProjectionMatrix(tile.tileID, symbolBucket.getProjection(), this.transform, this.projection);
```

[`getSymbolPlacementTileProjectionMatrix`](#projection_util.getSymbolPlacementTileProjectionMatrix)は`mapbox-gl-js`からエクスポートされていませんが、**我々のバージョンを実装するのは難しくありません**。
詳しくは[`getSymbolPlacementTileProjectionMatrix`](#projection_util.getSymbolPlacementTileProjectionMatrix)を参照ください。

#### パラメータ: elevation

[`CollisionIndex#placeCollisionBox`](#CollisionIndex#placeCollisionBox)は`elevation`を[symbol/collision_index.js#L102](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L102)で取得しています:
```js
        const elevation = collisionBox.elevation;
```

[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)は[`updateBoxData`](#Placement#placeLayerBucketPart.placeSymbol.updateBoxData)を[symbol/placement.js#L704](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L704)で呼び出し`elevation`プロパティを`iconBox`(=[`collisionBox`](#パラメータ:_collisionBox))に追加しています:
```js
                    updateBoxData(iconBox);
```

[`updateBoxData`](#Placement#placeLayerBucketPart.placeSymbol.updateBoxData)は`elevation`を[symbol/placement.js#L507-L509](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L507-L509)で計算しています:
```js
                box.elevation = this.transform.elevation ? this.transform.elevation.getAtTileOffset(
                    this.retainedQueryData[bucket.bucketInstanceId].tileID,
                    box.tileAnchorX, box.tileAnchorY) : 0;
```

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)の要素を直接[`updateBoxData`](#Placement#placeLayerBucketPart.placeSymbol.updateBoxData)に渡しているので、シンボルの配置が終わった後は **[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)の各要素の`iconBox`が`elevation`を記憶しているはず**です。

以下もご覧ください。
- [`Transform#elevation`](#Transform#elevation)
- [`Elevation#getAtTileOffset`](#Elevation#getAtTileOffset)
- [`Placement#retainedQueryData`](#Placement#retainedQueryData)

#### パラメータ: textPixelRatio

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は`textPixelRatio`をメソッドの最初の引数である`bucketPart`から[symbol/placement.js#L388-L401](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L388-L401)で取得しています:
```js
        const {
            // ... 可読性のため割愛
            textPixelRatio,
            // ... 可読性のため割愛
        } = bucketPart.parameters;
```

[`Placement#getBucketParts`](#Placement#getBucketParts)は`textPixelRatio`を[symbol/placement.js#L244](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L244)で計算しています:
```js
        const textPixelRatio = tile.tileSize / EXTENT;
```

[`Tile#tileSize`](#Tile#tileSize)と[`EXTENT`](#EXTENT)もご覧ください。
**このパラメータの計算は朝飯前です**。

#### パラメータ: scale

[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)は`iconScale`(=`scale`)を[symbol/placement.js#L708](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L708)で計算しています:
```js
                    const iconScale = bucket.getSymbolInstanceIconSize(partiallyEvaluatedIconSize, this.transform.zoom, symbolIndex);
```

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は`partiallyEvaluatedIconSize`をメソッドの最初の引数である`bucketPart`から[symbol/placement.js#L388-L401](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L388-L401)で取得しています:
```js
        const {
            // ... 可読性のため割愛
            partiallyEvaluatedIconSize,
            // ... 可読性のため割愛
        } = bucketPart.parameters;
```

[`Placement#getBucketParts`](#Placement#getBucketParts)は`partiallyEvaluatedIconSize`を[symbol/placement.js#L317](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L317)で計算しています:
```js
            partiallyEvaluatedIconSize: symbolSize.evaluateSizeForZoom(symbolBucket.iconSizeData, this.transform.zoom),
```

詳しくは[`SymbolBcuket#getSymbolInstanceIconSize`](#SymbolBucket#getSymbolInstanceIconSize)を参照ください。.

**`partiallyEvaluatedIconSize`は再現することができ、このパラメータを計算することができます**。

#### パラメータ: shift

[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)は`shiftPoint`(=`shift`)を[symbol/placement.js#L705-L707](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L705-L707)で計算しています:
```js
                    const shiftPoint: Point = hasIconTextFit && shift ?
                        offsetShift(shift.x, shift.y, rotateWithMap, pitchWithMap, this.transform.angle) :
                        new Point(0, 0);
```

上記コードの`shift`は in[src/symbol/placement.js#L609](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L609)で設定されています:
```js
                                    shift = result.shift;
```

`hasIconFit`は[symbol/placement.js#L409](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L409)で設定されています:
```js
        const hasIconTextFit = layout.get('icon-text-fit') !== 'none';
```

ラベルのないアイコンにフォーカスするので**このパラメータは`Point(0, 0)`であると想定できます**。

## まとめ

非表示シンボルの衝突ボックスを画面座標系で取得するお手軽な方法はありません。
しかし分析によると、[`Placement`](#Placement), [`Tile`](#Tile), [`SymbolBucket`](#SymbolBucket)が手に入ればそれぞれのシンボルの衝突ボックスを再計算することはできます。

以下の疑問が残っています。
- [`Tile`](#Tile)と[`SymbolBucket`](#SymbolBucket)はどうやって取得するのか?
- 再計算した衝突ボックスとシンボルの[Feature](#Feature)をどうやって対応づけるのか?

ということで、次のブログ投稿ではこれらの疑問に答えます。

## 補足

### 用語

この節では`mapbox-gl-js`特有の用語を簡単に解説します。

#### Feature

Layerのデータソースとして利用するVector Tileと[GeoJSON](https://docs.mapbox.com/mapbox-gl-js/api/sources/#geojsonsource)はFeatureの集合です。
Featureは形状(ジオメトリ)とオプションのプロパティを持ちます。

#### Layer

`mapbox-gl-js`はマップをLayerのスタックとして表します。
Layerのタイプはいくつかあり、["Symbol" Layer](https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/#symbol)はそのひとつです。
詳しくは[「Layers|Style specification」](https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/)[[1]](#Reference)を参照ください。

#### マップタイル

`mapbox-gl-js`は世界をマップタイルのグリッドに分ます。

#### タイル座標系(空間)

[map tile](#マップタイル)のジオメトリはローカルな座標系(タイル座標系)で表されます。
詳しくは[「Vector tiles standards」](https://docs.mapbox.com/data/tilesets/guides/vector-tiles-standards/)[[2]](#Reference)を参照ください。

### ソースコードレファレンス

この節では`mapbox-gl-js`のソースコードに関する私の補足コメントを紹介します。

#### Map

定義: [ui/map.js#L326-L3677](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L326-L3677)

`mapbox-gl-js`を使うためにインスタンス化する最初のクラスです。

##### Map#style

定義: [ui/map.js#L327](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/ui/map.js#L327)
```js
    style: Style;
```

このプロパティはすべてのマップデータを管理します。

[`Style`](#Style)もご覧ください。

#### Style

定義: [style/style.js#L135-L1860](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L135-L1860)

##### Style#placement

定義: [style/style.js#L173](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/style/style.js#L173)
```js
    placement: Placement;
```

[`Placement`](#Placement)もご覧ください。

#### Tile

定義: [source/tile.js#L95-L799](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L95-L799)

##### Tile#tileSize

定義: [src/source/tile.js#L99](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L99)
```js
    tileSize: number;
```

##### Tile#collisionBoxArray

定義: [source/tile.js#L115](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/source/tile.js#L115)
```js
    collisionBoxArray: ?CollisionBoxArray;
```

#### Placement

定義: [symbol/placement.js#L192-L1184](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L192-L1184)

[`Style`](#Style)は`Placement`のインスタンスを[`Style#placement`](#Style#placement)として保持します。

##### Placement#retainedQueryData

定義: [symbol/placement.js#L205](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L205)
```js
    retainedQueryData: {[_: number]: RetainedQueryData};
```

このプロパティは[`SymbolBucket`](#SymbolBucket)(Bucket)を[`RetainedQueryData`](#RetainedQueryData)と対応づけます。

[`Placement#getBucketParts`](#Placement#getBucketParts)は新しい[`RetainedQueryData`](#RetainedQueryData)をBucketに[symbol/placement.js#L297-L303](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L297-L303)で割り当てます:
```js
        this.retainedQueryData[symbolBucket.bucketInstanceId] = new RetainedQueryData(
            symbolBucket.bucketInstanceId,
            bucketFeatureIndex,
            symbolBucket.sourceLayerIndex,
            symbolBucket.index,
            tile.tileID
        );
```

このプロパティは[`SymbolBucket`](#SymbolBucket)に対応する[`FeatureIndex`](#FeatureIndex)(`bucketFeatureIndex`)を取得するのに必要です。

##### Placement#getBucketParts

定義: [symbol/placement.js#L233-L333](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L233-L333)

このメソッドは[`getSymbolPlacementTileProjectionMatrix`](#projection_util.getSymbolPlacementTileProjectionMatrix)を呼び出しタイルから画面座標系への射影マトリクスを計算します。

##### projection_util.getSymbolPlacementTileProjectionMatrix

定義: [geo/projection/projection_util.js#L35-L41](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/geo/projection/projection_util.js#L35-L41)
```js
export function getSymbolPlacementTileProjectionMatrix(coord: OverscaledTileID, bucketProjection: Projection, transform: Transform, runtimeProjection: string): Float32Array {
    if (bucketProjection.name === runtimeProjection) {
        return transform.calculateProjMatrix(coord.toUnwrapped());
    }
    assert(transform.projection.name === bucketProjection.name);
    return reconstructTileMatrix(transform, bucketProjection, coord);
}
```

##### Placement#placeLayerBucketPart

定義: [symbol/placement.js#L386-L808](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L386-L808)

このメソッドはシンボルの衝突検出を担います。

このメソッドは[symbol/placement.js#L786-L797](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L786-L797)で[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)を各シンボルについて呼び出します:
```js
        if (zOrderByViewportY) {
            assert(bucketPart.symbolInstanceStart === 0);
            const symbolIndexes = bucket.getSortedSymbolIndexes(this.transform.angle);
            for (let i = symbolIndexes.length - 1; i >= 0; --i) {
                const symbolIndex = symbolIndexes[i];
                placeSymbol(bucket.symbolInstances.get(symbolIndex), symbolIndex, bucket.collisionArrays[symbolIndex]);
            }
        } else {
            for (let i = bucketPart.symbolInstanceStart; i < bucketPart.symbolInstanceEnd; i++) {
                placeSymbol(bucket.symbolInstances.get(i), i, bucket.collisionArrays[i]);
            }
        }
```

##### Placement#placeLayerBucketPart.placeSymbol

定義: [symbol/placement.js#L439-L784](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L439-L784)

これは[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)の内部関数です。

この関数は与えられたシンボルについて衝突判定と配置を行います。

この関数はアイコンの衝突判定のために[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)を呼び出します。

##### Placement#placeLayerBucketPart.placeSymbol.placeIconFeature

定義: [symbol/placement.js#L703-L711](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L703-L711)
```js
                const placeIconFeature = iconBox => {
                    updateBoxData(iconBox);
                    const shiftPoint: Point = hasIconTextFit && shift ?
                        offsetShift(shift.x, shift.y, rotateWithMap, pitchWithMap, this.transform.angle) :
                        new Point(0, 0);
                    const iconScale = bucket.getSymbolInstanceIconSize(partiallyEvaluatedIconSize, this.transform.zoom, symbolIndex);
                    return this.collisionIndex.placeCollisionBox(bucket, iconScale, iconBox, shiftPoint,
                        iconAllowOverlap, textPixelRatio, posMatrix, collisionGroup.predicate);
                };
```

これは[`placeSymbol`](#Placement#placeLayerBucketPart.placeSymbol)の内部関数です。

この関数は`iconBox`を[タイル座標系](#タイル座標系(空間))から画面座標系に射影し、その射影したボックスについて衝突判定を行います。

以下もご覧ください。
- [`updateBoxData`](#Placement#placeLayerBucketPart.placeSymbol.updateBoxData)
- [`SymbolBucket#getSymbolInstanceIconSize`](#SymbolBucket#getSymbolInstanceIconSize)
- [`CollisionIndex#placeCollisionBox`](#CollisionIndex#placeCollisionBox)

##### Placement#placeLayerBucketPart.placeSymbol.updateBoxData

定義: [symbol/placement.js#L504-L510](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L504-L510)
```js
            const updateBoxData = (box: SingleCollisionBox) => {
                box.tileID = this.retainedQueryData[bucket.bucketInstanceId].tileID;
                if (!this.transform.elevation && !box.elevation) return;
                box.elevation = this.transform.elevation ? this.transform.elevation.getAtTileOffset(
                    this.retainedQueryData[bucket.bucketInstanceId].tileID,
                    box.tileAnchorX, box.tileAnchorY) : 0;
            };
```

これは[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)の内部関数です。

#### RetainedQueryData

定義: [symbol/placement.js#L87-L105](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/placement.js#L87-L105)
```js
export class RetainedQueryData {
    bucketInstanceId: number;
    featureIndex: FeatureIndex;
    sourceLayerIndex: number;
    bucketIndex: number;
    tileID: OverscaledTileID;
    featureSortOrder: ?Array<number>
    // ... truncated for simplicity
}
```

#### FeatureIndex

定義: [data/feature_index.js#L54-L312](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/feature_index.js#L54-L312)

`FeatureIndex`はシンボルの[Feature](#Feature)を解決する上で重要な役割を果たします。

#### SymbolBucket

定義: [data/bucket/symbol_bucket.js#L352-L1119](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L352-L1119)

##### SymbolBucket#collisionArrays

定義: [data/bucket/symbol_bucket.js#L380](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L380)
```js
    collisionArrays: Array<CollisionArrays>;
```

[`SymbolBucket#deserializeCollisionBoxes`](#SymbolBucket#deserializeCollisionBoxes)がこのプロパティを初期化します。

[`CollisionArrays`](#CollisionArrays)もご覧ください。

##### SymbolBucket#textCollisionBox

定義: [data/bucket/symbol_bucket.js#L398](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L398)
```js
    textCollisionBox: CollisionBuffers;
```

このプロパティはすべてのテキストラベルの衝突ボックスを格納します。

##### SymbolBucket#iconCollisionBox

定義: [data/bucket/symbol_bucket.js#L399](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L399)
```js
    iconCollisionBox: CollisionBuffers;
```

このプロパティはすべてのアイコンの衝突ボックスを格納します。

##### SymbolBucket#deserializeCollisionBoxes

定義: [data/bucket/symbol_bucket.js#L979-L995](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L979-L995)

このメソッドは[`SymbolBucket#collisionArrays`](#SymbolBucket#collisionArrays)を初期化します。

##### SymbolBucket#getSymbolInstanceIconSize

Definition: [data/bucket/symbol_bucket.js#L882-L887](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L882-L887)
```js
    getSymbolInstanceIconSize(iconSize: any, zoom: number, index: number): number {
        const symbol: any = this.icon.placedSymbolArray.get(index);
        const featureSize = symbolSize.evaluateSizeForFeature(this.iconSizeData, iconSize, symbol);

        return this.tilePixelRatio * featureSize;
    }
```

##### SymbolBucket#updateCollisionBuffers

定義: [data/bucket/symbol_bucket.js#L914-L939](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L914-L939)

[`Placement#placeLayerBucketPart`](#Placement#placeLayerBucketPart)は[`Map#showCollisionBoxes`](https://docs.mapbox.com/mapbox-gl-js/api/map/#map#showcollisionboxes)が`true`の場合のみこのメソッドを呼び出します。

#### CollisionArrays

定義: [data/bucket/symbol_bucket.js#L90-L99](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/bucket/symbol_bucket.js#L90-L99)
```js
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

#### CollisionIndex

定義: [symbol/collision_index.js#L64-L465](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L64-L465)

##### CollisionIndex#placeCollisionBox

定義: [symbol/collision_index.js#L94-L143](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L94-L143)
```js
    placeCollisionBox(bucket: SymbolBucket, scale: number, collisionBox: SingleCollisionBox, shift: Point, allowOverlap: boolean, textPixelRatio: number, posMatrix: Mat4, collisionGroupPredicate?: any): PlacedCollisionBox {
        assert(!this.transform.elevation || collisionBox.elevation !== undefined);

        let anchorX = collisionBox.projectedAnchorX;
        let anchorY = collisionBox.projectedAnchorY;
        let anchorZ = collisionBox.projectedAnchorZ;

        // Apply elevation vector to the anchor point
        const elevation = collisionBox.elevation;
        const tileID = collisionBox.tileID;
        if (elevation && tileID) {
            const up = bucket.getProjection().upVector(tileID.canonical, collisionBox.tileAnchorX, collisionBox.tileAnchorY);
            const upScale = bucket.getProjection().upVectorScale(tileID.canonical, this.transform.center.lat, this.transform.worldSize).metersToTile;

            anchorX += up[0] * elevation * upScale;
            anchorY += up[1] * elevation * upScale;
            anchorZ += up[2] * elevation * upScale;
        }

        const checkOcclusion = bucket.projection.name === 'globe' || !!elevation || this.transform.pitch > 0;
        const projectedPoint = this.projectAndGetPerspectiveRatio(posMatrix, [anchorX, anchorY, anchorZ], collisionBox.tileID, checkOcclusion, bucket.getProjection());

        const tileToViewport = textPixelRatio * projectedPoint.perspectiveRatio;
        const tlX = (collisionBox.x1 * scale + shift.x - collisionBox.padding) * tileToViewport + projectedPoint.point.x;
        const tlY = (collisionBox.y1 * scale + shift.y - collisionBox.padding) * tileToViewport + projectedPoint.point.y;
        const brX = (collisionBox.x2 * scale + shift.x + collisionBox.padding) * tileToViewport + projectedPoint.point.x;
        const brY = (collisionBox.y2 * scale + shift.y + collisionBox.padding) * tileToViewport + projectedPoint.point.y;
        // Clip at 10 times the distance of the map center or, said otherwise, when the label
        // would be drawn at 10% the size of the features around it without scaling. Refer:
        // https://github.com/mapbox/mapbox-gl-native/wiki/Text-Rendering#perspective-scaling
        // 0.55 === projection.getPerspectiveRatio(camera_to_center, camera_to_center * 10)
        const minPerspectiveRatio = 0.55;
        const isClipped = projectedPoint.perspectiveRatio <= minPerspectiveRatio || projectedPoint.occluded;

        if (!this.isInsideGrid(tlX, tlY, brX, brY) ||
            (!allowOverlap && this.grid.hitTest(tlX, tlY, brX, brY, collisionGroupPredicate)) ||
            isClipped) {
            return {
                box: [],
                offscreen: false,
                occluded: projectedPoint.occluded
            };
        }

        return {
            box: [tlX, tlY, brX, brY],
            offscreen: this.isOffscreen(tlX, tlY, brX, brY),
            occluded: false
        };
    }
```

[`placeIconFeature`](#Placement#placeLayerBucketPart.placeSymbol.placeIconFeature)はこのメソッドを呼び出します。

##### CollisionIndex#insertCollisionBox

定義: [symbol/collision_index.js#L401-L406](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L401-L406)
```js
    insertCollisionBox(collisionBox: Array<number>, ignorePlacement: boolean, bucketInstanceId: number, featureIndex: number, collisionGroupID: number) {
        const grid = ignorePlacement ? this.ignoredGrid : this.grid;

        const key = {bucketInstanceId, featureIndex, collisionGroupID};
        grid.insert(key, collisionBox[0], collisionBox[1], collisionBox[2], collisionBox[3]);
    }
```

##### CollisionIndex#projectAndGetPerspectiveRatio

定義: [symbol/collision_index.js#L417-L445](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/symbol/collision_index.js#L417-L445)

#### Transform

定義: [geo/transform.js#L42-L2061](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/geo/transform.js#L42-L2061)

##### Transform#elevation

定義: [geo/transform.js#L220](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/geo/transform.js#L220)

#### Elevation

定義: [terrain/elevation.js#L31-L237](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/terrain/elevation.js#L31-L237)

##### Elevation#getAtTileOffset

定義: [terrain/elevation.js#L110-L115](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/terrain/elevation.js#L110-L115)

#### 定数

##### EXTENT

定義: [data/extent.js#L18](https://github.com/mapbox/mapbox-gl-js/blob/e29e113ff5e1f4c073f84b8cbe546006d2fb604f/src/data/extent.js#L18)
```js
export default 8192;
```

この値は`EXTENT`として参照されます。

## Reference

1. [_Layers|Style specification_](https://docs.mapbox.com/mapbox-gl-js/style-spec/layers/)
2. [_Vector tiles standards_](https://docs.mapbox.com/data/tilesets/guides/vector-tiles-standards/)