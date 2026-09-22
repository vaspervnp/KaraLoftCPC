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

    /// <summary>Level 2, the forest.</summary>
    /// <remarks>
    /// <para>
    /// <b>The face of the forest is background, not a wall</b> — the lesson
    /// the City's brick already paid for (CLAUDE.md 8.8). The trunks, the
    /// crowns, the canopy and the whole mountain are scenery she walks in
    /// front of: made solid, a tree would be a wall across the level and
    /// the mountain would be the end of it.
    /// </para>
    /// <para>
    /// <b>The branches are <c>Platform</c> and not <c>Solid</c></b>, which is
    /// level 2's signature: a platform is a floor from above and nothing
    /// from below, so she jumps up through a branch and stands on it — the
    /// artist's own "walkable surface = tile top".
    /// </para>
    /// <para>
    /// <b>And <c>Hazard</c> does nothing yet.</b> <c>TA_HAZARD</c> is defined
    /// in <c>src/collide.asm</c> and nothing reads it, so the spike pit is
    /// flagged the way the level means it and is, for now, a dip she falls
    /// into and jumps out of. The data is right in advance; the engine is
    /// what owes.
    /// </para>
    /// </remarks>
    public static readonly IReadOnlyDictionary<string, TileFlags> Forest =
        new Dictionary<string, TileFlags>(StringComparer.Ordinal)
        {
            ["grass"] = TileFlags.Solid,
            ["grass_edge_l"] = TileFlags.Solid,
            ["grass_edge_r"] = TileFlags.Solid,
            ["dirt"] = TileFlags.Solid,
            // In the ground row with the grass, so they hold her up like it
            // — without these there is a hole at the foot of every tree.
            ["trunk_base_l"] = TileFlags.Solid,
            ["trunk_base_r"] = TileFlags.Solid,
            ["root_l"] = TileFlags.Solid,
            ["root_r"] = TileFlags.Solid,
            ["branch_l"] = TileFlags.Platform,
            ["branch_m"] = TileFlags.Platform,
            ["branch_r"] = TileFlags.Platform,
            ["spike_pit"] = TileFlags.Hazard,
            ["cave_floor_l"] = TileFlags.Solid,
            ["cave_floor"] = TileFlags.Solid,
            ["cave_floor_r"] = TileFlags.Solid,
        };

    /// <summary>
    /// The seeds for one level's art package, or nothing at all — four of
    /// the six levels have no map yet and start with every tile scenery.
    /// </summary>
    public static IReadOnlyDictionary<string, TileFlags> For(string assetLevel) =>
        assetLevel switch
        {
            "level1_city" => City,
            "level2_forest" => Forest,
            _ => new Dictionary<string, TileFlags>(StringComparer.Ordinal),
        };
}
