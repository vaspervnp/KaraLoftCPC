using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;
using CpcLevelEditor.Exporters;

namespace CpcLevelEditor.IntegrationTests;

/// <summary>
/// The painter's API, over real HTTP into a real host.
/// </summary>
/// <remarks>
/// The check that matters is the last one: a level opened through the API
/// and exported through the API comes back as <b>the same picture</b> the
/// game ships — 2,048 cells of 64 bytes, compared as pixels. Everything
/// between here and the Z80 is in that one equality.
/// </remarks>
public sealed class ApiTests(EditorApp app) : IClassFixture<EditorApp>
{
    private static readonly JsonSerializerOptions Json =
        new(JsonSerializerDefaults.Web);

    [Fact]
    public async Task The_page_is_served()
    {
        var response = await app.As(EditorApp.Admin).GetAsync("/");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("canvas", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task The_art_package_is_listed()
    {
        var levels = await app.As(EditorApp.Admin)
            .GetFromJsonAsync<List<LevelAssetsDto>>("/api/assets", Json);

        Assert.NotNull(levels);
        Assert.Equal(6, levels.Count);
        Assert.Contains(levels, l => l.Level == "level1_city" && l.Sheets.Contains("city_tiles"));
        // level 3 carries the quake's flood as a second sheet and level 6 the lasers
        Assert.Equal(2, levels.Single(l => l.Level == "level3_cave").Sheets.Count);
    }

    [Fact]
    public async Task An_id_that_is_not_a_slug_is_refused()
    {
        var client = app.As(EditorApp.Admin);

        var made = await client.PostAsJsonAsync("/api/projects",
            new { id = "../escape", name = "no" }, Json);
        Assert.Equal(HttpStatusCode.BadRequest, made.StatusCode);

        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/projects/..")).StatusCode);
    }

    /// <summary>
    /// <b>A vertical level is started as one</b> — the width is the only
    /// thing a new project has to be told, because every shape the engine
    /// installs is 2,048 bytes and the height follows (CLAUDE.md 8.3).
    /// <c>tools/test_shape.py</c> is the half of this that runs on a 6128.
    /// </summary>
    [Theory]
    [InlineData(32, 64, true)]
    [InlineData(64, 32, true)]
    [InlineData(0, 16, true)]           // ... and no width at all is the City
    [InlineData(96, 0, false)]
    [InlineData(16, 0, false)]          // 2,048 bytes, and still refused
    public async Task A_project_is_started_in_a_shape_the_engine_installs(
        int width, int height, bool taken)
    {
        var client = app.As(EditorApp.Admin);
        var id = "shape-" + Guid.NewGuid().ToString("N")[..8];

        var created = await client.PostAsJsonAsync("/api/projects",
            new { id, name = "a shaft", assetLevel = "level3_cave",
                  sheet = "cave_tiles", width }, Json);

        if (!taken)
        {
            Assert.Equal(HttpStatusCode.BadRequest, created.StatusCode);
            return;
        }
        created.EnsureSuccessStatusCode();
        var project = await created.Content.ReadFromJsonAsync<ProjectDto>(Json);
        Assert.NotNull(project);
        Assert.Equal(width == 0 ? EngineLimits.MapWidth : width, project.Width);
        Assert.Equal(height, project.Height);
        Assert.Equal(EngineLimits.MapBytes,
                     Convert.FromBase64String(project.Map).Length);
    }

    /// <summary>
    /// And the shapes are the ENGINE's list, served rather than spelled out
    /// in the canvas — the same rule <c>/api/vocabulary</c> follows for every
    /// other enum the inspector offers.
    /// </summary>
    [Fact]
    public async Task The_vocabulary_serves_every_shape_the_engine_installs()
    {
        var client = app.As(EditorApp.Admin);
        var vocab = await client.GetFromJsonAsync<VocabularyDto>(
            "/api/vocabulary", Json);

        Assert.NotNull(vocab);
        Assert.Equal(EngineLimits.MapShapes.Count(),
                     vocab.Limits.MapShapes.Count);
        foreach (var s in vocab.Limits.MapShapes)
        {
            Assert.True(EngineLimits.IsMapShape(s.Width, s.Height));
            Assert.Equal(EngineLimits.MapBytes, s.Width * s.Height);
        }
    }

    [Fact]
    public async Task The_shipped_city_opens_paintable_and_exports_to_the_same_picture()
    {
        var client = app.As(EditorApp.Admin);
        var id = "city-" + Guid.NewGuid().ToString("N")[..8];

        var created = await client.PostAsJsonAsync("/api/projects",
            new { id, name = "the City", seed = "shipped" }, Json);
        created.EnsureSuccessStatusCode();
        var project = await created.Content.ReadFromJsonAsync<ProjectDto>(Json);

        Assert.NotNull(project);
        Assert.Equal(EngineLimits.MapWidth, project.Width);
        Assert.NotEmpty(project.Overlays);
        Assert.NotEmpty(project.Entities);

        // ... and every cell is one of the ARTIST's tiles again, which is
        // what the overlay layer bought: the shipped map's composites have
        // been taken back apart.
        var tileset = await client.GetFromJsonAsync<TilesetDto>(
            $"/api/projects/{id}/tileset", Json);
        Assert.NotNull(tileset);
        Assert.Equal(41, tileset.Tiles.Count);
        Assert.Equal(16, tileset.Palette.Count);
        Assert.All(Convert.FromBase64String(project.Map),
                   tile => Assert.True(tile < tileset.Tiles.Count));

        var exported = await client.PostAsync($"/api/projects/{id}/export", null);
        exported.EnsureSuccessStatusCode();
        var result = await exported.Content.ReadFromJsonAsync<ExportDto>(Json);

        Assert.NotNull(result);
        Assert.DoesNotContain(result.Findings, f => f.Severity == "Error");
        // FOUR FILES AND NOT THREE. The fourth is the bake's own record,
        // and without it this export is a level the editor could never open
        // again - its own included, because a map cell is a finished tile
        // and nothing in the .lvl says which cells were an overlay on a
        // wall (CLAUDE.md 7.3, 8.3).
        Assert.Equal(
            new[] { "level_1.lvl", "tileflags_level1_city.bin",
                    "citytiles.bin", "city_baked.json" },
            result.Files.Select(f => f.Name));
        Assert.Equal(10, result.Pairs.Count(p => p.Baked));

        var shippedLevel = File.ReadAllBytes(Path.Combine(EditorApp.RepoRoot, "build", "level_1.lvl"));
        var shippedTiles = File.ReadAllBytes(Path.Combine(
            EditorApp.RepoRoot, "build", "levels", "level1_city", "citytiles.bin"));
        var ourLevel = Convert.FromBase64String(result.Files[0].Bytes);
        var ourTiles = Convert.FromBase64String(result.Files[2].Bytes);

        Assert.Equal(shippedLevel.Length, ourLevel.Length);
        Assert.Equal(shippedTiles.Length, ourTiles.Length);
        Assert.Equal(
            Picture(new BinaryLevelReader().Read(shippedLevel).Map, shippedTiles),
            Picture(new BinaryLevelReader().Read(ourLevel).Map, ourTiles));

        // ... and the four files are on disk, which is where the build
        // reads them from
        Assert.NotNull(result.Directory);
        foreach (var file in result.Files)
        {
            var path = Path.Combine(result.Directory, file.Name);
            Assert.True(File.Exists(path), path);
            Assert.Equal(file.Length, new FileInfo(path).Length);
        }
    }

    /// <summary>
    /// <b>A stale version is refused rather than merged.</b> Two windows on
    /// one level is where a lost stroke is silent, and a level is source.
    /// </summary>
    [Fact]
    public async Task An_edit_against_a_stale_version_is_refused()
    {
        var client = app.As(EditorApp.Admin);
        var id = "edit-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects", new { id, name = "scratch" }, Json);

        var first = await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = 0, ops = new[] { new { op = "tile", x = 3, y = 4, tile = 7 } } }, Json);
        first.EnsureSuccessStatusCode();
        var applied = await first.Content.ReadFromJsonAsync<EditResultDto>(Json);
        Assert.Equal(1, applied!.Version);

