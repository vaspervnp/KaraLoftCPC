using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// The artist's package into a tileset — and the witness is the blob the
/// build already ships.
/// </summary>
/// <remarks>
/// Four transformations are checked at once by that one comparison: the PNG
/// decoder, the quantiser against <c>src/palette.asm</c>'s sixteen pens, the
/// column-major packing the tile blitters read, and the frame order the
/// manifest states in prose. Each has a negative control under it, because
/// a comparison proves nothing until something shows it would have noticed.
/// </remarks>
public class AssetImportTests
{
    private static string LevelDir => Golden.Asset("sprites", "level1_city");

    private static byte[] ArtistPrefixOfShippedBlob =>
        Golden.CityTiles[..(Level1City.ArtistTileCount * Tile.ByteCount)];

    [Fact]
    public void The_artist_s_sheet_IS_the_shipped_tileset()
    {
        var imported = Level1City.ArtistTiles();

        Assert.Equal(Level1City.ArtistTileCount, imported.Count);
        Assert.Equal(ArtistPrefixOfShippedBlob, imported.ToBlob());
    }

    /// <summary>
    /// <b>Pens 1 and 5 were given to the art</b> — they were Bright Blue and
    /// Bright Magenta and nothing used either, and they are Pastel Cyan and
    /// Pink now (CLAUDE.md 7.1). The city sheet spends 58 pixels on pen 1,
    /// every one a bright highlight: the roof cap she stands on, the kerb at
    /// the top of the pavement, the lid of the air-conditioning unit. So
    /// quantising against the palette as it was before that swap has to come
    /// out different, and by how much is the measurement.
    /// </summary>
    [Fact]
    public void And_the_palette_is_the_engine_s_own()
    {
        var pens = CpcPalette.ReadGamePens(Golden.PaletteAsm);
        Assert.Equal(27, pens[1]);          // Pastel Cyan
        Assert.Equal(7, pens[5]);           // Pink

        var before = (int[])pens.Clone();
        before[1] = 21;                     // Bright Blue, as it was
        before[5] = 13;                     // Bright Magenta

        var theirs = Encode(pens);
        var wrong = Encode(before);
        var differing = theirs.Zip(wrong).Count(p => p.First != p.Second);

        Assert.Equal(ArtistPrefixOfShippedBlob, theirs);
        Assert.True(differing > 0,
            "the old palette produced the same bytes, so this check would pass "
            + "whichever palette the importer read");
    }

    /// <summary>
    /// The same 64 bytes in the other order. Every blitter in
    /// <c>tilemap.asm</c> paints a character column at a time, so
    /// column-major makes the step between lines one <c>INC L</c> — 64 T a
    /// raster against 76 (CLAUDE.md 9).
    /// </summary>
    [Fact]
    public void And_the_bytes_are_column_major()
    {
        var pens = CpcPalette.ReadGamePens(Golden.PaletteAsm);
        var source = AssetPack.TileSheet(LevelDir);
        var image = Png.Load(source.ImagePath);
        var frames = AssetPack.Frames(source.SheetJsonPath);

        var rowMajor = new List<byte>();
        foreach (var box in frames)
        {
            var tile = CpcPalette.Quantise(image, box.X, box.Y, box.Width, box.Height, pens);
            for (var y = 0; y < Tile.PixelHeight; y++)
                for (var x = 0; x < Tile.PixelWidth; x += 2)
                    rowMajor.Add(Mode0Layout.Encode(tile[y][x], tile[y][x + 1]));
        }

        Assert.Equal(ArtistPrefixOfShippedBlob.Length, rowMajor.Count);
        Assert.NotEqual(ArtistPrefixOfShippedBlob, rowMajor);
    }

    /// <summary>
    /// The names come out of <c>tile_table.json</c>, which is the only file
    /// in the package that has them for every sheet — and for level 1 the
    /// manifest states the same order independently, in prose, which is
    /// where <c>tools/make_city_map.py</c> reads it. <b>The two have to
    /// agree or the map's own bytes mean two different things.</b>
    /// </summary>
    [Fact]
    public void The_names_are_the_frame_order_and_both_sources_agree()
    {
        var source = AssetPack.TileSheet(LevelDir);

        Assert.Equal(Golden.CityTileNames(), source.TileNames);
        Assert.Equal(AssetPack.ManifestTileNames(LevelDir, "city_tiles"), source.TileNames);
        Assert.Equal("sky_stars", source.TileNames[0]);
        Assert.Equal("crate", source.TileNames[^1]);

        // ... and five of the nine sheets say nothing in the manifest at all
        Assert.Null(AssetPack.ManifestTileNames(
            Golden.Asset("sprites", "level2_forest"), "forest_tiles"));
    }

