using System.Text.Json.Serialization;
using CpcLevelEditor.Application;
using CpcLevelEditor.Web;

var builder = WebApplication.CreateBuilder(args);

// WHAT IS NOT HERE, AND WHY. docs/editor.md 6.4 starts with Identity, EF
// Core over SQLite, roles, antiforgery and a rate limiter - the shape of a
// tool several people share over a network. This one runs on the designer's
// own machine against the repository's own files, so there is nobody to
// authenticate and nothing to rate-limit, and a login page on localhost is
// a thing to click through rather than a control. The store is behind
// IProjectStore and the level rules are in the Application layer, so a team
// that needs the rest can add it without moving any of the parts that have
// to be right.
var options = builder.Configuration.GetSection("Editor").Get<EditorOptions>()
    ?? new EditorOptions();
options.WithDefaultsFrom(EditorOptions.FindRepoRoot(AppContext.BaseDirectory));

builder.Services.AddSingleton(options);
builder.Services.AddSingleton<IProjectStore>(_ => new FileProjectStore(options.Workspace));
builder.Services.AddSingleton(_ => new AssetCatalogue(options.SpritesRoot, options.PaletteAsm));
// ENUMS GO OVER THE WIRE BY NAME. A kind that arrives as 4 makes the
// browser keep its own copy of EntityKind, and two copies of an enum is the
// same class of bug as two copies of a bit table (CLAUDE.md 6.3).
builder.Services.AddControllers().AddJsonOptions(o =>
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()));
builder.Services.AddProblemDetails();

var app = builder.Build();

app.UseExceptionHandler();
app.UseStatusCodePages();
app.UseDefaultFiles();
app.UseStaticFiles();
app.MapControllers();

app.Run();

/// <summary>Named so the integration tests can host it.</summary>
public partial class Program;
