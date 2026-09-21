using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Application;

/// <summary>
/// A shipped level back into something a designer can paint: the map's
/// composited cells taken apart into the artist's tile and the overlays that
/// were put on it.
/// </summary>
/// <remarks>
/// <para>
/// <b>THE FILE CANNOT DO THIS ON ITS OWN, AND THAT IS THE FORMAT'S ONE REAL
/// GAP.</b> A map cell is one byte and a finished tile; nothing in
/// <c>level_&lt;n&gt;.lvl</c> says "this cell is an overlay over that one"
/// (CLAUDE.md 7.3, 8.3). What makes the un-bake possible is the build's own
/// sidecar, <c>city_baked.json</c> — the record of which pairs were
/// composited into which index. Without it a shipped level opens as 51 flat
/// tiles and the lamp post can never be moved off the wall again.
/// </para>
/// <para>
/// <b>A DROPPED PAIR IS NOT RECOVERABLE AND DOES NOT NEED TO BE.</b> Level 1
/// has one — <c>tank_10</c>, whose composite came out byte for byte the
/// overlay, so the bake reused the overlay's own index rather than spending
/// a tile on it. A cell holding that index is therefore either the plain
/// tile or the dropped pair and nothing can tell them apart; it comes back
/// as the plain tile, and re-exporting gives the same byte either way,
/// because that is exactly what "the composite came out the overlay" means.
/// </para>
/// </remarks>
public static class LevelUnbaker
{
    public readonly record struct Source(byte[] Map, IReadOnlyList<OverlayPlacement> Overlays);

    /// <summary>
    /// <paramref name="pairs"/> is the bake's own record — <c>index</c>,
    /// <c>over</c> and <c>under</c> per composite, which is what
    /// <c>build/city_baked.json</c> holds and what
    /// <see cref="ExportResult.Pairs"/> returns.
    /// </summary>
    public static Source Unbake(
        Level baked, IReadOnlyList<BakedPair> pairs, int artistTileCount)
    {
        var composite = pairs
            .Where(p => p.Index >= artistTileCount)
            .ToDictionary(p => p.Index, p => (p.Over, p.Under));

        var map = (byte[])baked.Map.Clone();
        var overlays = new List<OverlayPlacement>();

        for (var cell = 0; cell < map.Length; cell++)
        {
            if (map[cell] < artistTileCount)
                continue;

            // Walk down to the artist's tile, collecting the overlays on the
            // way; a pair's background can itself be a composite, which is
            // level 1's tank_21 over the air-conditioning unit.
            var stack = new List<int>();
            var index = (int)map[cell];
            while (index >= artistTileCount)
            {
                if (!composite.TryGetValue(index, out var pair))
                    throw new InvalidDataException(
                        $"cell ({cell % baked.Width},{cell / baked.Width}) points at tile "
                        + $"{index} and nothing in the bake record says what it was made of");
                stack.Add(pair.Over);
                index = pair.Under;
            }

            map[cell] = (byte)index;
            // Bottom-most first, so replaying them lands each one on the
            // background it was composited over.
            stack.Reverse();
            overlays.AddRange(stack.Select(
                over => new OverlayPlacement(
                    cell % baked.Width, cell / baked.Width, (byte)over)));
        }

        return new Source(map, overlays);
    }
}
