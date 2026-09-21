using System.Text.Json.Serialization;
using CpcLevelEditor.Application;
using CpcLevelEditor.Web.Services;
using Microsoft.AspNetCore.HttpOverrides;

var builder = WebApplication.CreateBuilder(args);

// WHAT IS NOT HERE, AND WHY. docs/editor.md 6.4 also asks for EF Core over
// SQLite and a rate limiter. The store is files behind IProjectStore because
// a level is SOURCE - the build reads it and the repository versions it - and
// the only thing worth rate-limiting, the sign-in codes, limits itself by
// address, by IP and in total (LoginCodes).
//
// THE SIGN-IN IS HERE NOW, AND IT USED TO SAY IT NEVER WOULD BE. The argument
// was that the editor runs on the designer's own machine, where a login page
// on localhost is a thing to click through rather than a control. That holds
// exactly as long as it IS on the designer's own machine; the moment it is
// reachable from anywhere else, an editor that writes files onto a disc with
// no account behind it is the whole of the problem. See EditorAuth.
var options = builder.Configuration.GetSection("Editor").Get<EditorOptions>()
    ?? new EditorOptions();
options.WithDefaultsFrom(EditorOptions.FindRepoRoot(AppContext.BaseDirectory));

builder.Services.AddSingleton(options);
builder.Services.AddHttpContextAccessor();
builder.Services.AddSingleton(_ => new AssetCatalogue(options.SpritesRoot, options.PaletteAsm));
// Who may use the editor, and the two roads in.
builder.Services.AddSingleton(AccountStore.From(builder.Configuration, builder.Environment));
builder.Services.AddSingleton<LoginCodes>();
builder.Services.AddSingleton<IMailer, SmtpMailer>();
// SCOPED, both of them, because their root is the SIGNED-IN account's folder.
// As singletons the first account to sign in would pin the path and everybody
// afterwards would paint on that one's levels.
builder.Services.AddScoped<UserWorkspace>();
builder.Services.AddScoped<IProjectStore>(
    services => new FileProjectStore(services.GetRequiredService<UserWorkspace>().Root));

// ENUMS GO OVER THE WIRE BY NAME. A kind that arrives as 4 makes the
// browser keep its own copy of EntityKind, and two copies of an enum is the
// same class of bug as two copies of a bit table (CLAUDE.md 6.3).
builder.Services.AddControllersWithViews().AddJsonOptions(o =>
    o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()));
builder.Services.AddProblemDetails();

// BEHIND A REVERSE PROXY the proxy ends the HTTPS and speaks plain HTTP to
// the editor. Without this Kestrel sees "http://localhost:5099" and builds
// the WRONG redirect_uri for Google - http instead of https, the wrong host -
// so the sign-in fails with redirect_uri_mismatch. It reaches the cookie too,
// which would otherwise go out without its Secure flag.
builder.Services.Configure<ForwardedHeadersOptions>(o =>
{
    o.ForwardedHeaders = ForwardedHeaders.XForwardedFor
                       | ForwardedHeaders.XForwardedProto
                       | ForwardedHeaders.XForwardedHost;
    // "Trust X-Forwarded-* from anybody", which stands ONLY because the
    // editor is not reachable except through the proxy. If it ever listens on
    // a public address these two have to come back, or anyone can claim any
    // scheme and any IP.
    o.KnownIPNetworks.Clear();
    o.KnownProxies.Clear();
});

EditorAuth.Add(builder);

var app = builder.Build();

// FIRST of all: it fixes the request's scheme and host before anything else
// reads them. Configure<ForwardedHeadersOptions> on its own does nothing.
app.UseForwardedHeaders();
app.UseExceptionHandler();
app.UseStatusCodePages();
// wwwroot is the script, the stylesheet and nothing else. It is served BEFORE
// authorization, so whatever is in it is public - which is why the painter's
// own page is a view and not index.html (HomeController).
app.UseStaticFiles();
app.UseRouting();
app.UseAuthentication();
app.UseAuthorization();
// AFTER the authorization: by now we know who it is, and we can turn away the
// ones nobody has approved yet while SHOWING THEM WHY.
app.UseMiddleware<ApprovalGate>();

app.MapControllers();
app.MapControllerRoute("default", "{controller=Home}/{action=Index}/{id?}");

app.Run();

/// <summary>Named so the integration tests can host it.</summary>
public partial class Program;
