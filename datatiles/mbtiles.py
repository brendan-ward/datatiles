
from functools import partial
import math
import os
from tempfile import TemporaryDirectory
from pymbtiles import MBtiles
import rasterio
import numpy as np

from datatiles.rgb import hex_to_rgb
from datatiles.png import to_smallest_png, to_paletted_png
from datatiles.tiles import read_tiles
from datatiles.raster import (
    get_geo_bounds,
    get_mbtiles_meta,
    get_default_max_zoom,
    to_indexed_tif,
)


def tif_to_mbtiles(
    infilename,
    outfilename,
    min_zoom,
    max_zoom,
    tile_size=256,
    metadata=None,
    tile_renderer=to_smallest_png,
):
    """Convert a tif to mbtiles, rendering each tile using tile_renderer.

    By default, this renders tiles as data using the smallest PNG image type
    for the data type of infilename.
    
    Parameters
    ----------
    infilename : path to input GeoTIFF file
    outfilename : path to output mbtiles file
    
    min_zoom : int
    max_zoom : int
    tile_size : int, optional (default: 256)
    metadata : dict, optional
        metadata dictionary to add to the mbtiles metadata
    tile_renderer : function, optional (default: to_smallest_png)
        function that takes as input the data array for the tile and returns a PNG
    """

    with rasterio.Env() as env:
        with rasterio.open(infilename) as src:
            with MBtiles(outfilename, mode="w") as mbtiles:
                meta = {
                    "tilejson": "2.0.0",
                    "version": "1.0.0",
                    "minzoom": min_zoom,
                    "maxzoom": max_zoom,
                }
                meta.update(get_mbtiles_meta(src, min_zoom))

                if metadata is not None:
                    meta.update(metadata)

                mbtiles.meta = meta

                for tile, data, transform in read_tiles(
                    src, min_zoom=min_zoom, max_zoom=max_zoom, tile_size=tile_size
                ):
                    # Only write out non-empty tiles
                    if not np.all(data == src.nodata):
                        # flip tile Y to match xyz scheme
                        tiley = int(math.pow(2, tile.z)) - tile.y - 1
                        mbtiles.write_tile(tile.z, tile.x, tiley, tile_renderer(data))


def render_tif_to_mbtiles(
    infilename, outfilename, colormap, min_zoom, max_zoom, metadata=None, tile_size=256
):
    """Convert a tif to mbtiles, rendered according to the colormap.

    The tif is first converted into an indexed image that matches the number of colors in the colormap,
    and all values not in the colormap are masked out.
    
    Parameters
    ----------
    infilename : path to input GeoTIFF file
    outfilename : path to output mbtiles file
    colormap : dict of values to hex color codes
    min_zoom : int, optional (default: 0)
    max_zoom : int, optional (default: None, which means it will automatically be calculated from extent)
    metadata : dict, optional
        metadata dictionary to add to the mbtiles metadata
    """

    # palette is created as a series of r,g,b values.  Positions correspond to the index
    # of each value in the image
    values = sorted(colormap.keys())
    palette = np.array([hex_to_rgb(colormap[value]) for value in values], dtype="uint8")

    with TemporaryDirectory() as tmpdir:
        with rasterio.open(infilename) as src:
            if src.count > 1:
                raise ValueError("tif must be single band")

            # Convert the image to indexed, if necessary
            unique_values = np.unique(src.read(1, masked=True))
            unique_values = [v for v in unique_values if v is not np.ma.masked]

            if len(set(unique_values).difference(values)):
                # convert the image to indexed
                print("Converting tif to indexed tif")
                indexedfilename = os.path.join(tmpdir, "indexed.tif")
                to_indexed_tif(infilename, indexedfilename, values)

            else:
                indexedfilename = infilename

        paletted_renderer = partial(to_paletted_png, palette=palette, nodata=src.nodata)
        tif_to_mbtiles(
            indexedfilename,
            outfilename,
            min_zoom,
            max_zoom,
            tile_size,
            metadata=metadata,
            tile_renderer=paletted_renderer,
        )
