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

        var (flags, paints) = Parse(args[1..]);
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
        foreach (var (x, y, name) in paints)
        {
            var index = IndexOf(artist, name);
            if ((uint)x >= project.Width || (uint)y >= project.Height)
                throw new ArgumentException($"({x},{y}) is off a {project.Width}x{project.Height} map");
            project.Map[(y * project.Width) + x] = (byte)index;
            Console.WriteLine($"   painted ({x},{y}) = {index} {name}");
        }

        var findings = LevelValidator.Check(project, artist);
        foreach (var finding in findings)
            Console.Error.WriteLine($"   {finding.Severity}: {finding.Rule}: {finding.Message}");
        if (findings.Any(f => f.Severity == Severity.Error))
            return 1;

        var result = ProjectExporter.Export(project, artist);
        var outDir = flags.GetValueOrDefault("out")
            ?? throw new ArgumentException("export needs --out DIR");
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

    /// <summary>--flag value pairs, and the repeatable --paint X,Y=NAME.</summary>
    private static (Dictionary<string, string> Flags, List<(int X, int Y, string Tile)> Paints)
        Parse(string[] args)
    {
        Dictionary<string, string> flags = [];
        List<(int, int, string)> paints = [];
        for (var i = 0; i < args.Length; i++)
        {
            if (!args[i].StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException($"unexpected argument \"{args[i]}\"");
            var name = args[i][2..];
            if (i + 1 >= args.Length || args[i + 1].StartsWith("--", StringComparison.Ordinal))
                throw new ArgumentException($"--{name} needs a value");
            var value = args[++i];
            if (name == "paint")
                paints.Add(ParsePaint(value));
            else
                flags[name] = value;
        }
        return (flags, paints);
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
}
