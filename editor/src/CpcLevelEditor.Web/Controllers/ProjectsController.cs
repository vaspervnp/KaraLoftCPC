using CpcLevelEditor.Application;
using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;
using CpcLevelEditor.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace CpcLevelEditor.Web.Controllers;

[ApiController]
[Route("api")]
public sealed class ProjectsController(
    IProjectStore store, AssetCatalogue assets, EditorOptions options,
    UserWorkspace workspace) : ControllerBase
{
    /// <summary>The art the editor can paint out of.</summary>
    [HttpGet("assets")]
    public IReadOnlyList<LevelAssets> Assets() =>
        [.. assets.Levels().Select(level => new LevelAssets(level, assets.Sheets(level)))];

    /// <summary>
    /// <b>Every enum the browser has to offer a designer, by name.</b>
    /// </summary>
    /// <remarks>
    /// A canvas that listed the entity kinds itself would be a second copy of
    /// <see cref="EntityKind"/>, in a language with no suite pointed at it —
    /// the same class of bug as two copies of a bit table (CLAUDE.md 6.3),
    /// and the reason enums already go over the wire by name rather than as
    /// numbers. So the lists come from the enums themselves, and the
    /// parameter labels come from <see cref="Entity"/>'s own table of what
    /// <c>p0</c> and <c>p1</c> mean per kind (CLAUDE.md 8.6).
    /// </remarks>
    [HttpGet("vocabulary")]
    public VocabularyView Vocabulary() => VocabularyView.Current;

    [HttpGet("projects")]
    public IReadOnlyList<ProjectSummary> List() =>
        [.. store.List()
            .Select(store.Load).OfType<EditorProject>()
            .Select(p => new ProjectSummary(p.Id, p.Name, p.AssetLevel, p.Sheet, p.Version))];

    [HttpGet("projects/{id}")]
    public ActionResult<ProjectView> Get(string id) =>
        Find(id, out var project) ? ProjectView.Of(project) : NotFound(id);

    /// <summary>
    /// A new project — empty, or <b>opened from the level the game already
    /// plays</b>. The second is the interesting one: the shipped
    /// <c>.lvl</c> holds composited tiles and no pairing, so the bake's own
    /// sidecar is read with it and the overlay layer is recovered
    /// (<see cref="LevelUnbaker"/>). Without that a designer gets 51 flat
    /// tiles and can never take the lamp post off the wall again.
    /// </summary>
    [HttpPost("projects")]
    public ActionResult<ProjectView> Create([FromBody] NewProject request)
    {
        if (!FileProjectStore.IsValidId(request.Id))
            return Problem($"\"{request.Id}\" is not a project id: letters, digits, - and _",
                           statusCode: 400);
        if (store.Load(request.Id) is not null)
            return Problem($"there is already a project called \"{request.Id}\"",
                           statusCode: 409);

        if (request.Width != 0
            && !EngineLimits.IsMapShape(request.Width,
                                        EngineLimits.MapBytes / Math.Max(1, request.Width)))
            return Problem(
                $"{request.Width} is not a width the engine installs: "
                + string.Join(", ", EngineLimits.MapShapes
                                                .Select(s => $"{s.Width}x{s.Height}")),
                statusCode: 400);

        var project = request.Seed == "shipped"
            ? OpenShipped(request)
            : new EditorProject
            {
                Id = request.Id,
                Name = request.Name,
                AssetLevel = request.AssetLevel,
                Sheet = request.Sheet,
                // The package's directory name says which level this is, and
                // the file is named after it. Nothing reads the tileset id
                // yet — MAP_INSTALL parses past it — so it follows.
                // The ENVIRONMENT comes from the art package's own
                // directory name; the LEVEL starts at the first of that
                // environment's block and the designer moves it with a
                // `level-id` op. Both the same number was right while there
                // was one level an environment (CLAUDE.md 8.1).
                TilesetId = EditorProject.LevelIdFor(request.AssetLevel),
                LevelId = (byte)EngineLimits.FirstLevelOf(
                    EditorProject.LevelIdFor(request.AssetLevel)),
                // THE MAP IS 2,048 BYTES WHATEVER ITS SHAPE (CLAUDE.md
                // 8.3), so the width is the only thing a new project has
                // to be told and the height follows from it.
                Width = request.Width == 0 ? EngineLimits.MapWidth : request.Width,
                Map = new byte[EngineLimits.MapBytes],
                TileFlags = new Dictionary<string, TileFlags>(
                    LevelFlagSeeds.For(request.AssetLevel)),
            };

        store.Save(project);
        return ProjectView.Of(project);
    }

    /// <summary>
    /// A batch of edits against the version the client last saw.
    /// <b>A stale version is refused rather than merged</b>: two windows on
    /// one level is the case where losing a stroke is silent, and a level is
    /// source.
    /// </summary>
    [HttpPatch("projects/{id}")]
    public ActionResult<EditResult> Edit(string id, [FromBody] EditBatch batch)
    {
        if (!Find(id, out var project))
            return NotFound(id);
        if (batch.Version != project.Version)
            return Problem(
                $"this project is at version {project.Version} and the edit was made "
                + $"against {batch.Version}; reload before painting over someone else",
                statusCode: 409);

        var outcome = ProjectEditor.Apply(project, batch.Ops);
        if (!outcome.Ok)
            return Problem($"op {outcome.Applied}: {outcome.Rejected}", statusCode: 400);

        project.Version++;
        store.Save(project);
        return new EditResult(project.Version, outcome.Applied);
    }

    [HttpGet("projects/{id}/tileset")]
    public ActionResult<TilesetView> TilesetOf(string id)
    {
        if (!Find(id, out var project))
            return NotFound(id);
        var tileset = assets.TilesetFor(project);

        // Two pens to a byte, high nibble first - the decoded form, so the
        // Mode 0 interleaving stays in one place (see TilesetView).
        var pens = new byte[tileset.Count * (Tile.PixelWidth / 2 * Tile.PixelHeight)];
        var at = 0;
        foreach (var tile in tileset.Tiles)
            for (var y = 0; y < Tile.PixelHeight; y++)
                for (var x = 0; x < Tile.PixelWidth; x += 2)
                    pens[at++] = (byte)((tile.PenAt(x, y) << 4) | tile.PenAt(x + 1, y));

        return new TilesetView(
            project.AssetLevel, project.Sheet, Tile.PixelWidth, Tile.PixelHeight,
            [.. assets.Palette.Select(c => new[] { (int)c.R, c.G, c.B })],
            [.. tileset.Tiles.Select(t => new TileView(t.Name, t.IsOverlay, (byte)t.Flags))],
            Convert.ToBase64String(pens));
    }

    [HttpGet("projects/{id}/validate")]
    public ActionResult<IReadOnlyList<FindingView>> Validate(string id) =>
        Find(id, out var project)
            ? LevelValidator.Check(project, assets.TilesetFor(project))
                .Select(FindingView.Of).ToArray()
            : NotFound(id);

    /// <summary>The three files the engine reads, and the record of the bake.</summary>
    [HttpPost("projects/{id}/export")]
    public ActionResult<ExportView> Export(string id)
    {
        if (!Find(id, out var project))
            return NotFound(id);

        var tileset = assets.TilesetFor(project);
        var findings = LevelValidator.Check(project, tileset);
        if (findings.Any(f => f.Severity == Severity.Error))
            return new ExportView([], [], [.. findings.Select(FindingView.Of)]);

        var result = ProjectExporter.Export(project, tileset);
        // ... into the SIGNED-IN account's own folder, beside its projects.
        var directory = Path.Combine(workspace.Root, project.Id + ".export");
        var files = ProjectExporter.WriteTo(directory, project, result);

        return new ExportView(
            [.. files.Select(f => new ExportedFile(f.Name, f.Bytes.Length,
                                                  Convert.ToBase64String(f.Bytes)))],
            [.. result.Pairs.Select(p =>
                new BakedPairView(p.Index, p.Over, p.Under, p.Name, p.Baked))],
            [.. findings.Select(FindingView.Of)],
            directory);
    }

    private bool Find(string id, out EditorProject project)
    {
        project = null!;
        if (!FileProjectStore.IsValidId(id))
            return false;
        var found = store.Load(id);
        if (found is null)
            return false;
        project = found;
        return true;
    }

    private EditorProject OpenShipped(NewProject request) =>
        ShippedLevel.Open(new ShippedLevel.Request
        {
            Id = request.Id,
            Name = request.Name,
            AssetLevel = request.AssetLevel,
            Sheet = request.Sheet,
            From = options.BuildRoot,
        }, assets);
}
