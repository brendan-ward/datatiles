"""Exponential encoding and decoding classes"""

import numpy as np


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
            self._encoded = arr.copy()

        else:
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
