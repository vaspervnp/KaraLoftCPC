using CpcLevelEditor.Application;
using CpcLevelEditor.Assets;
using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Cli;

/// <summary>
/// The editor's export, without the browser.
/// </summary>
/// <remarks>
/// <para>
/// The painter is where a level is made; this is how what it made reaches
/// the build. Everything here goes through the same Application layer the
/// web app does — <see cref="ShippedLevel"/> to open,
/// <see cref="ProjectExporter"/> to write — so there is no second opinion
/// about what a level is or what its files are called.
/// </para>
/// <para>
/// It exists because the one witness this project trusts is the hardware
/// (CLAUDE.md 5), and a suite that has to drive a browser to get a level
/// onto the emulator is a suite nobody runs.
/// </para>
/// </remarks>
public static class Program
{
    private const string Usage = """
        cpclevel export --out DIR [--project ID | --from-shipped DIR]

          --out DIR          where the four files go
          --project ID       a project from the workspace
          --from-shipped DIR open the level in DIR - its .lvl and its bake
                             record - the way the editor opens build/'s City
          --paint X,Y=TILE   set one map cell to a named tile before
                             exporting; repeatable. The overlay layer is left
                             alone, exactly as the painter's brush leaves it
          --entity KIND,COLUMN,ROW[,P0[,P1]]
                             place one entity, in TILES - the row is the one
                             whose top surface it stands on. Repeatable
          --region KIND,X,Y,W,H
                             place one region, in tiles. Repeatable
          --width N          re-cut the map to N tiles across (32, 64 or
                             128) before anything else
          --generate         fill the map and the records in with a level
                             that can be played, over whatever was there
          --workspace DIR    default: editor/workspace
          --sprites DIR      default: assets/sprites
          --palette FILE     default: src/palette.asm
          --level NAME       art package, default level1_city
          --sheet NAME       tile sheet, default city_tiles
        """;

    public static int Main(string[] args)
    {
        try
        {
            return Run(args);
        }
        catch (Exception e) when (e is IOException or InvalidDataException
                                    or ArgumentException or KeyNotFoundException)
        {
            Console.Error.WriteLine("cpclevel: " + e.Message);
            return 1;
        }
    }

