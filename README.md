# datatiles

Convert raster data to data tiles.

WARNING: UNDER HEAVY DEVELOPMENT AND SUBJECT TO MAJOR BREAKING CHANGES

Data tiles are a way of encoding multiple raster data layers into a single layer PNG for transport to the browser. Once in the browser, the tiles are decoded to original values.

Tiles are currently packaged into 8-bit grayscale or 24-bit RGB PNG files.

## Why?

We needed to display pixel values at a location across multiple layers. We wanted to update these in near real time based on user interaction such as panning or clicking on the map, in order to provide a highly dynamic data exploration interface.

The traditional web GIS approach is to use a full-featured mapserver that provicdes a query / identify API, which takes a location as input and returns information about that location across one or more data layers. Unfortunately, that is non-ideal for a couple reasons:

-   due to the round-trip latency of making these requests to a server, that information is hard to update in near real-time due to user interaction. This means that the user interaction would need to be handled differently and follow more traditional approaches such as clicking on the map and waiting for the response.
-   a full-featured mapserver is complex to setup and may require licenses. Our ideal setup uses the tiniest tile server stack possible, [mbtileserver](https://github.com/consbio/mbtileserver).

RGB encoding schemes for elevation data (e.g., [Mapbox elevation tiles](https://www.mapbox.com/help/access-elevation-data/)) demonstrate that it is possible to encode data into PNG tiles and decode within the browser.

## Basic approach

The core idea of data tiles is to use an encoding to "stack" multiple raster data tiles into a single layer and cut stacked values into PNG tiles. Once received in the browser, the RGB values can be decoded back into data values.

One way to stack data layers into a single layer is to use an exponential encoder. Given a `base` and values for each layer at a pixel (`a`, `b`, `c`, `d`), we can encode data by multiplying the original values by base raised to a power corresponding to the 0-based index of that value. Example:

```
output = a + (b * base) + (c * (base ** 2)) + (d * (base ** 3))
```

All values must be unsigned integers between `0` and `base` in order for this approach to work. This means that we can vary `base` based on the value range of the data to create a fairly compact encoding: we can have several binary data layers stacked into a single PNG, or a few layers with more values.

The final `output` value can be encoded as either 8-bit grayscale or 24-bit RGB data and cut into tiles.

To decode, we reverse the process. First, we convert the RGBA values from the `canvas` back into an unsigned integer using bit-shifting (note: alpha is discarded, see below). To do so, you need to know if the original value was 8 or 24 bits. From there, we iteratively decode values:

```
remainder_d = output % (base ** 3)
d = (output - remainder_d) / (base ** 3)

remainder_c = remainder_d % (base ** 2)
c = (remainder_d - remainder_c) / (base ** 2)

a = remainder_c % base
b = (remainder_c - a) / base
```

This approach does not allow random access to values from a single layer; all values must be decoded at once.

Other encoders are currently being investigated.

### Unique values

In order to make the encoding more compact, you can convert the original values to indexed values. The indexed values are then encoded, and the table of indices to values is provided as part of the encoding. For example, the values `1, 10, 42, 97` would require a base of at least `97`, which is very inefficient. Instead, these values can be stored using their index in array (e.g., value 1 is index 0, 42 is index 2, etc). This only requires a base of `4` which is much more compact.

### Nodata values

In practice, we handle `nodata` values in the source data in 2 ways:

-   nodata for a single layer is stored as `base - 1`. These are decoded to `null` for that layer.
-   nodata present in all layers is stored as the max of that data type - 1 (8-bit is `255`, 24-bit is `16777215`). In this case, `null` is returned instead of an object.

### Encoding metadata

In order to decode RGB values to their original values, we need to know the basic encoding information that was used when the tiles were created.

Example:

```
{
    "type": "exponential",
    "base": 8,
    "dtype": "uint16",
    "nodata": 65535,
    "layers": [
        {
            "id": "layer1",
            "nodata": 7,
            "type": "indexed",
            "values": [1, 2, 3, 4, 5]
        },
        {
            "id": "layer2",
            "nodata": 7,
            "type": "indexed",
            "values": [10, 20, 30, 40, 50]
        }
    ]
}
```

Note: `exponential` is currently the only supported encoder; others are planned.

### Reduced size tiles

The default tile size is 256 x 256. However, this is most likely unnecessary precision when responding to user interactions on the frontend, so instead we can create smaller tiles. Leaflet automatically stretches the display of these tiles to 256 x 256, and we do the same when decoding values.

In practice, we found 1/2 resolution tiles (128 x 128) achieve a reasonable balance between tile size and precision. You can vary this down further based on the nature of your data and use case.

## Installation and usage

TODO

## Limitations

Due to issues with RGBA decoding, RGBA PNGs are not currently supported. This is because different browsers apply gamma correction differently for RGBA PNG files, which means that the RGBA values derived from the image no longer match the values used when encoding the data tiles. Unfortunately, this completely breaks the decoding process.

Supported formats are 8-bit grayscale and 24-bit RGB PNG tiles.

## Development

TODO

## Credits:

This project was supported in part by a grant from the [South Atlantic Landscape Conservation Cooperative](http://southatlanticlcc.org/).

The core idea of datatiles was inspired by encoded elevation data, such as [Mapbox elevation tiles](https://www.mapbox.com/help/access-elevation-data/).
