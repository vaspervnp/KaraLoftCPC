namespace CpcLevelEditor.Web;

/// <summary>
/// Where the editor's four kinds of file live. Every one of them defaults to
/// somewhere inside this repository, because the editor is part of the
/// game's build pipeline and not a thing you point at a server.
/// </summary>
public sealed class EditorOptions
{
    /// <summary>The art package: <c>assets/sprites</c>.</summary>
    public string SpritesRoot { get; set; } = "";

    /// <summary>The engine's own sixteen pens: <c>src/palette.asm</c>.</summary>
    public string PaletteAsm { get; set; } = "";

    /// <summary>Where projects are kept, one JSON file each.</summary>
    public string Workspace { get; set; } = "";

    /// <summary>
    /// <c>build/</c> — read only, and only to open a level the game already
    /// plays: the shipped <c>.lvl</c> and the bake's sidecar are what
    /// <see cref="Application.LevelUnbaker"/> needs to give a designer back
    /// the overlay layer the format cannot carry.
    /// </summary>
    public string BuildRoot { get; set; } = "";

    /// <summary>
    /// Fills in anything unset from the repository this assembly is running
    /// out of — the directory with CLAUDE.md in it, which is the same way
    /// the test suite finds its golden files.
    /// </summary>
    public EditorOptions WithDefaultsFrom(string repoRoot)
    {
        if (string.IsNullOrEmpty(SpritesRoot))
            SpritesRoot = Path.Combine(repoRoot, "assets", "sprites");
        if (string.IsNullOrEmpty(PaletteAsm))
            PaletteAsm = Path.Combine(repoRoot, "src", "palette.asm");
        if (string.IsNullOrEmpty(Workspace))
            Workspace = Path.Combine(repoRoot, "editor", "workspace");
        if (string.IsNullOrEmpty(BuildRoot))
            BuildRoot = Path.Combine(repoRoot, "build");
        return this;
    }

    /// <summary>Walks up for CLAUDE.md, which is what makes a repository this one.</summary>
    public static string FindRepoRoot(string from)
    {
        var dir = new DirectoryInfo(from);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "CLAUDE.md")))
            dir = dir.Parent;
        return dir?.FullName
            ?? throw new DirectoryNotFoundException("no CLAUDE.md above " + from);
    }
}
