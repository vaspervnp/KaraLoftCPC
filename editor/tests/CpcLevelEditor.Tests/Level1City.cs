using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Tests;

/// <summary>
/// Level 1's tileset as the artist drew it — 41 tiles, before anything was
/// baked — imported from the art package.
/// </summary>
internal static class Level1City
{
    /// <summary>What the artist's sheet holds, before the bake appends to it.</summary>
    public const int ArtistTileCount = 41;

    /// <summary>
    /// The 41 tiles, <b>out of the artist's own sheet</b> — the PNG, its
    /// frame boxes, the names in the manifest's prose and the draw table,
    /// quantised against <c>src/palette.asm</c>.
    /// <para>
    /// They used to be taken out of the front of the shipped blob, which was
    /// safe (the bake only ever appends) and quietly circular: the bake test
    /// then compared 3,264 bytes of which the first 2,624 had been copied
    /// from the file being compared against, so only the ten baked tiles
    /// were really under test. Imported, all 51 are.
    /// </para>
    /// </summary>
    public static Tileset ArtistTiles() => AssetPackImporter.ImportTileset(
        Golden.Asset("sprites", "level1_city"),
        Golden.PaletteAsm,
        LevelFlagSeeds.City);

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
