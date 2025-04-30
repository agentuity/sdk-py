import pytest
from agentuity.server.data import EmptyDataReader, StringStreamReader, BytesStreamReader


@pytest.mark.asyncio
async def test_empty_data_reader():
    reader = EmptyDataReader()

    # Test read methods
    assert await reader.read() == b""
    assert await reader.readany() == b""
    assert await reader.readline() == b""
    assert await reader.readchunk() == (b"", True)

    # Test readexactly
    assert await reader.readexactly(0) == b""
    with pytest.raises(ValueError):
        await reader.readexactly(1)

    # Test state methods
    assert reader.at_eof() is True
    assert reader.exception() is None

    # Test unread_data
    with pytest.raises(ValueError):
        reader.unread_data(b"test")


@pytest.mark.asyncio
async def test_string_stream_reader():
    test_string = "Hello, World!"
    reader = StringStreamReader(test_string)

    # Test read methods
    assert await reader.read() == test_string.encode("utf-8")
    assert reader.at_eof() is True

    # Reset reader
    reader = StringStreamReader(test_string)

    # Test readexactly
    assert await reader.readexactly(5) == b"Hello"
    assert await reader.readexactly(2) == b", "
    assert await reader.readexactly(6) == b"World!"
    assert reader.at_eof() is True

    # Test readline (should return entire string)
    reader = StringStreamReader(test_string)
    assert await reader.readline() == test_string.encode("utf-8")

    # Test readchunk
    reader = StringStreamReader(test_string)
    data, eof = await reader.readchunk()
    assert data == test_string.encode("utf-8")
    assert eof is True

    # Test unread_data
    reader = StringStreamReader(test_string)
    data = await reader.readexactly(5)
    reader.unread_data(data)
    assert await reader.read() == test_string.encode("utf-8")

    # Test error cases
    with pytest.raises(ValueError):
        await reader.readexactly(-1)
    with pytest.raises(ValueError):
        await reader.readexactly(1)
    with pytest.raises(NotImplementedError):
        reader.feed_data(b"test")


@pytest.mark.asyncio
async def test_bytes_stream_reader():
    test_bytes = b"Hello, World!"
    reader = BytesStreamReader(test_bytes)

    # Test read methods
    assert await reader.read() == test_bytes
    assert reader.at_eof() is True

    # Reset reader
    reader = BytesStreamReader(test_bytes)

    # Test readexactly
    assert await reader.readexactly(5) == b"Hello"
    assert await reader.readexactly(2) == b", "
    assert await reader.readexactly(6) == b"World!"
    assert reader.at_eof() is True

    # Test readline (should return entire bytes)
    reader = BytesStreamReader(test_bytes)
    assert await reader.readline() == test_bytes

    # Test readchunk
    reader = BytesStreamReader(test_bytes)
    data, eof = await reader.readchunk()
    assert data == test_bytes
    assert eof is True

    # Test unread_data
    reader = BytesStreamReader(test_bytes)
    data = await reader.readexactly(5)
    reader.unread_data(data)
    assert await reader.read() == test_bytes

    # Test error cases
    with pytest.raises(ValueError):
        await reader.readexactly(-1)
    with pytest.raises(ValueError):
        await reader.readexactly(1)
    with pytest.raises(NotImplementedError):
        reader.feed_data(b"test")


@pytest.mark.asyncio
async def test_stream_reader_edge_cases():
    # Test empty string
    reader = StringStreamReader("")
    assert await reader.read() == b""
    assert reader.at_eof() is True

    # Test empty bytes
    reader = BytesStreamReader(b"")
    assert await reader.read() == b""
    assert reader.at_eof() is True

    # Test unread_data with empty data
    reader = StringStreamReader("test")
    reader.unread_data(b"")
    assert await reader.read() == b"test"

    # Test unread_data with full data
    reader = StringStreamReader("test")
    data = await reader.read()
    reader.unread_data(data)
    assert await reader.read() == b"test"

    # Test feed_eof
    reader = StringStreamReader("test")
    reader.feed_eof()
    assert reader.at_eof() is True
    assert await reader.read() == b""
