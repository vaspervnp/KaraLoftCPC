using CpcLevelEditor.Application;
using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.Tests;

/// <summary>
/// A project is the level as the DESIGNER holds it — the artist's tiles with
/// an overlay layer over them — and the witness that the two forms are the
/// same level is that taking the shipped City apart and putting it back
/// gives the shipped bytes.
/// </summary>
public class ProjectTests
{
    /// <summary>
    /// <b>The whole round trip, and it closes the one gap the format has.</b>
    /// The engine's map cell is a finished tile, so nothing in
    /// <c>level_&lt;n&gt;.lvl</c> says which cells were an overlay on a wall;
    /// the bake's own sidecar does, and with it a shipped level opens as
    /// something paintable and exports back to the same picture.
    /// <para>
    /// <b>THE SAME PICTURE AND NOT THE SAME MAP BYTES, AND THAT IS
    /// §8.3's RULE RATHER THAN A CONCESSION.</b> A pair takes its index the
    /// first time it is placed, so the numbering follows the ORDER the
    /// placements arrive in: <c>make_city_map.py</c> sweeps prop by prop and
    /// a painter lays them down row by row, and neither is more correct.
    /// What has to agree is what a cell SHOWS and what it DOES — so this
    /// compares the whole level as pixels, 2,048 cells of 64 bytes, and the
    /// attribute byte under each one.
    /// </para>
    /// </summary>
    [Fact]
    public void The_shipped_city_taken_apart_and_put_back_IS_the_same_picture()
    {
        var project = CitySource.Open();
        var result = ProjectExporter.Export(project, CitySource.ArtistTiles(project));
        var shipped = new BinaryLevelReader().Read(Golden.Level1);
        var exported = new BinaryLevelReader().Read(result.Level);

        Assert.Equal(Golden.CityTiles.Length, result.Tiles.Length);
        Assert.Equal(Picture(shipped.Map, Golden.CityTiles), Picture(exported.Map, result.Tiles));
        Assert.Equal(
            Attributes(shipped.Map, Golden.CityTileFlags),
            Attributes(exported.Map, result.TileFlags));

        // ... and everything that is not the map is byte for byte
        Assert.Equal(Golden.Level1.Length, result.Level.Length);
        Assert.Equal(shipped.Entities, exported.Entities);
        Assert.Equal(shipped.Links, exported.Links);
        Assert.Equal(shipped.Regions, exported.Regions);
        Assert.Equal(Golden.Level1[..LevelFormat.HeaderBytes],
                     result.Level[..LevelFormat.HeaderBytes]);
    }

    /// <summary>
    /// ... and the overlay layer is really carrying the picture: move one
    /// placement a cell along and the file changes.
    /// </summary>
    [Fact]
    public void And_the_overlay_layer_is_what_puts_the_lamp_on_the_wall()
    {
        var project = CitySource.Open();
        Assert.NotEmpty(project.Overlays);

        var moved = project.Overlays[0];
        project.Overlays[0] = moved with { X = moved.X + 1 };
        var result = ProjectExporter.Export(project, CitySource.ArtistTiles(project));

        var shipped = new BinaryLevelReader().Read(Golden.Level1);
        var moved_ = new BinaryLevelReader().Read(result.Level);
        Assert.NotEqual(Picture(shipped.Map, Golden.CityTiles),
                        Picture(moved_.Map, result.Tiles));
    }

    /// <summary>The whole level as pixels: every cell's 64 bytes, in order.</summary>
    private static byte[] Picture(byte[] map, byte[] tiles)
    {
        var picture = new byte[map.Length * Tile.ByteCount];
        for (var cell = 0; cell < map.Length; cell++)
            tiles.AsSpan(map[cell] * Tile.ByteCount, Tile.ByteCount)
                 .CopyTo(picture.AsSpan(cell * Tile.ByteCount));
        return picture;
    }

    /// <summary>... and what every cell DOES, which travels in the sibling file.</summary>
    private static byte[] Attributes(byte[] map, byte[] flags) =>
        [.. map.Select(tile => tile < flags.Length ? flags[tile] : (byte)0)];

    private sealed class SequenceComparer : IEqualityComparer<byte[]>
    {
        public bool Equals(byte[]? a, byte[]? b) => a is not null && b is not null && a.SequenceEqual(b);

        public int GetHashCode(byte[] a) => a.Aggregate(17, (h, v) => h * 31 + v);
    }

