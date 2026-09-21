using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Assets;

/// <summary>
/// <b>What a tile DOES, and there is no file in the package to import it
/// from.</b>
/// </summary>
/// <remarks>
/// <para>
/// <c>tile_table.json</c> says how a tile is DRAWN — opaque or overlay, its
/// pen-0 count, its bounding box — and carries no collision at all; the
/// manifest says what a sheet is FOR. Today the only statement of what a
/// cell does anywhere in this repository is a dict written by hand in
/// <c>tools/make_city_map.py</c>. So the flags are data the EDITOR owns and
/// <c>tileflags_&lt;level&gt;.bin</c> is its OUTPUT, not its input; these are
/// the seeds a designer starts from and then edits.
/// </para>
/// <para>
/// Anything not named is scenery, and that is load-bearing rather than
/// lazy. The whole face of the building — <c>brick</c> and both its windows
/// — has no attributes: made solid, which it once was, the foot of every
/// ladder is a place she arrives INSIDE a wall, because she is three tiles
/// wide and the shaft is one (CLAUDE.md 8.8).
/// </para>
/// </remarks>
public static class LevelFlagSeeds
{
    /// <summary>Level 1, the City.</summary>
    public static readonly IReadOnlyDictionary<string, TileFlags> City =
        new Dictionary<string, TileFlags>(StringComparer.Ordinal)
        {
            ["concrete"] = TileFlags.Solid,
            ["roof_l"] = TileFlags.Solid,
            ["roof_m"] = TileFlags.Solid,
            ["roof_r"] = TileFlags.Solid,
            // THE TOP RUNG IS IN THE ROOF'S OWN ROW and is a platform as well
            // as a ladder: a platform is a floor from above and nothing from
            // below, so she walks over it like any other roof tile and DOWN
            // steps her onto the shaft. A ladder starting one row lower -
            // which is where the artist's mockup draws it - would be a thing
            // she could only fall onto (CLAUDE.md 8.8).
            ["ladder"] = TileFlags.Ladder | TileFlags.Platform,
            ["sidewalk"] = TileFlags.Solid,
            ["curb"] = TileFlags.Solid,
            ["street"] = TileFlags.Solid,
            ["street_line"] = TileFlags.Solid,
            ["crate"] = TileFlags.Solid,
        };

    /// <summary>
    /// The seeds for one level's art package, or nothing at all — five of
    /// the six levels have no map yet and start with every tile scenery.
    /// </summary>
    public static IReadOnlyDictionary<string, TileFlags> For(string assetLevel) =>
        assetLevel == "level1_city"
            ? City
            : new Dictionary<string, TileFlags>(StringComparer.Ordinal);
}
