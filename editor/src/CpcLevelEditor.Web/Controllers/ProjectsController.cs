using CpcLevelEditor.Application;
using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;
using Microsoft.AspNetCore.Mvc;

namespace CpcLevelEditor.Web.Controllers;

[ApiController]
[Route("api")]
public sealed class ProjectsController(
    IProjectStore store, AssetCatalogue assets, EditorOptions options) : ControllerBase
{
    /// <summary>The art the editor can paint out of.</summary>
    [HttpGet("assets")]
    public IReadOnlyList<LevelAssets> Assets() =>
        [.. assets.Levels().Select(level => new LevelAssets(level, assets.Sheets(level)))];

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

        var project = request.Seed == "shipped"
            ? OpenShipped(request)
            : new EditorProject
            {
                Id = request.Id,
                Name = request.Name,
                AssetLevel = request.AssetLevel,
                Sheet = request.Sheet,
                Map = new byte[EngineLimits.MapWidth * EngineLimits.MapHeight],
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

        var applied = 0;
        foreach (var op in batch.Ops)
        {
            switch (op.Op)
            {
                case "tile":
                    if (!InsideMap(project, op.X, op.Y))
                        return Problem($"({op.X},{op.Y}) is off the map", statusCode: 400);
                    project.Map[op.Y * project.Width + op.X] = op.Tile;
                    break;
                case "overlay":
                    if (!InsideMap(project, op.X, op.Y))
                        return Problem($"({op.X},{op.Y}) is off the map", statusCode: 400);
                    project.Overlays.Add(new OverlayPlacement(op.X, op.Y, op.Tile));
                    break;
                case "overlay-clear":
                    project.Overlays.RemoveAll(o => o.X == op.X && o.Y == op.Y);
                    break;
                case "flags":
                    if (op.Name is null)
                        return Problem("a flags op needs a tile name", statusCode: 400);
                    project.TileFlags[op.Name] = (TileFlags)op.Flags;
                    break;
                case "name":
                    project.Name = op.Name ?? project.Name;
                    break;
                default:
                    return Problem($"there is no \"{op.Op}\" edit", statusCode: 400);
            }
            applied++;
        }

        project.Version++;
        store.Save(project);
        return new EditResult(project.Version, applied);
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
        var directory = Path.Combine(options.Workspace, project.Id + ".export");
        var files = ProjectExporter.WriteTo(directory, project, result);

        return new ExportView(
            [.. files.Select(f => new ExportedFile(f.Name, f.Bytes.Length,
                                                  Convert.ToBase64String(f.Bytes)))],
            [.. result.Pairs.Select(p =>
                new BakedPairView(p.Index, p.Over, p.Under, p.Name, p.Baked))],
            [.. findings.Select(FindingView.Of)],
            directory);
    }

    private static bool InsideMap(EditorProject p, int x, int y) =>
        (uint)x < p.Width && (uint)y < p.Height;

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
