import numpy as np
import pytest
from hypothesis import given, strategies as st

from datatiles.encoding.exponential import (
    encode,
    decode,
    ExponentialEncoder,
    ExponentialDecoder,
)


@given(st.lists(st.integers(0, 100), min_size=1, max_size=4))
def test_encode(values):
    base = max(2, max(values) + 1)

    num_values = len(values)
    encoded = encode(values, base=base)

    # Encoding is tested manually to avoid testing against the same implementation as the underlying implementation we are testing against
    if num_values == 1:
        assert encoded == values[0]

    elif num_values == 2:
        assert encoded == values[0] + (values[1] * base)

    elif num_values == 3:
        assert encoded == values[0] + (values[1] * base) + (values[2] * (base ** 2))

    elif num_values == 3:
        assert encoded == values[0] + (values[1] * base) + (values[2] * (base ** 2)) + (
            values[3] * (base ** 3)
        )


def test_encode_error():
    # Fails due to invalid values
    for invalid_values in (None, [], 4):
        with pytest.raises(ValueError):
            encode(invalid_values)

    # Fails due to base=1
    with pytest.raises(ValueError):
        encode([4], base=1)

    # Fails due to base < max(values)
    with pytest.raises(ValueError):
        encode([4], base=2)


@given(st.integers(7, 100))
def test_decode(base):
    assert decode(4, base=base) == [4]

    encoded = 4 + (5 * base)
    out = decode(encoded, base=base, size=2)
    assert out == [4, 5]

    encoded = 4 + (5 * base) + (6 * (base ** 2))
    out = decode(encoded, base=base, size=3)
    assert out == [4, 5, 6]


@given(st.lists(st.integers(0, 100), min_size=1, max_size=10))
def test_encode_decode_roundtrip(values):
    base = max(2, max(values) + 1)
    assert decode(encode(values, base=base), base=base, size=len(values)) == values


@given(st.lists(st.integers(0, 254), min_size=1, max_size=100))
def test_ExponentialEncoder(values):
    base = max(2, max(values) + 1)
    encoder = ExponentialEncoder(base=base)

    arr = np.array(values, dtype="uint32")
    encoder.add(arr)
    assert np.array_equal(encoder.values, arr)

    arr2 = arr.copy()[::-1]
    encoder.add(arr2)
    expected = arr + arr2 * base
    assert np.array_equal(encoder.values, expected)

    arr3 = arr.copy()
    np.random.shuffle(arr3)
    encoder.add(arr3)
    expected = arr + (arr2 * base) + (arr3 * (base ** 2))
    assert np.array_equal(encoder.values, expected)


@given(st.lists(st.integers(0, 254), min_size=1, max_size=100))
def test_ExponentialDecoder(values):
    base = max(2, max(values) + 1)
    encoder = ExponentialEncoder(base=base)

    arr = np.array(values, dtype="uint32")
    arr2 = arr.copy()[::-1]
    arr3 = arr.copy()
    np.random.shuffle(arr3)

    encoder.add(arr)
    decoder = ExponentialDecoder(encoded=encoder.values, size=1, base=base)
    decoded = next(decoder.decode())
    assert np.array_equal(decoded, arr)

    encoder.add(arr2)
    decoder = ExponentialDecoder(encoded=encoder.values, size=2, base=base)
    decode = decoder.decode()
    assert np.array_equal(next(decode), arr2)
    assert np.array_equal(next(decode), arr)

    encoder.add(arr3)
    decoder = ExponentialDecoder(encoded=encoder.values, size=3, base=base)
    decode = decoder.decode()
    assert np.array_equal(next(decode), arr3)
    assert np.array_equal(next(decode), arr2)
    assert np.array_equal(next(decode), arr)
