using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Tests;

/// <summary>
/// Level 1's tileset as the artist drew it — 41 tiles, before anything was
/// baked — assembled from the shipped blob and the manifest.
/// </summary>
internal static class Level1City
{
    /// <summary>What the artist's sheet holds, before the bake appends to it.</summary>
    public const int ArtistTileCount = 41;

    /// <summary>
    /// <b>What a tile DOES, and there is no file to import it from.</b>
    /// <c>tile_table.json</c> says how a tile is DRAWN — opaque or overlay,
    /// its pen-0 count, its bounding box — and carries no collision at all;
    /// today the only statement of this anywhere is a dict written by hand
    /// in <c>tools/make_city_map.py</c>. So it is data the EDITOR owns, and
    /// this is the seed it starts level 1 from.
    /// <para>
    /// Anything not named here is scenery. That includes the whole face of
    /// the building: <c>brick</c> and its windows have no attributes, because
    /// made solid the foot of every ladder is a place she arrives INSIDE a
    /// wall (CLAUDE.md 8.8).
    /// </para>
    /// </summary>
    public static readonly IReadOnlyDictionary<string, TileFlags> Flags =
        new Dictionary<string, TileFlags>
        {
            ["concrete"] = TileFlags.Solid,
            ["roof_l"] = TileFlags.Solid,
            ["roof_m"] = TileFlags.Solid,
            ["roof_r"] = TileFlags.Solid,
            // The top rung is in the ROOF's own row and is a platform as well
            // as a ladder, so she walks over it like any other roof tile and
            // DOWN steps her onto the shaft (CLAUDE.md 8.8).
            ["ladder"] = TileFlags.Ladder | TileFlags.Platform,
            ["sidewalk"] = TileFlags.Solid,
            ["curb"] = TileFlags.Solid,
            ["street"] = TileFlags.Solid,
            ["street_line"] = TileFlags.Solid,
            ["crate"] = TileFlags.Solid,
        };

    /// <summary>
    /// The 41 tiles, with their pixels taken out of the front of the shipped
    /// blob — which is safe to do because the bake only ever APPENDS, so the
    /// artist's tiles are still the first 41 of it.
    /// </summary>
    public static Tileset ArtistTiles()
    {
        var names = Golden.CityTileNames();
        Assert.Equal(ArtistTileCount, names.Length);
        var blob = Golden.CityTiles;

        var tiles = new List<Tile>(names.Length);
        for (var i = 0; i < names.Length; i++)
        {
            tiles.Add(new Tile
            {
                Name = names[i],
                Bytes = blob[(i * Tile.ByteCount)..((i + 1) * Tile.ByteCount)],
                Flags = Flags.GetValueOrDefault(names[i]),
            });
        }
        return new Tileset(tiles);
    }

    /// <summary>
    /// Replays the placements that produced <c>build/city_baked.json</c>:
    /// one cell per pair, prefilled with the background the record names, and
    /// a chained pair dropped on the cell its own background came from.
    /// </summary>
    public static Level WithOverlaysReplayed(IReadOnlyList<BakedRecord> baked)
    {
        var map = new byte[EngineLimits.MapWidth * EngineLimits.MapHeight];
        var overlays = new List<OverlayPlacement>();
        var cellOf = new Dictionary<int, int>();
        var next = 0;

        foreach (var record in baked)
        {
            int cell;
            if (record.Under < ArtistTileCount)
            {
                cell = next++;
                map[cell] = (byte)record.Under;
            }
            else
            {
                // An overlay standing on a composite - level 1's tank_21 over
                // the air-conditioning unit. The SAME cell takes a second
                // placement, which is what makes the bake recursive.
                cell = cellOf[record.Under];
            }

            overlays.Add(new OverlayPlacement(
                cell % EngineLimits.MapWidth, cell / EngineLimits.MapWidth,
                (byte)record.Over));

            if (record.Baked)
                cellOf[record.Index] = cell;
        }

        return new Level
        {
            LevelId = 1,
            TilesetId = 1,
            Width = EngineLimits.MapWidth,
            Height = EngineLimits.MapHeight,
            Map = map,
            Overlays = overlays,
        };
    }
}