    /// <summary>
    /// The un-bake recovers the pairing the file cannot state, including the
    /// one that stands on another composite — the water tank's corner over
    /// the air-conditioning unit, which is why the bake resolves by
    /// recursion (CLAUDE.md 7.3).
    /// </summary>
    [Fact]
    public void The_map_comes_back_to_the_artist_s_own_tiles()
    {
        var project = CitySource.Open();

        Assert.All(project.Map, tile => Assert.True(tile < Level1City.ArtistTileCount));
        Assert.Equal(
            Golden.CityBaked.Count(r => r.Baked),
            project.Overlays
                .Select(o => (o.Overlay, Under: project.Map[o.Y * project.Width + o.X]))
                .Distinct().Count());

        // THE CHAINED PAIR: two placements land on one cell and the second
        // one's background is the first one's composite - the water tank's
        // top-right corner over the air-conditioning unit, which is why the
        // bake resolves by recursion. One PAIR, and the level places it in
        // three cells.
        var twice = project.Overlays.GroupBy(o => (o.X, o.Y)).Where(g => g.Count() > 1).ToArray();
        Assert.Equal(3, twice.Length);
        Assert.All(twice, g => Assert.Equal(2, g.Count()));
        Assert.Single(twice.Select(g => g.Select(o => o.Overlay).Order().ToArray()).Distinct(
            new SequenceComparer()));
    }

    [Fact]
    public void A_project_survives_the_store()
    {
        var root = CitySource.TemporaryRoot();
        try
        {
            var store = new FileProjectStore(root);
            var project = CitySource.Open();
            store.Save(project);

            Assert.Equal(["city"], store.List());
            var back = store.Load("city");

            Assert.NotNull(back);
            Assert.Equal(project.Map, back.Map);
            Assert.Equal(project.Overlays, back.Overlays);
            Assert.Equal(project.Entities, back.Entities);
            Assert.Equal(project.TileFlags, back.TileFlags);
            Assert.Equal(
                ProjectExporter.Export(project, CitySource.ArtistTiles(project)).Level,
                ProjectExporter.Export(back, CitySource.ArtistTiles(back)).Level);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    /// <summary>
    /// An id becomes a file name, so it is a slug or it is nothing: a store
    /// that took one from an HTTP route unchecked is a directory traversal.
    /// </summary>
    [Theory]
    [InlineData("city", true)]
    [InlineData("level_1-draft", true)]
    [InlineData("../../etc/passwd", false)]
    [InlineData("city/../city", false)]
    [InlineData("", false)]
    public void An_id_is_a_slug(string id, bool allowed)
    {
        Assert.Equal(allowed, FileProjectStore.IsValidId(id));
    }

    [Fact]
    public void The_shipped_city_validates()
    {
        var project = CitySource.Open();
        var findings = LevelValidator.Check(project, CitySource.ArtistTiles(project));

        // NOTHING AT ALL NOW, AND IT USED TO BE ONE WARNING. The shipped
        // City had no EK_PLAYER_START - its ten records were pickups, a
        // door, an NPC and three drones - because KARA_WX and KARA_WY
        // were assembler initialisers and nothing read a start record.
        // PLAYER_SPAWN does (CLAUDE.md 11 step 8), so the City carries
        // one and the level is clean.
        Assert.Empty(findings);
    }

    [Fact]
    public void A_level_with_no_start_record_is_a_level_that_says_so()
    {
        // ... and the rule that used to be exercised BY the shipped City
        // needs its own case now that the City satisfies it. A warning
        // and not an error: the engine leaves her where SCROLL_INIT last
        // put her, which is somewhere rather than nowhere.
        var project = CitySource.Open();
        project.Entities.RemoveAll(e => e.Kind == EntityKind.PlayerStart);
        Assert.Contains(LevelValidator.Check(
            project, CitySource.ArtistTiles(project)),
            f => f.Rule == "player-start" && f.Severity == Severity.Warning);
    }

    [Fact]
    public void And_the_validator_would_have_noticed()
    {
        var project = CitySource.Open();
        var tiles = CitySource.ArtistTiles(project);

        project.Map[0] = (byte)tiles.Count;
        Assert.Contains(LevelValidator.Check(project, tiles),
            f => f.Rule == "tile-index" && f.Severity == Severity.Error);
        project.Map[0] = 0;

        project.Overlays.Add(new OverlayPlacement(project.Width, 0, 0));
        Assert.Contains(LevelValidator.Check(project, tiles),
            f => f.Rule == "overlay-bounds" && f.Severity == Severity.Error);
        project.Overlays.RemoveAt(project.Overlays.Count - 1);

        // "concrete" is opaque in the artist's table, so as an overlay it
        // composites to itself.
        project.Overlays.Add(new OverlayPlacement(0, 0, (byte)tiles.IndexOf("concrete")));
        Assert.Contains(LevelValidator.Check(project, tiles),
            f => f.Rule == "overlay-opaque" && f.Severity == Severity.Warning);
        project.Overlays.RemoveAt(project.Overlays.Count - 1);

        project.Entities.Add(new Entity(EntityKind.Pickup, 9999, 0, EntityFlags.Active, 0, 0));
        Assert.Contains(LevelValidator.Check(project, tiles), f => f.Rule == "entity-bounds");
        project.Entities.RemoveAt(project.Entities.Count - 1);

        while (project.Entities.Count <= EngineLimits.MaxEntities)
            project.Entities.Add(new Entity(EntityKind.Pickup, 0, 0, EntityFlags.Active, 0, 0));
        Assert.Contains(LevelValidator.Check(project, tiles), f => f.Rule == "engine-limits");
    }
}
