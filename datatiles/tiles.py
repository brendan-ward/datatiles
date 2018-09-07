from functools import partial
import os
import math
import json
from tempfile import TemporaryDirectory

from affine import Affine
import mercantile
import numpy as np

import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from progress.counter import Counter

from datatiles.rgb import hex_to_rgb
from datatiles.png import to_smallest_png, to_paletted_png
from datatiles.raster import (
    get_geo_bounds,
    get_mbtiles_meta,
    get_default_max_zoom,
    to_indexed_tif,
)


def read_tiles(src, min_zoom=0, max_zoom=None, tile_size=256):
    """This function is a generator that reads all tiles 
    that overlap with the extent of src between min_zoom and max_zoom.
    
    Parameters
    ----------
    src : rasterio.DatasetReader
        Input dataset, opened for reading
    min_zoom : int, optional (default 0)
    max_zoom : int, optional (default None)
        If None, max_zoom will be calculated based on the extent of src
    tile_size : int, optional (default 256)
        length and width of tile
    
    Yields
    ------
    tile (mercantile.Tile), tile data (of shape (tile_size, tile_size)), and tile transform
    """

    def _read_tile(vrt, tile, tile_size=256):
        """Read a tile of data from the VRT.

        If the tile bounds fall outside the vrt bounds, we have to calculate
        offsets and widths ourselves (because WarpedVRT does not allow boundless reads)
        and paste the data that were read into an otherwise blank tile (filled with Nodata value).
        
        Parameters
        ----------
        vrt : rasterio.WarpedVRT
            WarpedVRT initialized from the data source.  Example:
                with WarpedVRT(
                    src,
                    crs="EPSG:3857",
                    nodata=src.nodata,
                    resampling=Resampling.nearest,
                    width=tile_size,
                    height=tile_size,
                ) as vrt
        tile : mercantile.Tile
            Tile object describing z, x, y coordinates
        tile_size : int, optional (default 256)
            length and width of tile   

        Returns
        -------
        tuple of numpy array of data with shape (tile_size, tile_size), tile transform object
        """

        tile_bounds = mercantile.xy_bounds(*tile)
        window = vrt.window(*tile_bounds)

        dst_transform = vrt.window_transform(window)
        scaling = Affine.scale(window.width / tile_size, window.height / tile_size)
        dst_transform *= scaling

        x_res = abs(dst_transform.a)
        y_res = abs(dst_transform.e)

        left_offset = max(int(round((vrt.bounds[0] - tile_bounds[0]) / x_res, 0)), 0)
        right_offset = max(int(round((tile_bounds[2] - vrt.bounds[2]) / x_res, 0)), 0)

        bottom_offset = max(int(round((vrt.bounds[1] - tile_bounds[1]) / y_res, 0)), 0)
        top_offset = max(int(round((tile_bounds[3] - vrt.bounds[3]) / y_res, 0)), 0)

        width = tile_size - left_offset - right_offset
        height = tile_size - top_offset - bottom_offset

        data = vrt.read(out_shape=(1, height, width), window=window)

        if width != tile_size or height != tile_size:
            # Create a blank tile (filled with nodata) and paste in data
            out = np.empty((1, tile_size, tile_size), dtype=vrt.dtypes[0])
            out.fill(vrt.nodata)
            out[
                0,
                top_offset : top_offset + data.shape[1],
                left_offset : left_offset + data.shape[2],
            ] = data
            data = out

        return data[0], dst_transform

    with WarpedVRT(
        src,
        crs="EPSG:3857",
        nodata=src.nodata,
        resampling=Resampling.nearest,
        width=tile_size,
        height=tile_size,
    ) as vrt:

        if max_zoom is None:
            get_default_max_zoom(src)

        tiles = mercantile.tiles(*get_geo_bounds(src), range(min_zoom, max_zoom + 1))

        for tile in Counter("Extracting tiles...    ").iter(tiles):
            data, transform = _read_tile(vrt, tile, tile_size)
            yield tile, data, transform


def tif_to_tiles(
    infilename,
    outpath,
    min_zoom,
    max_zoom,
    tile_size=256,
    tile_renderer=to_smallest_png,
):
    """Convert a tif to image tiles, rendered according to tile_renderer.

    By default, tiles are rendered as data using the smallest PNG image type.

    Images will be stored in subdirectories under path:
    <outpath>/<zoom>/<x>/<y>.png
    
    Note: tile x,y,z coordinates follow the XYZ scheme to match their numbering in an mbtiles file.

    Parameters
    ----------
    infilename : path to input GeoTIFF file
    path : root path of output tiles
    min_zoom : int, optional (default: 0)
    max_zoom : int, optional (default: None, which means it will automatically be calculated from extent)
    tile_size : int, optional (default: 256)
    tile_renderer : function, optional (default: to_smallest_png)
        function that takes as input the data array for the tile and returns a PNG
    """

    with rasterio.open(infilename) as src:

        for tile, data, transform in read_tiles(
            src, min_zoom=min_zoom, max_zoom=max_zoom, tile_size=tile_size
        ):
            # Only write non-empty tiles
            if not np.all(data == src.nodata):

                # flip tile Y to match xyz scheme
                tiley = int(math.pow(2, tile.z)) - tile.y - 1

                outfilename = "{path}/{z}/{x}/{y}.png".format(
                    path=outpath, z=tile.z, x=tile.x, y=tile.y
                )
                outdir = os.path.dirname(outfilename)
                if not os.path.exists(outdir):
                    os.makedirs(outdir)

                with open(outfilename, "wb") as out:
                    out.write(tile_renderer(data))


def render_tif_to_tiles(
    infilename, outpath, colormap, min_zoom, max_zoom, tile_size=256
):
    """Convert a tif to image tiles, rendered according to the colormap.

    The tif is first converted into an indexed image that matches the number of colors in the colormap,
    and all values not in the colormap are masked out.

    Images will be stored in subdirectories under path:
    <outpath>/<zoom>/<x>/<y>.png
    
    Note: tile x,y,z coordinates follow the XYZ scheme to match their numbering in an mbtiles file.

    Parameters
    ----------
    infilename : path to input GeoTIFF file
    path : root path of output tiles
    colormap : dict of values to hex color codes
    min_zoom : int, optional (default: 0)
    max_zoom : int, optional (default: None, which means it will automatically be calculated from extent)
    """

    # palette is created as a series of r,g,b values.  Positions correspond to the index
    # of each value in the image
    values = sorted(colormap.keys())
    palette = np.array([hex_to_rgb(colormap[value]) for value in values], dtype="uint8")

    with TemporaryDirectory() as tmpdir:
        with rasterio.Env() as env:
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

            paletted_renderer = partial(
                to_paletted_png, palette=palette, nodata=src.nodata
            )
            tif_to_tiles(
                indexedfilename,
                outpath,
                min_zoom,
                max_zoom,
                tile_size,
                tile_renderer=paletted_renderer,
            )
