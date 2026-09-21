using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;

namespace CpcLevelEditor.IntegrationTests;

/// <summary>
/// The editor hosted in-process, with a workspace of its own so a test
/// never paints on a real project. The art and the golden files are this
/// repository's own — the same rule the unit suite follows, and for the same
/// reason: a copied fixture stops being golden the first time the generator
/// changes and nobody re-copies it.
/// </summary>
public sealed class EditorApp : WebApplicationFactory<Program>
{
    public string Workspace { get; } =
        Directory.CreateTempSubdirectory("cpc-editor-web-").FullName;

    public static string RepoRoot { get; } = FindRepoRoot();

    protected override IHost CreateHost(IHostBuilder builder)
    {
        builder.UseContentRoot(Path.Combine(RepoRoot, "editor", "src", "CpcLevelEditor.Web"));
        builder.ConfigureHostConfiguration(config => config.AddInMemoryCollection(
            new Dictionary<string, string?> { ["Editor:Workspace"] = Workspace }));
        return base.CreateHost(builder);
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (disposing && Directory.Exists(Workspace))
            Directory.Delete(Workspace, recursive: true);
    }

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "CLAUDE.md")))
            dir = dir.Parent;
        return dir?.FullName
            ?? throw new DirectoryNotFoundException("no CLAUDE.md above " + AppContext.BaseDirectory);
    }
}
