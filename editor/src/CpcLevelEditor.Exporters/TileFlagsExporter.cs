using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Exporters;

/// <summary>
/// Writes <c>tileflags_&lt;level&gt;.bin</c>: one byte a tile, in the
/// tileset's own frame order.
/// </summary>
/// <remarks>
/// <para>
/// <b>It is a SIBLING file, not a section of the <c>.lvl</c></b>, and it is
/// the table itself rather than something the engine converts:
/// <c>MAP_INSTALL</c> clears all 256 entries of <c>TILE_ATTR</c> and
/// <c>LDIR</c>s this file over the front, so a tile index past the end of it
/// answers zero (CLAUDE.md 8.3).
/// </para>
/// <para>
/// The file may be SHORTER than 256 and must not be longer — level 1's is 51
/// bytes for 41 of the artist's tiles and 10 baked ones.
/// </para>
/// </remarks>
public sealed class TileFlagsExporter
{
    public byte[] Write(Tileset tileset)
    {
        if (tileset.Count > EngineLimits.TileAttributeCount)
            throw new ArgumentException(
                $"{tileset.Count} tiles against the {EngineLimits.TileAttributeCount} "
                + "entries the engine indexes with a one-byte tile number",
                nameof(tileset));

        var flags = new byte[tileset.Count];
        for (var i = 0; i < tileset.Count; i++)
            flags[i] = (byte)tileset[i].Flags;
        return flags;
    }
}
