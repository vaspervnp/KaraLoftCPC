using System.Security.Claims;
using System.Text.Encodings.Web;
using CpcLevelEditor.Web.Services;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace CpcLevelEditor.IntegrationTests;

/// <summary>
/// The editor hosted in-process, with a workspace and an account list of its
/// own so a test never paints on a real project or writes down a real
/// address. The art and the golden files are this repository's own — the same
/// rule the unit suite follows, and for the same reason: a copied fixture
/// stops being golden the first time the generator changes and nobody
/// re-copies it.
/// </summary>
/// <remarks>
/// <para>
/// <b>THE EDITOR REFUSES TO START WITH NO WAY IN</b> (<see cref="EditorAuth"/>),
/// so the host is given one — an SMTP setting, through the environment,
/// because that is read while the builder is still being configured. The
/// mailer itself is then replaced with one that keeps the message instead of
/// sending it, which is what lets the suite drive the whole of the email road
/// rather than the two halves either side of an SMTP call.
/// </para>
/// <para>
/// <b>And the sign-in itself is not faked away.</b> The test scheme only
/// authenticates when a request carries <see cref="TestUser.Header"/>;
/// without it, it asks the COOKIE — so a client that has signed in the real
/// way is signed in, and a client that has not is anonymous and meets the
/// same challenge a stranger would.
/// </para>
/// </remarks>
public sealed class EditorApp : WebApplicationFactory<Program>
{
    /// <summary>The account the editor is configured to trust as administrator.</summary>
    public const string Admin = "admin@example.invalid";

    public string Workspace { get; } =
        Directory.CreateTempSubdirectory("cpc-editor-web-").FullName;

    public string Accounts { get; } =
        Directory.CreateTempSubdirectory("cpc-editor-accounts-").FullName;

    /// <summary>The messages the editor "sent", newest last.</summary>
    public CapturedMail Mail { get; } = new();

    public static string RepoRoot { get; } = FindRepoRoot();

    /// <summary>A client that is signed in as <paramref name="email"/>.</summary>
    public HttpClient As(string email)
    {
        var client = CreateClient();
        client.DefaultRequestHeaders.Add(TestUser.Header, email);
        return client;
    }

    /// <summary>... and one that is nobody, which is what a stranger is.</summary>
    public HttpClient Anonymous() => CreateClient(new WebApplicationFactoryClientOptions
    {
        AllowAutoRedirect = false,
    });

    protected override IHost CreateHost(IHostBuilder builder)
    {
        // THROUGH THE ENVIRONMENT and not through ConfigureHostConfiguration:
        // EditorAuth reads these while the WebApplicationBuilder is still
        // being put together, which is before any of the factory's own
        // configuration callbacks run.
        Environment.SetEnvironmentVariable(SmtpMailer.HostVar, "localhost");
        Environment.SetEnvironmentVariable(SmtpMailer.FromVar, "editor@example.invalid");
        Environment.SetEnvironmentVariable(EditorAuth.AdminVar, Admin);
        Environment.SetEnvironmentVariable(AccountStore.DirectoryVar, Accounts);

        builder.UseContentRoot(Path.Combine(RepoRoot, "editor", "src", "CpcLevelEditor.Web"));
        builder.ConfigureHostConfiguration(config => config.AddInMemoryCollection(
            new Dictionary<string, string?> { ["Editor:Workspace"] = Workspace }));
        return base.CreateHost(builder);
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder) =>
        builder.ConfigureTestServices(services =>
        {
            services.AddSingleton<IMailer>(Mail);
            services.AddAuthentication()
                .AddScheme<AuthenticationSchemeOptions, TestUser>(TestUser.Name, _ => { });
            // ONLY the authenticate scheme. The challenge stays the cookie's,
            // so an anonymous page request is still redirected to the sign-in
            // page and an anonymous API call still answers 401 — which is the
            // behaviour worth testing.
            services.Configure<AuthenticationOptions>(
                o => o.DefaultAuthenticateScheme = TestUser.Name);
        });

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (!disposing) return;
        foreach (var directory in new[] { Workspace, Accounts })
            if (Directory.Exists(directory))
                Directory.Delete(directory, recursive: true);
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

/// <summary>A mailer that keeps what it was given.</summary>
public sealed class CapturedMail : IMailer
{
    private readonly List<(string To, string Subject, string Body)> _sent = [];
    private readonly Lock _gate = new();

    public bool IsConfigured => true;

    public string? From => "editor@example.invalid";

    public Task<bool> SendAsync(string to, string subject, string body)
    {
        lock (_gate) _sent.Add((to, subject, body));
        return Task.FromResult(true);
    }

    /// <summary>The last message to an address, or nothing.</summary>
    public string? LastTo(string to)
    {
        lock (_gate)
            return _sent.LastOrDefault(m => m.To == to).Body;
    }

    public int Count
    {
        get { lock (_gate) return _sent.Count; }
    }
}

/// <summary>
/// Signs a request in from a header, and falls back to the cookie when there
/// is none — so both roads are testable and neither is a back door in the
/// editor itself: this handler exists only in the test assembly.
/// </summary>
public sealed class TestUser(
    IOptionsMonitor<AuthenticationSchemeOptions> options, ILoggerFactory logger,
    UrlEncoder encoder) : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    public const string Name = "Test";
    public const string Header = "X-Test-User";

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue(Header, out var header)
            || header.ToString() is not { Length: > 0 } email)
            return Context.AuthenticateAsync(CookieAuthenticationDefaults.AuthenticationScheme);

        var identity = new ClaimsIdentity(
            [new Claim(ClaimTypes.Email, email), new Claim(ClaimTypes.Name, email),
             new Claim(ClaimTypes.NameIdentifier, email)],
            Name);
        return Task.FromResult(AuthenticateResult.Success(
            new AuthenticationTicket(new ClaimsPrincipal(identity), Name)));
    }
}
