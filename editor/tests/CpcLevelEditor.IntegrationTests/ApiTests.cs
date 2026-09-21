using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
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
        var response = await app.CreateClient().GetAsync("/");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Contains("canvas", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task The_art_package_is_listed()
    {
        var levels = await app.CreateClient()
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
        var client = app.CreateClient();

        var made = await client.PostAsJsonAsync("/api/projects",
            new { id = "../escape", name = "no" }, Json);
        Assert.Equal(HttpStatusCode.BadRequest, made.StatusCode);

        Assert.Equal(HttpStatusCode.NotFound, (await client.GetAsync("/api/projects/..")).StatusCode);
    }

    [Fact]
    public async Task The_shipped_city_opens_paintable_and_exports_to_the_same_picture()
    {
        var client = app.CreateClient();
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
        Assert.Equal(3, result.Files.Count);
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

        // ... and the three files are on disk, which is where the build
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
        var client = app.CreateClient();
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
        var client = app.CreateClient();
        var id = "bounds-" + Guid.NewGuid().ToString("N")[..8];
        await client.PostAsJsonAsync("/api/projects", new { id, name = "scratch" }, Json);

        var response = await client.PatchAsJsonAsync($"/api/projects/{id}",
            new { version = 0, ops = new[] { new { op = "tile", x = 999, y = 0, tile = 1 } } },
            Json);

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }

    private static byte[] Picture(byte[] map, byte[] tiles)
    {
        var picture = new byte[map.Length * Tile.ByteCount];
        for (var cell = 0; cell < map.Length; cell++)
            tiles.AsSpan(map[cell] * Tile.ByteCount, Tile.ByteCount)
                 .CopyTo(picture.AsSpan(cell * Tile.ByteCount));
        return picture;
    }

    private sealed record LevelAssetsDto(string Level, List<string> Sheets);
    private sealed record ProjectDto(
        string Id, string Name, int Width, int Height, int Version, string Map,
        List<JsonElement> Overlays, List<JsonElement> Entities);
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
}
