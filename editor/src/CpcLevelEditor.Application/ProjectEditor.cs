using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Application;

/// <summary>
/// One edit. A client sends a batch of them with the version it made them
/// against.
/// </summary>
/// <param name="Op">
/// <c>tile</c>, <c>overlay</c>, <c>overlay-clear</c>, <c>flags</c>,
/// <c>name</c>, <c>entity-add</c>, <c>entity-set</c>, <c>entity-remove</c>,
/// <c>region-add</c>, <c>region-set</c>, <c>region-remove</c>.
/// </param>
/// <param name="X">A map cell for the tile ops, and unused by the rest —
/// an entity carries world pixels and a region tiles, inside the record.</param>
/// <param name="Index">
/// Which record an <c>-set</c> or <c>-remove</c> means, <b>as the batch has
/// the list at that point</b>. The ops are applied in order and a client
/// mutating its own copy in the same order sees the same indices, which is
/// what lets a remove and a later edit travel together.
/// </param>
public sealed record EditOp(
    string Op,
    int X = 0,
    int Y = 0,
    byte Tile = 0,
    string? Name = null,
    byte Flags = 0,
    int Index = 0,
    Domain.Entity? Entity = null,
    Domain.Region? Region = null);

/// <summary>How far a batch got, and why it stopped.</summary>
public readonly record struct EditOutcome(int Applied, string? Rejected)
{
    public bool Ok => Rejected is null;
}

/// <summary>
/// The edits themselves, away from HTTP.
/// </summary>
/// <remarks>
/// <para>
/// What an op may do is a property of the LEVEL and not of the transport:
/// an entity past <c>ENT_MAX</c>, a region off the map and a cell off the
/// map are all things the engine would be given and could not use. They are
/// refused here so the canvas hears about it on the stroke rather than at
/// export.
/// </para>
/// <para>
/// <b>A rejected batch leaves the project half-edited and that is safe
/// because it is never saved.</b> The store reads from disk on every load,
/// so the object a rejected batch mutated is thrown away with the request;
/// what a client must do is reload, which is the same thing a stale version
/// asks of it.
/// </para>
/// </remarks>
public static class ProjectEditor
{
    public static EditOutcome Apply(EditorProject project, IReadOnlyList<EditOp> ops)
    {
        var applied = 0;
        foreach (var op in ops)
        {
            if (ApplyOne(project, op) is { } rejected)
                return new EditOutcome(applied, rejected);
            applied++;
        }
        return new EditOutcome(applied, null);
    }