        var stale = await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = 0, ops = new[] { new { op = "tile", x = 3, y = 4, tile = 9 } } }, Json);
        Assert.Equal(HttpStatusCode.Conflict, stale.StatusCode);

        var project = await client.GetFromJsonAsync<ProjectDto>($"/api/projects/{id}", Json);
        Assert.Equal(7, Convert.FromBase64String(project!.Map)[4 * EngineLimits.MapWidth + 3]);
    }

    [Fact]
    public async Task An_edit_off_the_map_is_refused()
    {
        var client = app.As(EditorApp.Admin);
        var id = "bounds-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects", new { id, name = "scratch" }, Json);

        var response = await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = 0, ops = new[] { new { op = "tile", x = 999, y = 0, tile = 1 } } },
            Json);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    /// <summary>
    /// <b>A record placed on the canvas reaches the file.</b> An entity and a
    /// region go in over HTTP, the level is exported over HTTP, and the bytes
    /// are read back by the independent reader: the eight-byte record in the
    /// engine's own layout and the seven-byte one that must not be padded to
    /// eight (docs/editor.md 9.2).
    /// </summary>
    [Fact]
    public async Task An_entity_and_a_region_placed_through_the_API_reach_the_file()
    {
        var client = app.As(EditorApp.Admin);
        var id = "records-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects", new { id, name = "records" }, Json);

        // The vocabulary is where the browser gets its lists, so the test uses
        // it too rather than spelling the enums out a second time.
        var vocabulary = await client.GetFromJsonAsync<VocabularyDto>("/api/vocabulary", Json);
        Assert.NotNull(vocabulary);
        Assert.Equal(EngineLimits.MaxEntities, vocabulary.Limits.MaxEntities);
        Assert.Contains("Enemy", vocabulary.Lists["EntityKind"]);
        Assert.Equal("Active, Touch", vocabulary.DefaultFlags["Pickup"]);

        // EVERY LIST A PARAMETER NAMES HAS TO BE IN THE DOCUMENT, because the
        // browser resolves it by name and a missing one is a number box where
        // a list was meant - which is what an enemy's p0 was until EnemyKind
        // existed.
        foreach (var (kind, parameters) in vocabulary.Params)
            foreach (var options in parameters.Select(p => p.Options).Where(o => o is not null))
                Assert.True(vocabulary.Lists.ContainsKey(options!),
                    $"{kind} names the list \"{options}\" and the vocabulary has "
                    + string.Join(", ", vocabulary.Lists.Keys));
        Assert.Equal("EnemyKind", vocabulary.Params["Enemy"][0].Options);

        var edit = await client.PatchAsJsonAsync($"/api/projects/{id}", new
        {
            version = 0,
            ops = new object[]
            {
                new { op = "entity-add", entity = new
                    { kind = "Enemy", x = 36 * 8, y = 5 * 16, flags = "Active", p0 = 1, p1 = 4 } },
                new { op = "region-add", region = new
                    { kind = "CameraLock", x = 10, y = 2, width = 6, height = 4 } },
            },
        }, Json);
        edit.EnsureSuccessStatusCode();
        Assert.Equal(2, (await edit.Content.ReadFromJsonAsync<EditResultDto>(Json))!.Applied);

        var exported = await client.PostAsync($"/api/projects/{id}/export", null);
        exported.EnsureSuccessStatusCode();
        var result = await exported.Content.ReadFromJsonAsync<ExportDto>(Json);
        var level = new BinaryLevelReader().Read(
            Convert.FromBase64String(result!.Files[0].Bytes));

        var entity = Assert.Single(level.Entities);
        Assert.Equal(EntityKind.Enemy, entity.Kind);
        Assert.Equal(288, entity.X);
        Assert.Equal(80, entity.Y);
        Assert.Equal(EntityFlags.Active, entity.Flags);
        // p0 IS WHICH CHARACTER and p1 the patrol half-width, which is the way
        // round make_city_map.py writes them and the opposite of what
        // editor.md's appendix says (CLAUDE.md 8.6).
        Assert.Equal(1, entity.P0);
        Assert.Equal(4, entity.P1);

        var region = Assert.Single(level.Regions);
        Assert.Equal(RegionKind.CameraLock, region.Kind);
        Assert.Equal(10, region.X);
        Assert.Equal(2, region.Y);
        Assert.Equal(6, region.Width);
        Assert.Equal(4, region.Height);
    }

    /// <summary>
    /// ... and the ones the engine could not be given do not: the table holds
    /// <c>ENT_MAX</c> records and a region is measured against the map.
    /// </summary>
    [Fact]
    public async Task A_record_the_engine_could_not_take_is_refused()
    {
        var client = app.As(EditorApp.Admin);
        var id = "refused-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects", new { id, name = "scratch" }, Json);

        var tooMany = await client.PatchAsJsonAsync($"/api/projects/{id}", new
        {
            version = 0,
            ops = Enumerable.Range(0, EngineLimits.MaxEntities + 1).Select(i => new
            {
                op = "entity-add",
                entity = new { kind = "Checkpoint", x = i * 8, y = 96, flags = "Active", p0 = 0, p1 = 0 },
            }).ToArray(),
        }, Json);
        Assert.Equal(HttpStatusCode.BadRequest, tooMany.StatusCode);

        var offMap = await client.PatchAsJsonAsync($"/api/projects/{id}", new
        {
            version = 0,
            ops = new object[] { new { op = "region-add", region = new
                { kind = "Water", x = 126, y = 0, width = 6, height = 2 } } },
        }, Json);
        Assert.Equal(HttpStatusCode.BadRequest, offMap.StatusCode);

        // AND NOTHING WAS KEPT. A rejected batch mutates the object it was
        // handed and is never saved, so the level on disk is untouched — which
        // is what makes "reload" the only thing a client has to do.
        var project = await client.GetFromJsonAsync<ProjectDto>($"/api/projects/{id}", Json);
        Assert.Empty(project!.Entities);
        Assert.Empty(project.Regions);
        Assert.Equal(0, project.Version);
    }

    /// <summary>
    /// <b>Any environment of the package, not only the City.</b> A blank
    /// project takes its tile sheet from the art, its ENVIRONMENT from the
    /// package's own directory name, and its LEVEL number from the first
    /// slot of that environment's block — the forest is environment 2 and
    /// its levels are 5 to 8. It starts with no tile flags at all, because
    /// nothing in the package says what a tile does (CLAUDE.md 11 step 7).
    /// <para>
    /// This used to expect <c>level_2.lvl</c>, from when there was one level
    /// an environment and the two numbers were the same one.
    /// </para>
    /// </summary>
    [Fact]
    public async Task A_new_project_can_be_started_on_any_level_of_the_package()
    {
        var client = app.As(EditorApp.Admin);
        var id = "forest-" + Guid.NewGuid().ToString("N")[..8];

        var made = await client.PostAsJsonAsync("/api/projects", new
        {
            id, name = "the forest", assetLevel = "level2_forest", sheet = "forest_tiles",
        }, Json);
        made.EnsureSuccessStatusCode();

        var tileset = await client.GetFromJsonAsync<TilesetDto>(
            $"/api/projects/{id}/tileset", Json);
        Assert.Equal(42, tileset!.Tiles.Count);          // CLAUDE.md 7.3's own table
        Assert.All(tileset.Tiles, t => Assert.Equal(0, t.Flags));

        var exported = await client.PostAsync($"/api/projects/{id}/export", null);
        var result = await exported.Content.ReadFromJsonAsync<ExportDto>(Json);
        Assert.Equal(
            new[] { "level_5.lvl", "tileflags_level2_forest.bin",
                    "foresttiles.bin", "forest_baked.json" },
            result!.Files.Select(f => f.Name));
        var level = new BinaryLevelReader()
            .Read(Convert.FromBase64String(result.Files[0].Bytes));
        Assert.Equal(EngineLimits.FirstLevelOf(2), level.LevelId);
        Assert.Equal(2, level.TilesetId);       // ... and the two are separate
    }

    /// <summary>
    /// <b>And the level number is the designer's, inside its own block.</b>
    /// <c>DISC_LEVEL_MAPS</c> has one entry a level, so the number is what
    /// the disc is indexed by; the environment is what <c>LEVEL_GOTO</c>
    /// loads art from. Moving a forest project to level 7 is allowed and
    /// moving it to level 3 is not, because 3 is the City's and nothing on
    /// the hardware would say which map had been overwritten.
    /// </summary>
    [Fact]
    public async Task A_level_can_be_renumbered_inside_its_own_environment()
    {
        var client = app.As(EditorApp.Admin);
        var id = "forest-" + Guid.NewGuid().ToString("N")[..8];

        (await client.PostAsJsonAsync("/api/projects", new
        {
            id, name = "the forest", assetLevel = "level2_forest", sheet = "forest_tiles",
        }, Json)).EnsureSuccessStatusCode();

        var moved = await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = 0, ops = new[] { new { op = "level-id", index = 7 } } }, Json);
        moved.EnsureSuccessStatusCode();

        var exported = await client.PostAsync($"/api/projects/{id}/export", null);
        var result = await exported.Content.ReadFromJsonAsync<ExportDto>(Json);
        Assert.Equal("level_7.lvl", result!.Files[0].Name);

        // ... and the control: the City's block is refused, on the stroke.
        var project = await client.GetFromJsonAsync<ProjectDto>($"/api/projects/{id}", Json);
        var refused = await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = project!.Version, ops = new[] { new { op = "level-id", index = 3 } } },
            Json);
        Assert.Equal(HttpStatusCode.BadRequest, refused.StatusCode);
    }

    private static byte[] Picture(byte[] map, byte[] tiles)
    {
        var picture = new byte[map.Length * Tile.ByteCount];
        for (var cell = 0; cell < map.Length; cell++)
            tiles.AsSpan(map[cell] * Tile.ByteCount, Tile.ByteCount)
                 .CopyTo(picture.AsSpan(cell * Tile.ByteCount));
        return picture;
    }

    /// <summary>
    /// <b>A blank project is filled in with a level that plays, over HTTP,
    /// and the server's own validator has nothing to say about it.</b>
    /// </summary>
    /// <remarks>
    /// The unit suite checks the plan; this checks the ROUTE — that the
    /// generated map and records are what the store kept and what the
    /// exporter then reads. The export is the witness rather than the
    /// response: it runs the same seven designer rules a painted level
    /// meets, on the bytes the engine would be given.
    /// <c>scratchpad/disc_from.py</c> is the half of it that runs on a 6128.
    /// </remarks>
    [Theory]
    [InlineData(32)]
    [InlineData(64)]
    [InlineData(128)]
    public async Task A_generated_level_goes_through_the_API_and_exports_clean(int width)
    {
        var client = app.As(EditorApp.Admin);
        var id = "gen-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects",
            new { id, name = "generated", width }, Json);

        var response = await client.PostAsJsonAsync(
            $"/api/projects/{id}/generate", new { version = 0 }, Json);
        response.EnsureSuccessStatusCode();
        var made = await response.Content.ReadFromJsonAsync<GeneratedDto>(Json);

        Assert.NotNull(made);
        Assert.Equal(1, made.Version);
        Assert.True(made.Floors >= 2, $"{made.Floors} floor(s)");
        Assert.Equal(made.Floors - 1, made.Ladders);
        Assert.True(made.Pickups >= 1 && made.Enemies >= 1);
        // The roles are the FLAGS' and not the names', so what they came
        // out as is read back off the tileset rather than written here.
        var tileset = await client.GetFromJsonAsync<TilesetDto>(
            $"/api/projects/{id}/tileset", Json);
        var floor = tileset!.Tiles.Single(t => t.Name == made.FloorTile);
        var ladder = tileset.Tiles.Single(t => t.Name == made.LadderTile);
        Assert.Equal((byte)TileFlags.Solid, (byte)(floor.Flags & (byte)TileFlags.Solid));
        Assert.Equal((byte)(TileFlags.Ladder | TileFlags.Platform), ladder.Flags);
        Assert.Equal(0, tileset.Tiles.Single(t => t.Name == made.BackgroundTile).Flags);

        // ... and the level the store kept is one the exporter will take
        var exported = await client.PostAsync($"/api/projects/{id}/export", null);
        exported.EnsureSuccessStatusCode();
        var result = await exported.Content.ReadFromJsonAsync<ExportDto>(Json);
        Assert.NotNull(result);
        Assert.DoesNotContain(result.Findings,
            f => f.Severity == "Error" || f.Severity == "Warning");

        var level = new BinaryLevelReader().Read(
            Convert.FromBase64String(result.Files[0].Bytes));
        Assert.Equal(width, level.Width);
        Assert.Equal(EngineLimits.MapBytes / width, level.Height);
        Assert.Equal(made.Pickups + made.Enemies + 2, level.Entities.Count);
    }

    /// <summary>
    /// <b>And a project with nothing marked is refused with the role it is
    /// missing named</b> — five of the six art packages have no flag seeds
    /// at all (<see cref="LevelFlagSeeds"/>), so this is the state a new
    /// forest project is really in, not a contrived one.
    /// </summary>
    [Fact]
    public async Task A_project_with_no_floor_in_it_is_refused_and_says_so()
    {
        var client = app.As(EditorApp.Admin);
        var id = "gen-bare-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects",
            new { id, name = "a forest", assetLevel = "level2_forest",
                  sheet = "forest_tiles" }, Json);

        var response = await client.PostAsJsonAsync(
            $"/api/projects/{id}/generate", new { version = 0 }, Json);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Contains("Solid", await response.Content.ReadAsStringAsync());

        var project = await client.GetFromJsonAsync<ProjectDto>($"/api/projects/{id}", Json);
        Assert.Equal(0, project!.Version);          // and nothing was written
    }

    /// <summary>
    /// <b>Generate takes the version check every other change takes.</b> It
    /// replaces the whole map, so a stale one is the one edit in this editor
    /// whose loss could not be reconstructed from the canvas.
    /// </summary>
    [Fact]
    public async Task A_generate_against_a_stale_version_is_refused()
    {
        var client = app.As(EditorApp.Admin);
        var id = "gen-stale-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects", new { id, name = "scratch" }, Json);
        await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = 0, ops = new[] { new { op = "tile", x = 3, y = 4, tile = 7 } } }, Json);

        var stale = await client.PostAsJsonAsync(
            $"/api/projects/{id}/generate", new { version = 0 }, Json);

        Assert.Equal(HttpStatusCode.Conflict, stale.StatusCode);
        var project = await client.GetFromJsonAsync<ProjectDto>($"/api/projects/{id}", Json);
        Assert.Equal(1, project!.Version);
        Assert.Equal(7, Convert.FromBase64String(project.Map)[4 * EngineLimits.MapWidth + 3]);
    }

    private sealed record GeneratedDto(
        int Version, int Floors, int Ladders, int Holes, int Pickups, int Enemies,
        string FloorTile, string LadderTile, string BackgroundTile);

    private sealed record LevelAssetsDto(string Level, List<string> Sheets);
    private sealed record ProjectDto(
        string Id, string Name, int Width, int Height, int Version, string Map,
        List<JsonElement> Overlays, List<JsonElement> Entities, List<JsonElement> Regions);
    private sealed record TileDto(string Name, bool Overlay, byte Flags);
    private sealed record TilesetDto(
        List<int[]> Palette, List<TileDto> Tiles, string Pens);
    private sealed record FindingDto(string Severity, string Rule, string Message);
    private sealed record FileDto(string Name, int Length, string Bytes);
    private sealed record PairDto(int Index, int Over, int Under, string Name, bool Baked);
    private sealed record ExportDto(
        List<FileDto> Files, List<PairDto> Pairs, List<FindingDto> Findings,
        string? Directory);
    private sealed record EditResultDto(int Version, int Applied);
    private sealed record LimitsDto(
        int MaxEntities, int MapWidth, int MapHeight,
        IReadOnlyList<MapShapeDto> MapShapes);

    private sealed record MapShapeDto(int Width, int Height);
    private sealed record ParamDto(string Label, string? Options);
    private sealed record VocabularyDto(
        Dictionary<string, List<string>> Lists, Dictionary<string, ParamDto[]> Params,
        Dictionary<string, string> DefaultFlags, LimitsDto Limits);
}