    /// <summary>
    /// <b>Nothing about a tile's pixels says whether it is an overlay.</b>
    /// Pen 0 is transparent in one and opaque black in the other, and the two
    /// populations overlap rather than sit either side of a threshold: over
    /// the six levels 69 tiles carry pen 0 and only 34 are overlays
    /// (CLAUDE.md 7.3). Here is level 1's share of that, counted.
    /// </summary>
    [Fact]
    public void An_overlay_is_the_table_s_word_and_not_the_pixels()
    {
        var tiles = Level1City.ArtistTiles().Tiles;
        var overlays = tiles.Where(t => t.IsOverlay).Select(t => t.Name).Order().ToArray();

        Assert.Equal(
            ["ac_unit", "antenna", "chimney", "lamp_pole", "lamp_top",
             "tank_00", "tank_01", "tank_10", "tank_11", "tank_20", "tank_21"],
            overlays);

        // ... AND THE RULE THAT GUESSES FROM THE PIXELS CANNOT BE SAVED BY
        // PICKING A BETTER NUMBER. Counted on the bytes the engine actually
        // gets — pen 0 after quantisation, which is the only thing a blitter
        // can see — level 1's eleven overlays run from 32 to 94 of their 128
        // pixels and its thirty opaque tiles from 0 to 128, with 27 of them
        // carrying some. The two populations overlap outright, so the best
        // threshold there is still gets twelve of the forty-one wrong:
        // sky_stars is 126 transparent-looking pixels and a plain copy.
        var transparent = tiles
            .Select(t => Enumerable.Range(0, Tile.PixelHeight)
                .Sum(y => Enumerable.Range(0, Tile.PixelWidth).Count(x => t.PenAt(x, y) == 0)))
            .ToArray();
        var worstCase = Enumerable.Range(0, Tile.PixelWidth * Tile.PixelHeight + 1)
            .Min(threshold => tiles
                .Where((t, i) => transparent[i] >= threshold != t.IsOverlay)
                .Count());

        Assert.Equal(12, worstCase);
        Assert.Equal(126, transparent[Level1City.ArtistTiles().IndexOf("sky_stars")]);
    }

    /// <summary>
    /// The flags are the editor's OUTPUT and never its input: nothing in the
    /// art package states what a cell does, so <see cref="LevelFlagSeeds"/>
    /// is where level 1's start (CLAUDE.md 11 step 7).
    /// </summary>
    [Fact]
    public void The_flags_are_the_editor_s_own_data()
    {
        var flags = new TileFlagsExporter().Write(Level1City.ArtistTiles());

        Assert.Equal(Golden.CityTileFlags[..Level1City.ArtistTileCount], flags);
    }

    /// <summary>
    /// <b>Every tile sheet in the package, not just the one with a golden
    /// file.</b> Nine sheets across six levels, and the two routes to a
    /// tile's name are both in it: levels 3 and 5 carry <c>tile_names</c>
    /// and the other four state the frame order in the sheet's prose.
    /// <para>
    /// The counts are CLAUDE.md 7.3's own table, so this pins that table as
    /// well as the reader: 275 tiles and 34 overlays, with forest, undersea
    /// and desert at zero because their sheets have no pen 0 in them at all.
    /// </para>
    /// </summary>
    [Theory]
    [InlineData("level1_city", "city_tiles", 41, 11)]
    [InlineData("level2_forest", "forest_tiles", 42, 0)]
    [InlineData("level3_cave", "cave_tiles", 47, 9)]
    [InlineData("level3_cave", "cave_quake", 13, 8)]
    [InlineData("level4_underwater", "sea_tiles", 42, 0)]
    [InlineData("level5_desert", "desert_tiles", 41, 0)]
    [InlineData("level5_desert", "desert_quicksand", 4, 0)]
    [InlineData("level6_station", "station_tiles", 39, 0)]
    [InlineData("level6_station", "station_laser", 6, 6)]
    public void Every_level_s_tiles_import(string level, string sheet, int tiles, int overlays)
    {
        var tileset = AssetPackImporter.ImportTileset(
            Golden.Asset("sprites", level), Golden.PaletteAsm,
            new Dictionary<string, TileFlags>(), sheet);

        Assert.Equal(tiles, tileset.Count);
        Assert.Equal(overlays, tileset.Tiles.Count(t => t.IsOverlay));
        Assert.All(tileset.Tiles, t => Assert.Equal(Tile.ByteCount, t.Bytes.Length));
        Assert.Equal(tiles, tileset.Tiles.Select(t => t.Name).Distinct().Count());
    }

    private static byte[] Encode(int[] pens)
    {
        var source = AssetPack.TileSheet(LevelDir);
        var image = Png.Load(source.ImagePath);
        var blob = new List<byte>();
        foreach (var box in AssetPack.Frames(source.SheetJsonPath))
            blob.AddRange(Tile.Encode(
                CpcPalette.Quantise(image, box.X, box.Y, box.Width, box.Height, pens)));
        return [.. blob];
    }
}