    private static int Run(string[] args)
    {
        if (args.Length == 0 || args[0] is "-h" or "--help" or "help")
        {
            Console.WriteLine(Usage);
            return args.Length == 0 ? 2 : 0;
        }
        if (args[0] != "export")
        {
            Console.Error.WriteLine($"cpclevel: there is no \"{args[0]}\" command\n\n{Usage}");
            return 2;
        }

        var (flags, repeated) = Parse(args[1..]);
        var outDir = flags.GetValueOrDefault("out")
            ?? throw new ArgumentException("export needs --out DIR");
        var options = new EditorOptions
        {
            SpritesRoot = flags.GetValueOrDefault("sprites", ""),
            PaletteAsm = flags.GetValueOrDefault("palette", ""),
            Workspace = flags.GetValueOrDefault("workspace", ""),
        }.WithDefaultsFrom(EditorOptions.FindRepoRoot(AppContext.BaseDirectory));

        var assets = new AssetCatalogue(options.SpritesRoot, options.PaletteAsm);
        var project = Open(flags, options, assets);

        // The artist's own tileset, so a tile can be named rather than
        // numbered: an index is a frame order and a name is the thing. It
        // comes off the PROJECT and not off the flags - a stored project
        // knows which package it was painted out of.
        var artist = assets.Tileset(project.AssetLevel, project.Sheet, project.TileFlags);

        // EVERY CHANGE GOES THROUGH ProjectEditor, which is the same code the
        // canvas's PATCH goes through - so a level made here and a level
        // painted in the browser cannot be made in two different ways.
        var ops = new List<EditOp>();
        if (flags.TryGetValue("width", out var width))
            ops.Add(new EditOp("shape", Index: int.Parse(width)));
        foreach (var (x, y, name) in repeated.Paints)
            ops.Add(new EditOp("tile", x, y, (byte)IndexOf(artist, name)));
        foreach (var entity in repeated.Entities)
            ops.Add(new EditOp("entity-add", Entity: entity));
        foreach (var region in repeated.Regions)
            ops.Add(new EditOp("region-add", Region: region));

        // THE SHAPE FIRST, THEN THE PLAN, THEN THE STROKES. Generating
        // over a width that is about to change would lay the floors out on
        // the wrong grid, and a --paint is the designer's word over the
        // generator's - so the order here is the order a person would do
        // it in.
        //
        // AND A GENERATE EMPTIES THE RECORDS BEFORE THE SHAPE IS CUT,
        // because it is going to replace them anyway: the shape op refuses
        // a re-cut that would leave a record off the map (which is right -
        // the engine reads it, does nothing and carries on), and the City's
        // own records are all off a 32-wide one.
        if (flags.ContainsKey("generate"))
        {
            project.Entities.Clear();
            project.Regions.Clear();
            project.Overlays.Clear();
        }
        var shapeFirst = ops.Where(o => o.Op == "shape").ToList();
        if (shapeFirst.Count > 0)
        {
            var cut = ProjectEditor.Apply(project, shapeFirst);
            if (!cut.Ok)
                throw new ArgumentException(cut.Rejected);
            ops.RemoveAll(o => o.Op == "shape");
        }
        if (flags.ContainsKey("generate"))
        {
            var (made, refused) = LevelGenerator.Fill(project, artist);
            if (made is not { } plan)
                throw new ArgumentException(refused);
            Console.WriteLine(
                $"   generated {project.Width}x{project.Height}: {plan.Floors} floor(s), "
                + $"{plan.Ladders} ladder(s), {plan.Holes} hole(s), {plan.Pickups} "
                + $"pickup(s), {plan.Enemies} enem(ies), one door - floor "
                + $"{plan.FloorTile}, ladder {plan.LadderTile}, sky {plan.BackgroundTile}");
        }

        var outcome = ProjectEditor.Apply(project, ops);
        if (!outcome.Ok)
            throw new ArgumentException($"op {outcome.Applied}: {outcome.Rejected}");
        if (ops.Count > 0)
            Console.WriteLine($"   {repeated.Paints.Count} cell(s) painted, "
                + $"{repeated.Entities.Count} entity(s) and "
                + $"{repeated.Regions.Count} region(s) placed");

        var findings = LevelValidator.Check(project, artist);
        foreach (var finding in findings)
            Console.Error.WriteLine($"   {finding.Severity}: {finding.Rule}: {finding.Message}");
        if (findings.Any(f => f.Severity == Severity.Error))
            return 1;

        var result = ProjectExporter.Export(project, artist);
        foreach (var file in ProjectExporter.WriteTo(outDir, project, result))
            Console.WriteLine($"-> {file.Name}  {file.Bytes.Length} bytes");
        Console.WriteLine(
            $"   {result.Pairs.Count(p => p.Baked)} overlay pair(s) baked of "
            + $"{result.Pairs.Count} placed, {result.BakedTileset.Count} tiles in the blob");
        return 0;
    }

    private static EditorProject Open(
        IReadOnlyDictionary<string, string> flags, EditorOptions options,
        AssetCatalogue assets)
    {
        if (flags.TryGetValue("project", out var id))
            return new FileProjectStore(options.Workspace).Load(id)
                ?? throw new KeyNotFoundException(
                    $"no project \"{id}\" in {options.Workspace}");

        return ShippedLevel.Open(new ShippedLevel.Request
        {
            Id = "cli",
            Name = "exported by cpclevel",
            AssetLevel = flags.GetValueOrDefault("level", "level1_city"),
            Sheet = flags.GetValueOrDefault("sheet", "city_tiles"),
            From = flags.GetValueOrDefault("from-shipped", options.BuildRoot),
        }, assets);
    }