    private static string? ApplyOne(EditorProject project, EditOp op)
    {
        switch (op.Op)
        {
            case "tile":
                if (!InsideMap(project, op.X, op.Y))
                    return Off(project, op.X, op.Y);
                project.Map[(op.Y * project.Width) + op.X] = op.Tile;
                return null;

            case "overlay":
                if (!InsideMap(project, op.X, op.Y))
                    return Off(project, op.X, op.Y);
                project.Overlays.Add(new OverlayPlacement(op.X, op.Y, op.Tile));
                return null;

            case "overlay-clear":
                project.Overlays.RemoveAll(o => o.X == op.X && o.Y == op.Y);
                return null;

            case "flags":
                if (op.Name is null)
                    return "a flags op needs a tile name";
                project.TileFlags[op.Name] = (TileFlags)op.Flags;
                return null;

            case "name":
                project.Name = op.Name ?? project.Name;
                return null;

            // WHICH LEVEL THIS IS, as against which ENVIRONMENT it is in.
            // The environment is the art package the project was started on
            // and never changes; the number is the designer's, and it is what
            // DISC_LEVEL_MAPS is indexed by, so two projects sharing one
            // would put two maps at one disc entry and the build would keep
            // whichever it wrote last.
            case "level-id":
                if (op.Index < 1 || op.Index > EngineLimits.MaxLevels)
                    return $"level {op.Index} is outside 1..{EngineLimits.MaxLevels}";
                if (EngineLimits.EnvironmentOf(op.Index) != project.TilesetId)
                    return $"level {op.Index} belongs to environment "
                         + $"{EngineLimits.EnvironmentOf(op.Index)} and this "
                         + $"project is environment {project.TilesetId}: the "
                         + $"numbering is blocks of "
                         + $"{EngineLimits.LevelsPerEnvironment}";
                project.LevelId = (byte)op.Index;
                return null;

            // AND WHAT SHAPE THE MAP IS. It is stored as the WIDTH alone
            // and the height follows, because the map is 2,048 bytes of
            // base RAM whatever its shape (CLAUDE.md 8.3) - so a shape
            // cannot be half-changed.
            //
            // THE CELLS KEEP THEIR ORDER AND THE GRID IS RE-CUT, which is
            // the honest thing for it to do and is worth saying out loud:
            // the same 2,048 bytes in a 32-wide grid are a different
            // picture, not a scaled one. What it will NOT do is leave a
            // record off the map, because a record off the map is a thing
            // the engine reads, quietly does nothing with, and carries on
            // (CLAUDE.md 11 step 7) - so it is refused on the stroke and
            // the designer moves the record first.
            case "shape":
                if (!EngineLimits.IsMapShape(op.Index,
                                             EngineLimits.MapBytes / Math.Max(1, op.Index)))
                    return $"{op.Index} is not a width the engine installs: "
                         + string.Join(", ", EngineLimits.MapShapes
                                                         .Select(s => $"{s.Width}x{s.Height}"));
                var was = project.Width;
                project.Width = op.Index;
                if (project.Entities.Select(e => OutsideWorld(project, e))
                                    .FirstOrDefault(w => w is not null) is { } lost)
                {
                    project.Width = was;
                    return $"{op.Index}x{EngineLimits.MapBytes / op.Index} would "
                         + $"leave a record off the map: {lost}";
                }
                if (project.Regions.Select(r => OutsideMap(project, r))
                                   .FirstOrDefault(w => w is not null) is { } gone)
                {
                    project.Width = was;
                    return $"{op.Index}x{EngineLimits.MapBytes / op.Index} would "
                         + $"leave a region off the map: {gone}";
                }
                return null;

            case "entity-add":
                if (op.Entity is not { } added)
                    return "an entity-add op needs an entity";
                if (project.Entities.Count >= EngineLimits.MaxEntities)
                    return $"the table holds ENT_MAX = {EngineLimits.MaxEntities} records and "
                         + "the engine clears exactly that many";
                if (OutsideWorld(project, added) is { } why)
                    return why;
                project.Entities.Add(added);
                return null;

            case "entity-set":
                if (op.Entity is not { } set)
                    return "an entity-set op needs an entity";
                if (!Holds(project.Entities.Count, op.Index))
                    return Missing("entity", op.Index, project.Entities.Count);
                if (OutsideWorld(project, set) is { } wrong)
                    return wrong;
                project.Entities[op.Index] = set;
                return null;

            case "entity-remove":
                if (!Holds(project.Entities.Count, op.Index))
                    return Missing("entity", op.Index, project.Entities.Count);
                project.Entities.RemoveAt(op.Index);
                return null;

            case "region-add":
                if (op.Region is not { } region)
                    return "a region-add op needs a region";
                if (OutsideMap(project, region) is { } bad)
                    return bad;
                project.Regions.Add(region);
                return null;

            case "region-set":
                if (op.Region is not { } moved)
                    return "a region-set op needs a region";
                if (!Holds(project.Regions.Count, op.Index))
                    return Missing("region", op.Index, project.Regions.Count);
                if (OutsideMap(project, moved) is { } outside)
                    return outside;
                project.Regions[op.Index] = moved;
                return null;

            case "region-remove":
                if (!Holds(project.Regions.Count, op.Index))
                    return Missing("region", op.Index, project.Regions.Count);
                project.Regions.RemoveAt(op.Index);
                return null;

            default:
                return $"there is no \"{op.Op}\" edit";
        }
    }

    private static bool InsideMap(EditorProject p, int x, int y) =>
        (uint)x < p.Width && (uint)y < p.Height;

    private static bool Holds(int count, int index) => (uint)index < count;

    private static string Off(EditorProject p, int x, int y) =>
        $"({x},{y}) is off a {p.Width}x{p.Height} map";

    private static string Missing(string what, int index, int count) =>
        $"there is no {what} {index}: the level has {count}";

    /// <summary>
    /// X is a world pixel and Y is the BASE of the hitbox, so a thing
    /// standing on the floor below the last row is at exactly the world's
    /// height and is in (<see cref="Entity"/>).
    /// </summary>
    private static string? OutsideWorld(EditorProject p, Entity e) =>
        e.X >= p.Width * Entity.TileWidth || e.Y > p.Height * Entity.TileHeight
            ? $"an entity at ({e.X},{e.Y}) is outside a world of "
              + $"{p.Width * Entity.TileWidth}x{p.Height * Entity.TileHeight} pixels"
            : null;

    /// <summary>... and a region is in TILES, which is what its byte-wide
    /// width and height are for (<see cref="Region"/>).</summary>
    private static string? OutsideMap(EditorProject p, Region r) =>
        r.Width == 0 || r.Height == 0
            ? "a region with no width or no height covers nothing"
            : r.X + r.Width > p.Width || r.Y + r.Height > p.Height
                ? $"a {r.Width}x{r.Height} region at ({r.X},{r.Y}) runs off a "
                  + $"{p.Width}x{p.Height} map"
                : null;
}
