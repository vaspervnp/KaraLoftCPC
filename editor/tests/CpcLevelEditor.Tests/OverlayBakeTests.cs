using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The overlays, which are the half of the format question CLAUDE.md 8.3
/// leaves open: a map cell is one byte and there is nowhere in it to say
/// "this is an overlay over that". The pairing lives in the generator today
/// and dies there; here it lives in the editor's own layer and is resolved
/// at export, so the FORMAT and the ENGINE are both unchanged.
/// </summary>
public class OverlayBakeTests
{
    private static readonly OverlayBaker Baker = new();

    [Fact]
    public void The_build_baked_something_at_all()
    {
        // The anti-vacuity guard tools/test_format.py carries for the same
        // reason: a loop over an empty list passes every assertion in it.
        var baked = Golden.CityBaked;
        Assert.NotEmpty(baked);
        Assert.Contains(baked, b => b.Baked);
    }

    [Fact]
    public void Every_pair_composites_to_the_tile_the_build_shipped()
    {
        var artist = Level1City.ArtistTiles();
        var golden = Golden.CityBaked;
        var result = Baker.Bake(Level1City.WithOverlaysReplayed(golden), artist);

        Assert.Equal(golden.Count, result.Pairs.Count);
        foreach (var (i, pair) in result.Pairs.Index())
        {
            var want = golden[i];
            Assert.Equal((want.Index, want.Over, want.Under, want.Name, want.Baked),
                         (pair.Index, pair.Over, pair.Under, pair.Name, pair.Baked));
        }

        // ... and the tileset blob itself, which is what goes into bank C4.
        Assert.Equal(Golden.CityTiles, result.Tileset.ToBlob());
        Assert.Equal(Golden.CityTiles.Length / Tile.ByteCount, result.Tileset.Count);
    }

    [Fact]
    public void A_composite_that_came_out_the_overlay_again_is_dropped()
    {
        // Level 1 has exactly one, tank_10 over far_fill: the background
        // showed through nowhere, so spending 64 bytes of bank on a copy of
        // a tile that already exists is the one thing the bake must not do.
        var artist = Level1City.ArtistTiles();
        var result = Baker.Bake(Level1City.WithOverlaysReplayed(Golden.CityBaked), artist);

        var dropped = Assert.Single(result.Pairs, p => !p.Baked);
        Assert.Equal(artist.IndexOf("tank_10"), dropped.Index);
        Assert.Equal(dropped.Over, dropped.Index);
    }

    [Fact]
    public void None_of_the_baked_tiles_is_just_the_overlay_again()
    {
        // The other side of the same rule: a pair that WAS baked has to
        // differ from its overlay, or dropping it was the right answer and
        // the drop test is passing for the wrong reason.
        var artist = Level1City.ArtistTiles();
        var result = Baker.Bake(Level1City.WithOverlaysReplayed(Golden.CityBaked), artist);

        foreach (var pair in result.Pairs.Where(p => p.Baked))
            Assert.NotEqual(artist[pair.Over].Bytes, result.Tileset[pair.Index].Bytes);
    }

    [Fact]
    public void An_overlay_can_stand_on_a_tile_that_was_itself_baked()
    {
        // The water tank's top-right corner sits on the air-conditioning
        // unit, so the pair's background is another composite and the
        // resolution has to recurse. It is also why the sidecar records the
        // background AFTER the remap and not before.
        var result = Baker.Bake(Level1City.WithOverlaysReplayed(Golden.CityBaked),
                                Level1City.ArtistTiles());
        var chained = Assert.Single(result.Pairs,
            p => p.Under >= Level1City.ArtistTileCount);
        Assert.Equal("tank_21_on_ac_unit_on_far_fill", chained.Name);
    }

    [Fact]
    public void A_baked_tile_does_what_the_one_underneath_does()
    {
        // What the cell IS depends on what she stands on, walks into or
        // climbs; the overlay is the decoration that was drawn over it.
        var artist = Level1City.ArtistTiles();
        var result = Baker.Bake(Level1City.WithOverlaysReplayed(Golden.CityBaked), artist);

        foreach (var pair in result.Pairs.Where(p => p.Baked))
            Assert.Equal(result.Tileset[pair.Under].Flags, result.Tileset[pair.Index].Flags);
    }

    [Fact]
    public void The_map_s_cells_point_at_the_finished_tile()
    {
        var artist = Level1City.ArtistTiles();
        var level = Level1City.WithOverlaysReplayed(Golden.CityBaked);
        var result = Baker.Bake(level, artist);

        // A cell holds the LAST thing placed on it, which for the chained
        // pair is the composite of the composite - so the expectation is
        // built the same way the placements were, and not from the pair list
        // in order.
        var expected = new Dictionary<int, int>();
        foreach (var (i, pair) in result.Pairs.Index())
        {
            var placement = level.Overlays[i];
            expected[placement.Y * level.Width + placement.X] = pair.Index;
        }
        foreach (var (cell, index) in expected)
            Assert.Equal(index, result.Map[cell]);

        // And no cell is left holding a provisional id, which would be a
        // tile index past the end of the tileset.
        Assert.All(result.Map, cell => Assert.True(cell < result.Tileset.Count));
    }

    [Fact]
    public void The_shipped_map_places_the_baked_tile_and_never_the_raw_overlay()
    {
        // An overlay left raw in the map would be drawn over black instead of
        // over the wall behind it - which is what the bake exists to prevent,
        // and 279 pixels of level 1 are the difference (CLAUDE.md 7.3).
        var reader = new BinaryLevelReader();
        var map = reader.Read(Golden.Level1).Map;
        var baked = Golden.CityBaked;

        var kept = baked.Where(b => !b.Baked).Select(b => b.Index).ToHashSet();
        var rawOverlays = baked.Select(b => b.Over).ToHashSet();
        rawOverlays.ExceptWith(kept);

        Assert.Empty(map.Select(c => (int)c).ToHashSet().Intersect(rawOverlays));

        // ... and tank_10 IS in the map raw, legitimately, because its bake
        // was dropped. Without this the check above could pass on a map that
        // simply never placed an overlay at all.
        Assert.Contains(Level1City.ArtistTiles().IndexOf("tank_10"),
                        map.Select(c => (int)c));
    }

    [Fact]
    public void The_two_tiles_of_a_pair_are_not_interchangeable()
    {
        // THE NEGATIVE CONTROL. The composite rule is "the overlay's pens
        // where they are not 0, the background's where they are"; composited
        // the wrong way round it is a different tile, and if it were not,
        // this suite would be measuring nothing about which is which.
        var artist = Level1City.ArtistTiles();
        var result = Baker.Bake(Level1City.WithOverlaysReplayed(Golden.CityBaked), artist);

        var same = 0;
        foreach (var pair in result.Pairs.Where(p => p.Baked))
        {
            var top = artist[pair.Over].ToPens();
            var bottom = result.Tileset[pair.Under].ToPens();
            var wrongWayRound = new byte[Tile.PixelHeight][];
            for (var y = 0; y < Tile.PixelHeight; y++)
            {
                wrongWayRound[y] = new byte[Tile.PixelWidth];
                for (var x = 0; x < Tile.PixelWidth; x++)
                    wrongWayRound[y][x] = bottom[y][x] != 0 ? bottom[y][x] : top[y][x];
            }
            if (Tile.Encode(wrongWayRound).AsSpan()
                    .SequenceEqual(result.Tileset[pair.Index].Bytes))
                same++;
        }
        Assert.True(same < result.Pairs.Count(p => p.Baked),
            "every pair composites the same either way round, so nothing here "
            + "distinguishes the overlay from the tile under it");
    }
}
