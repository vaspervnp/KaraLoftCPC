namespace CpcLevelEditor.Domain;

/// <summary>
/// A level's tiles, in the artist's frame order — which is what a map byte
/// indexes and what the flags file is ordered by.
/// </summary>
/// <remarks>
/// The set GROWS at export: the baker appends one tile per distinct
/// (overlay, background) pair the designer placed. Level 1 ships 41 of the
/// artist's and 10 baked, 3,264 bytes of bank C4.
/// </remarks>
public sealed class Tileset
{
    private readonly List<Tile> _tiles;

    public Tileset(IEnumerable<Tile> tiles) => _tiles = [.. tiles];

    public IReadOnlyList<Tile> Tiles => _tiles;

    public int Count => _tiles.Count;

    public Tile this[int index] => _tiles[index];

    /// <summary>
    /// Adds a tile and returns its index — which is the map byte that will
    /// point at it. Indices only ever grow, which is what lets the baker
    /// resolve an overlay standing on another composite by recursion.
    /// </summary>
    public byte Append(Tile tile)
    {
        if (_tiles.Count >= EngineLimits.ScratchTileFirst)
            throw new InvalidOperationException(
                $"tile {_tiles.Count} would land in the pickup bake's scratch range "
                + $"({EngineLimits.ScratchTileFirst}-255), which ENT_BAKE stamps into "
                + "at run time");
        _tiles.Add(tile);
        return (byte)(_tiles.Count - 1);
    }

    /// <summary>The index of a named tile, or -1.</summary>
    public int IndexOf(string name)
    {
        for (var i = 0; i < _tiles.Count; i++)
            if (_tiles[i].Name == name)
                return i;
        return -1;
    }

    /// <summary>The pixel bytes of every tile, end to end — the tileset blob.</summary>
    public byte[] ToBlob()
    {
        var blob = new byte[_tiles.Count * Tile.ByteCount];
        for (var i = 0; i < _tiles.Count; i++)
            _tiles[i].Bytes.CopyTo(blob, i * Tile.ByteCount);
        return blob;
    }
}
