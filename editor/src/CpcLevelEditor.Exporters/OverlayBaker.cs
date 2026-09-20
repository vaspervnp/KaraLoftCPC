using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Exporters;

/// <summary>
/// Composites every distinct (overlay, background) pair into a new tile and
/// points the map's cells at it — the port of <c>make_city_map.py</c>'s
/// <c>put_overlay()</c> and <c>bake_overlays()</c>.
/// </summary>
/// <remarks>
/// <para>
/// <b>THE ENGINE HAS NO MASKED TILE PATH AND IS NOT GETTING ONE.</b> A
/// masked cell is 1,338-2,007 T against a scrolling frame's 3,548 of
/// headroom, so two overlay cells in one column would be the whole budget.
/// The composite does not change between frames — an overlay tile and the
/// tile under it are both scenery — so it is done once, here, and costs
/// nothing per frame for ever after (CLAUDE.md 7.3).
/// </para>
/// <para>
/// <b>Placement ORDER decides the numbering.</b> A pair takes its index the
/// first time it is placed, so a different order gives different indices and
/// therefore different map bytes for the same picture. That is not a defect
/// to be designed away — any assignment is arbitrary — but it does mean the
/// numbering is not part of the format's contract, and a golden test should
/// compare a pair's CONTENT and the map's consistency rather than its index.
/// Handed the placements in <c>make_city_map.py</c>'s order, this reproduces
/// <c>city_baked.json</c> exactly.
/// </para>
/// <para>
/// <b>An overlay can stand on a BAKED tile</b> — level 1's water tank has a
/// corner over the air-conditioning unit — so the background of a pair may
/// itself be a composite and the resolution is recursive. It terminates
/// because a bake's index is always higher than both tiles it was made from.
/// </para>
/// </remarks>
public sealed class OverlayBaker
{
    public OverlayBakeResult Bake(Level level, Tileset artistTiles)
    {
        var map = (byte[])level.Map.Clone();
        var tiles = new Tileset(artistTiles.Tiles);

        // Pass one: the provisional pass. A cell takes the pair's id the
        // moment it is placed, so a later overlay dropped on the same cell
        // sees the composite as its background rather than the raw tile.
        var order = new List<(int Over, int Under)>();
        var provisional = new Dictionary<(int Over, int Under), int>();
        foreach (var placement in level.Overlays)
        {
            var cell = placement.Y * level.Width + placement.X;
            var key = (Over: (int)placement.Overlay, Under: (int)map[cell]);
            if (!provisional.TryGetValue(key, out var id))
            {
                id = artistTiles.Count + order.Count;
                provisional[key] = id;
                order.Add(key);
            }
            map[cell] = checked((byte)id);
        }

        // Pass two: composite, drop what the background did not change, and
        // work out where each provisional id really points.
        var pens = new Dictionary<int, byte[][]>();
        var names = new Dictionary<int, string>();
        var flags = new Dictionary<int, TileFlags>();
        var remap = new Dictionary<int, byte>();
        var pairs = new List<BakedPair>();

        byte[][] PensOf(int index)
        {
            if (pens.TryGetValue(index, out var cached))
                return cached;
            if (index < artistTiles.Count)
                return pens[index] = artistTiles[index].ToPens();
            var (over, under) = order[index - artistTiles.Count];
            var top = PensOf(over);
            var bottom = PensOf(under);
            var mixed = new byte[Tile.PixelHeight][];
            for (var y = 0; y < Tile.PixelHeight; y++)
            {
                mixed[y] = new byte[Tile.PixelWidth];
                for (var x = 0; x < Tile.PixelWidth; x++)
                    // The overlay's pen 0 is the transparent one, and it is
                    // the TABLE that says a tile is an overlay: the pixels
                    // cannot, because pen 0 is opaque black everywhere else.
                    mixed[y][x] = top[y][x] != 0 ? top[y][x] : bottom[y][x];
            }
            return pens[index] = mixed;
        }

        string NameOf(int index) =>
            index < artistTiles.Count ? artistTiles[index].Name : names[index];

        TileFlags FlagsOf(int index) =>
            index < artistTiles.Count ? artistTiles[index].Flags : flags[index];

        for (var i = 0; i < order.Count; i++)
        {
            var id = artistTiles.Count + i;
            var (over, under) = order[i];
            var underFinal = under < artistTiles.Count ? under : remap[under];
            var composite = Tile.Encode(PensOf(id));

            if (composite.AsSpan().SequenceEqual(artistTiles[over].Bytes))
            {
                // The background showed through nowhere. Spending 64 bytes of
                // bank C4 on a copy of the overlay is the one thing the bake
                // must not do, so the cell points back at the overlay itself.
                remap[id] = checked((byte)over);
                // A dropped pair can still be the BACKGROUND of a later one,
                // so it has to answer for its name and its flags like any
                // other cell - and what it is, is the overlay.
                names[id] = artistTiles[over].Name;
                flags[id] = artistTiles[over].Flags;
                pairs.Add(new BakedPair(over, over, underFinal,
                                        artistTiles[over].Name, Baked: false));
                continue;
            }

            var name = $"{artistTiles[over].Name}_on_{NameOf(under)}";
            // A BAKED TILE DOES WHAT THE ONE UNDERNEATH DOES. What the cell
            // is depends on what she stands on, walks into or climbs; the
            // overlay is the decoration that was drawn over it.
            var index = tiles.Append(new Tile
            {
                Name = name,
                Bytes = composite,
                Flags = FlagsOf(under),
                IsOverlay = false,
            });
            remap[id] = index;
            names[id] = name;
            flags[id] = FlagsOf(under);
            pairs.Add(new BakedPair(index, over, underFinal, name, Baked: true));
        }

        for (var i = 0; i < map.Length; i++)
            if (remap.TryGetValue(map[i], out var final))
                map[i] = final;

        return new OverlayBakeResult(map, tiles, pairs);
    }
}
