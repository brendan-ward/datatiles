"""Exponential encoding and decoding classes"""

import collections
import numpy as np


def encode(values, base=10):
    """Encode values using exponential method.

    Note: this is not an efficient method for encoding many values; use ExponentialEncoder instead.
    
    Parameters
    ----------
    values : list-like of values to encode
    base : unsigned int, optional (default: 10)
        base is raised to a value for each array added to the encoder.
        All values of the array to encode must fit between 0 and base.
        Must be > 1.

    Returns
    -------
    int : encoded value
    """

    if not isinstance(values, collections.Iterable):
        raise ValueError("values must be an iterable")

    if not len(values):
        raise ValueError("values must be non-empty")

    if base <= 1:
        raise ValueError("base must be larger than 1")

    if max(values) > base:
        raise ValueError("base must be larger than the max value")

    encoded = 0
    for i, value in enumerate(values):
        encoded += value * (base ** i)

    return encoded


def decode(encoded, base=10, size=1):
    """Decode the values previously encoded using base.
    
    Parameters
    ----------
    encoded : int
        encoded value
    base : int, optional (default: 10)
        base is raised to a value for each array added to the encoder.
        All values of the array to encode must fit between 0 and base.
    size : int, optional (default: 1)
        number of values to decode.  Must be equal to the number of values that were encoded.
    
    Returns
    -------
    list of decoded values
    """

    values = []
    for i in range(size - 1, -1, -1):
        if i == 0:
            decoded = encoded
        else:
            factor = base ** i
            remainder = encoded % factor
            decoded = (encoded - remainder) / factor
            encoded = remainder

        values.append(decoded)

    values.reverse()
    return values


class ExponentialEncoder(object):
    """
    Use exponential encoding method to iteratively encode and decode 2D arrays.

    Due to the encoding order, arrays are pushed onto the encoder to encode, and
    popped off the encoder to decode.
    """

    def __init__(self, dtype="uint32", base=10):
        """Initialize the encoder.

        To decode, you must provide the encoded and the number of arrays that
        were encoded.
        
        Parameters
        ----------
        dtype : str, optional
            data type of the encoding (default: uint32)
        base : int, optional
            base to use for encoding (default 10); base is raised to a value for each array
            added to the encoder.  All values of the array to encode must fit between 0 and base. 
        """

        self._dtype = dtype
        self._base = base
        self._encoded = None
        self._index = 0

    def add(self, arr):
        """Add an array to the encoder.
        
        Parameters
        ----------
        arr : numpy.array or numpy.ma.MaskedArray

        Returns
        -------
        numpy.array
            Encoded array
        """

        # TODO: validate dtype <= self.dtype
        # TODO: validate that values are between 0 and slot_size
        # TODO: nodata filling?

        if self._index == 0:
            self._encoded = arr.copy().astype(self._dtype)

        else:
            if arr.shape != self._encoded.shape:
                raise ValueError("all arrays must be the same shape to encode")

            self._encoded += arr * (self._base ** self._index)

        self._index += 1

    @property
    def values(self):
        """
        Get the currently encoded data.
        
        Returns
        -------
        numpy array
        """

        return self._encoded.copy()

    def get_config(self):
        """
        TODO: Return the encoder config dict.
        
        """
        pass


class ExponentialDecoder(object):
    """
    Use exponential encoding method to iteratively encode and decode 2D arrays.

    Due to the encoding order, arrays are pushed onto the encoder to encode, and
    popped off the encoder to decode.
    """

    def __init__(self, encoded, size, base=10):
        """Initialize the encoder.

        To decode, you must provide the encoded and the number of arrays that
        were encoded.
        
        Parameters
        ----------
        encoded : numpy array or MaskedArray  
        size : int
            number of arrays that were encoded
        base : int, optional
            base that was used for encoding (default 10).
        """

        self._encoded = encoded
        self._size = size
        self._base = base

    def decode(self):
        """Generator that iteratively decodes each value from the encoded data"""

        for index in range(self._size - 1, -1, -1):
            if index == 0:
                decoded = self._encoded

            else:
                factor = self._base ** index
                remaining = self._encoded % factor
                decoded = ((self._encoded - remaining) / factor).astype(
                    self._encoded.dtype
                )
                self._encoded = remaining

            yield decoded

        return
