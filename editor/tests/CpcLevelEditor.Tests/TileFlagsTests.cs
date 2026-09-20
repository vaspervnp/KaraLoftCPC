using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// <c>tileflags_&lt;level&gt;.bin</c>, which is not a section of the level
/// file but a sibling — and is not a table the engine converts either. It IS
/// <c>TILE_ATTR</c>: <c>MAP_INSTALL</c> clears 256 entries and <c>LDIR</c>s
/// this over the front (CLAUDE.md 8.3).
/// </summary>
public class TileFlagsTests
{
    private static readonly TileFlagsExporter Exporter = new();
    private static readonly OverlayBaker Baker = new();

    private static Tileset BakedTileset() =>
        Baker.Bake(Level1City.WithOverlaysReplayed(Golden.CityBaked),
                   Level1City.ArtistTiles()).Tileset;

    [Fact]
    public void The_file_is_the_one_the_build_ships()
    {
        Assert.Equal(Golden.CityTileFlags, Exporter.Write(BakedTileset()));
    }

    [Fact]
    public void It_is_one_byte_a_tile_and_no_longer_than_the_table()
    {
        var tileset = BakedTileset();
        var flags = Exporter.Write(tileset);
        Assert.Equal(tileset.Count, flags.Length);
        Assert.True(flags.Length <= EngineLimits.TileAttributeCount);

        // Shorter is fine and is the normal case - the loader zeroes the
        // rest, so a tile index past the end of the file answers "scenery".
        Assert.True(flags.Length < EngineLimits.TileAttributeCount);
    }

    [Fact]
    public void The_bit_order_is_the_format_s_and_so_the_engine_s()
    {
        // TA_SOLID used to be bit 7 in collide.asm and the engine took the
        // format's numbering instead, so neither side translates. If these
        // ever diverged the ladder would come back as TA_WATER.
        var tileset = BakedTileset();
        var flags = Exporter.Write(tileset);

        Assert.Equal((byte)(TileFlags.Ladder | TileFlags.Platform),
                     flags[tileset.IndexOf("ladder")]);
        Assert.Equal((byte)TileFlags.Solid, flags[tileset.IndexOf("roof_m")]);
        Assert.Equal((byte)TileFlags.Solid, flags[tileset.IndexOf("sidewalk")]);

        // The building's face is BACKGROUND, not a wall. Made solid, the foot
        // of every ladder is a place she arrives inside a wall and BOX_SOLID_H
        // then refuses every step along the street (CLAUDE.md 8.8).
        Assert.Equal(0, flags[tileset.IndexOf("brick")]);
        Assert.Equal(0, flags[tileset.IndexOf("brick_win_lit")]);
        Assert.Equal(0, flags[tileset.IndexOf("brick_win_dark")]);
    }

    [Fact]
    public void The_ten_tiles_with_anything_on_are_the_ten_the_build_has()
    {
        var mine = Exporter.Write(BakedTileset());
        var theirs = Golden.CityTileFlags;
        Assert.Equal(theirs.Count(f => f != 0), mine.Count(f => f != 0));
        Assert.Equal(10, mine.Count(f => f != 0));
    }

    [Fact]
    public void A_flag_moved_to_the_wrong_tile_shows_up()
    {
        // THE NEGATIVE CONTROL, and it is the mistake that looks almost
        // right: the same ten flags on tiles one along. Every count check
        // above still passes and the file is wrong.
        var artist = Level1City.ArtistTiles();
        var shifted = new Tileset(artist.Tiles.Select((t, i) => new Tile
        {
            Name = t.Name,
            Bytes = t.Bytes,
            Flags = artist[(i + 1) % artist.Count].Flags,
        }));
        var flags = Exporter.Write(shifted);
        Assert.Equal(10, flags.Count(f => f != 0));
        Assert.NotEqual(Golden.CityTileFlags.Take(artist.Count), flags);
    }
}