    private static int IndexOf(Tileset tiles, string name)
    {
        for (var i = 0; i < tiles.Count; i++)
            if (tiles.Tiles[i].Name == name)
                return i;
        throw new KeyNotFoundException($"no tile called \"{name}\" in the sheet");
    }

    /// <summary>The three repeatable placements.</summary>
    private sealed record Placements(
        List<(int X, int Y, string Tile)> Paints,
        List<Entity> Entities,
        List<Region> Regions);

    /// <summary>The flags that carry no value.</summary>
    private static readonly HashSet<string> Switches = ["generate"];

    /// <summary>--flag value pairs, and the repeatable placements.</summary>
    private static (Dictionary<string, string> Flags, Placements Repeated) Parse(string[] args)
    {
        Dictionary<string, string> flags = [];
        Placements repeated = new([], [], []);
        for (var i = 0; i < args.Length; i++)
        {
            if (!args[i].StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException($"unexpected argument \"{args[i]}\"");
            var name = args[i][2..];
            // A SWITCH IS NAMED, and everything else needs a value. Reading
            // "a flag with nothing after it" as a switch would make
            // `--out` at the end of a line mean something instead of being
            // the mistake it is.
            if (Switches.Contains(name)) { flags[name] = "yes"; continue; }
            if (i + 1 >= args.Length || args[i + 1].StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException($"--{name} needs a value");
            var value = args[++i];
            switch (name)
            {
                case "paint": repeated.Paints.Add(ParsePaint(value)); break;
                case "entity": repeated.Entities.Add(ParseEntity(value)); break;
                case "region": repeated.Regions.Add(ParseRegion(value)); break;
                default: flags[name] = value; break;
            }
        }
        return (flags, repeated);
    }

    private static (int, int, string) ParsePaint(string value)
    {
        var equals = value.IndexOf('=');
        var comma = value.IndexOf(',');
        if (equals < 0 || comma < 0 || comma > equals)
            throw new ArgumentException($"--paint wants X,Y=TILE and got \"{value}\"");
        return (int.Parse(value[..comma]),
                int.Parse(value[(comma + 1)..equals]),
                value[(equals + 1)..]);
    }

    /// <summary>
    /// <c>KIND,COLUMN,ROW[,P0[,P1]]</c> — in TILES, with the row being the
    /// one whose top surface it stands on, which is the conversion
    /// <see cref="Entity.AtTile"/> does.
    /// </summary>
    private static Entity ParseEntity(string value)
    {
        var parts = Fields(value, "--entity", "KIND,COLUMN,ROW[,P0[,P1]]", 3, 5);
        var kind = Enum.Parse<EntityKind>(parts[0], ignoreCase: true);
        return Entity.AtTile(kind, int.Parse(parts[1]), int.Parse(parts[2]),
                             Entity.DefaultFlagsFor(kind),
                             parts.Length > 3 ? byte.Parse(parts[3]) : (byte)0,
                             parts.Length > 4 ? byte.Parse(parts[4]) : (byte)0);
    }

    /// <summary><c>KIND,X,Y,W,H</c> — in tiles, which is a region's unit.</summary>
    private static Region ParseRegion(string value)
    {
        var parts = Fields(value, "--region", "KIND,X,Y,W,H", 5, 5);
        return new Region(Enum.Parse<RegionKind>(parts[0], ignoreCase: true),
                          ushort.Parse(parts[1]), ushort.Parse(parts[2]),
                          byte.Parse(parts[3]), byte.Parse(parts[4]));
    }

    private static string[] Fields(string value, string flag, string shape, int least, int most)
    {
        var parts = value.Split(',');
        return parts.Length >= least && parts.Length <= most
            ? parts
            : throw new ArgumentException($"{flag} wants {shape} and got \"{value}\"");
    }
}
