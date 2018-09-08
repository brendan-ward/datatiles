
from collections import defaultdict

import numpy as np
import rasterio
from rasterio.windows import get_data_window, union, transform as transform_window

from datatiles.encoding.exponential import (
    ExponentialDecoder,
    ExponentialEncoder,
    encode as exponential_encode,
)
from datatiles.raster import has_matching_attributes, unique_to_indexed
from datatiles.utils import get_dtype, get_nodata_value


def encode_tifs(sources, outfilename, encoding="exponential"):
    """Stack and encode tifs using encoding and write to outfilename.

    TODO: eventually, each source could be of a different type.  Right now, the default type is indexed.
    
    Parameters
    ----------
    sources : dictionary of sources:  {"id": {"source": "<path to file>"}, ...}
        All sources must be single band tifs
    outfilename : name of output tif
    encoding : str, optional (default: "exponential")
    
    Returns
    -------
    dict : encoding metadata
    """

    # TODO: validation: every element in sources must have a "source" key

    inputs = {k: rasterio.open(v["source"]) for k, v in sources["sources"].items()}
    rasters = inputs.values()

    print("Validating rasters...")

    # All rasters must be single band
    for src in rasters:
        if src.count > 1:
            raise ValueError("Source must be single band: {}".format(src.name))

    # All rasters must have matching attributes
    atts = ("crs", "transform", "width", "height")
    for att in atts:
        if not has_matching_attributes(rasters, att):
            raise ValueError("Sources have different values for {}".format(att))

    print("Calculating encoding parameters...")

    # Figure out the max value for each raster, based on its type
    # for indexed types, the max value is len(unique_values) - 1

    max_values = []
    for key, src in inputs:
        data = src.read(1, masked=True)

        if sources[key].get("type", "indexed") == "indexed":
            # we reserve the last value as nodata for each set of unique values
            max_value = np.unique(data).compressed().size

        # TODO: generalize to other types
        else:
            raise NotImplementedError(
                "source type {} not implemented".format(sources[key]["type"])
            )

        max_values.append(max_value)

    if encoding == "exponential":

        # add 1 to this to save spot for NODATA, which will be max value per slot
        base = max(max_values) + 1
        print("base", base)

        max_encoded_value = exponential_encode(max_values) + 1
        target_dtype = get_dtype(max_encoded_value)
        nodata = get_nodata_value(max_encoded_value)
        layer_nodata = base - 1
        print("target dtype", target_dtype, "nodata", nodata)

        print("Encoding data...")
        encoder = ExponentialEncoder(base=base, dtype=target_dtype)
        mask = None  # nodata present across all layers
        encoding = {
            "type": "exponential",
            "base": base,
            "dtype": target_dtype,
            "nodata": nodata,
            "layers": [],
        }
        for i, (id, src) in enumerate(inputs.items()):
            print("encoding {0}".format(id))
            data = src.read(1, masked=True)

            if mask is None:
                mask = data.mask
            else:
                mask = mask & data.mask

            # convert to indexed.  TODO: handle other types
            if sources[key].get("type", "indexed") == "indexed":
                data, unique = unique_to_indexed(data)
                data = data.filled(layer_nodata).as_type(target_dtype)

                encoding["layers"].append(
                    {
                        "id": id,
                        "nodata": layer_nodata,
                        "type": "indexed",
                        "values": unique.tolist(),
                    }
                )

            # else: already raised as error above

            encoder.add(data)

        # Apply mask to final encoded data and fill with nodata value
        encoded = np.ma.MaskedArray(encoder.values, mask).filled(nodata)

    else:
        raise NotImplementedError("other encoding types not yet supported")

    # Write tif of encoded data
    template_raster = list(rasters.values())[0]
    profile = template_raster.profile.copy()
    profile.update({"driver": "GTiff", "dtype": target_dtype, "nodata": nodata})

    with rasterio.open(outfilename, "w", **profile) as out:
        out.write(encoded, 1)

    return encoding
