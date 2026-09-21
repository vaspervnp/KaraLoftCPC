using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.Mvc.Testing;

namespace CpcLevelEditor.IntegrationTests;

/// <summary>
/// The way in, over real HTTP.
/// </summary>
/// <remarks>
/// <para>
/// <b>A credential path nothing drives is one nobody has checked</b>, so the
/// email road is walked end to end here — ask for a code, read it out of the
/// message the editor "sent", and sign in — rather than tested either side
/// of an SMTP call. Google's road is not: it is OAuth against somebody
/// else's server, and the part of it that is ours is the same cookie this
/// one ends in.
/// </para>
/// <para>
/// Every test has its negative half beside it: a wrong code does not sign
/// anyone in, a used code does not work twice, an unapproved account gets
/// nowhere, and the administrator's screen is not even there for anybody
/// else.
/// </para>
/// </remarks>
public sealed class AuthTests(EditorApp app) : IClassFixture<EditorApp>
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    [Fact]
    public async Task A_stranger_is_sent_to_the_sign_in_page()
    {
        var response = await app.Anonymous().GetAsync("/");

        Assert.Equal(HttpStatusCode.Found, response.StatusCode);
        Assert.Contains("/accounts/login", response.Headers.Location!.ToString());
    }

    /// <summary>
    /// <b>... and the API answers 401 instead of handing back a page.</b> A
    /// <c>fetch()</c> follows a 302, gets HTML with status 200, and the canvas
    /// reports "Unexpected token &lt;" — which says nothing about being signed
    /// out.
    /// </summary>
    [Fact]
    public async Task And_the_API_says_401_rather_than_sending_a_page()
    {
        var response = await app.Anonymous().GetAsync("/api/vocabulary");

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
        Assert.Null(response.Headers.Location);
    }

    /// <summary>
    /// The page offers the roads that are CONFIGURED. This host has SMTP and
    /// no Google client, so there is an email form and no Google button — the
    /// same page with a Google client would show both.
    /// </summary>
    [Fact]
    public async Task The_sign_in_page_offers_the_roads_that_are_configured()
    {
        var page = await app.Anonymous().GetStringAsync("/accounts/login");

        Assert.Contains("Send me a code", page);
        Assert.DoesNotContain("Sign in with Google", page);
    }

    [Fact]
    public async Task A_code_in_an_email_signs_somebody_in()
    {
        var client = Plain();
        await AskForCode(client, EditorApp.Admin);

        var code = CodeIn(app.Mail.LastTo(EditorApp.Admin));
        var verify = await Post(client, "/accounts/verify",
            new() { ["email"] = EditorApp.Admin, ["code"] = code });

        Assert.Equal(HttpStatusCode.Found, verify.StatusCode);
        Assert.Equal("/", verify.Headers.Location!.ToString());

        var me = await client.GetFromJsonAsync<MeDto>("/accounts/me", Json);
        Assert.True(me!.SignedIn);
        Assert.Equal(EditorApp.Admin, me.Email);
        Assert.True(me.Admin);

        // ... and the cookie is what carries it: the same client now reaches
        // the API, which a moment ago answered 401 to a stranger.
        Assert.Equal(HttpStatusCode.OK,
                     (await client.GetAsync("/api/vocabulary")).StatusCode);
    }

    [Fact]
    public async Task A_wrong_code_signs_nobody_in()
    {
        var client = Plain();
        await AskForCode(client, EditorApp.Admin);
        var right = CodeIn(app.Mail.LastTo(EditorApp.Admin));
        var wrong = right == "000000" ? "111111" : "000000";

        var verify = await Post(client, "/accounts/verify",
            new() { ["email"] = EditorApp.Admin, ["code"] = wrong });

        // Back to the sign-in page, and still nobody.
        Assert.Equal(HttpStatusCode.Found, verify.StatusCode);
        Assert.Contains("/accounts/login", verify.Headers.Location!.ToString());
        Assert.False((await client.GetFromJsonAsync<MeDto>("/accounts/me", Json))!.SignedIn);
    }

    /// <summary>One code, one sign-in: it is spent when it works.</summary>
    [Fact]
    public async Task A_code_works_once()
    {
        var first = Plain();
        await AskForCode(first, EditorApp.Admin);
        var code = CodeIn(app.Mail.LastTo(EditorApp.Admin));
        await Post(first, "/accounts/verify",
            new() { ["email"] = EditorApp.Admin, ["code"] = code });

        var second = Plain();
        await Get(second, "/accounts/login");      // its own antiforgery pair
        var again = await Post(second, "/accounts/verify",
            new() { ["email"] = EditorApp.Admin, ["code"] = code });

        Assert.Contains("/accounts/login", again.Headers.Location!.ToString());
        Assert.False((await second.GetFromJsonAsync<MeDto>("/accounts/me", Json))!.SignedIn);
    }

    /// <summary>
    /// <b>Signing in says who you are, not that you have business here.</b>
    /// An address nobody has approved gets the waiting page, the API refuses
    /// it, and the request is written down so the administrator can see it.
    /// </summary>
    [Fact]
    public async Task Somebody_nobody_approved_waits_and_is_written_down()
    {
        var stranger = "newcomer@example.invalid";
        Assert.Equal(HttpStatusCode.Forbidden,
                     (await app.As(stranger).GetAsync("/api/vocabulary")).StatusCode);

        var page = app.CreateClient(new WebApplicationFactoryClientOptions
        {
            AllowAutoRedirect = false,
        });
        page.DefaultRequestHeaders.Add(TestUser.Header, stranger);
        var home = await page.GetAsync("/");
        Assert.Equal(HttpStatusCode.Found, home.StatusCode);
        Assert.Equal("/accounts/pending", home.Headers.Location!.ToString());

        // ... and the administrator can see the request
        var admin = await app.As(EditorApp.Admin).GetStringAsync("/admin");
        Assert.Contains(stranger, admin);
        Assert.Contains("asked", admin);
    }

    /// <summary>... and once approved, the same account works.</summary>
    [Fact]
    public async Task The_administrator_approves_and_revokes()
    {
        var person = "painter@example.invalid";
        var them = app.As(person);
        Assert.Equal(HttpStatusCode.Forbidden,
                     (await them.GetAsync("/api/vocabulary")).StatusCode);

        var admin = app.As(EditorApp.Admin);
        await Get(admin, "/admin");
        (await Post(admin, "/admin/approve", new() { ["email"] = person }))
            .EnsureSuccessStatusCode();
        Assert.Equal(HttpStatusCode.OK, (await them.GetAsync("/api/vocabulary")).StatusCode);

        (await Post(admin, "/admin/revoke", new() { ["email"] = person }))
            .EnsureSuccessStatusCode();
        Assert.Equal(HttpStatusCode.Forbidden,
                     (await them.GetAsync("/api/vocabulary")).StatusCode);
    }

    /// <summary>
    /// <b>404 and not 403</b>: that the accounts screen exists is nobody
    /// else's business.
    /// </summary>
    [Fact]
    public async Task The_accounts_screen_is_not_there_for_anybody_else()
    {
        var admin = app.As(EditorApp.Admin);
        await Get(admin, "/admin");
        (await Post(admin, "/admin/invite", new() { ["email"] = "guest@example.invalid" }))
            .EnsureSuccessStatusCode();

        var response = await app.As("guest@example.invalid").GetAsync("/admin");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    /// <summary>
    /// <b>Every account paints in a folder of its own.</b> Two of them make a
    /// project under the same name and neither can see the other's: the store
    /// is SCOPED to the signed-in account, and as a singleton the first one in
    /// would have pinned the path for everybody.
    /// </summary>
    [Fact]
    public async Task Two_accounts_do_not_share_a_workspace()
    {
        var admin = app.As(EditorApp.Admin);
        await Get(admin, "/admin");
        foreach (var who in new[] { "one@example.invalid", "two@example.invalid" })
            (await Post(admin, "/admin/invite", new() { ["email"] = who }))
                .EnsureSuccessStatusCode();

        var first = app.As("one@example.invalid");
        var second = app.As("two@example.invalid");
        const string id = "shared-name";

        (await first.PostAsJsonAsync("/api/projects",
            new { id, name = "the first one's" }, Json)).EnsureSuccessStatusCode();
        (await second.PostAsJsonAsync("/api/projects",
            new { id, name = "the second one's" }, Json)).EnsureSuccessStatusCode();

        // Same id, two projects, and each one sees only its own.
        Assert.Equal("the first one's",
            (await first.GetFromJsonAsync<NamedDto>($"/api/projects/{id}", Json))!.Name);
        Assert.Equal("the second one's",
            (await second.GetFromJsonAsync<NamedDto>($"/api/projects/{id}", Json))!.Name);

        var listed = await first.GetFromJsonAsync<List<NamedDto>>("/api/projects", Json);
        Assert.Equal([ "the first one's" ], listed!.Select(p => p.Name));
    }

    /// <summary>A client with no header: the COOKIE is what signs it in.</summary>
    private HttpClient Plain() => app.CreateClient(new WebApplicationFactoryClientOptions
    {
        AllowAutoRedirect = false,
    });

    private static async Task AskForCode(HttpClient client, string email)
    {
        await Get(client, "/accounts/login");
        var asked = await Post(client, "/accounts/code", new() { ["email"] = email });
        Assert.Equal(HttpStatusCode.Found, asked.StatusCode);
    }

    /// <summary>The six digits out of the message the editor "sent".</summary>
    private static string CodeIn(string? body)
    {
        Assert.NotNull(body);
        var match = Regex.Match(body, @"\b(\d{6})\b");
        Assert.True(match.Success, body);
        return match.Groups[1].Value;
    }

    private static readonly Dictionary<HttpClient, string> Tokens = [];

    /// <summary>
    /// A page, keeping its antiforgery token — the forms are real forms and
    /// the editor validates them, so the test has to behave like a browser.
    /// </summary>
    private static async Task<string> Get(HttpClient client, string path)
    {
        var html = await client.GetStringAsync(path);
        var match = Regex.Match(html, "__RequestVerificationToken[^>]*value=\"([^\"]+)\"");
        if (match.Success)
            lock (Tokens) Tokens[client] = match.Groups[1].Value;
        return html;
    }

    private static async Task<HttpResponseMessage> Post(
        HttpClient client, string path, Dictionary<string, string> fields)
    {
        string token;
        lock (Tokens) Tokens.TryGetValue(client, out token!);
        Assert.NotNull(token);
        fields["__RequestVerificationToken"] = token;
        return await client.PostAsync(path, new FormUrlEncodedContent(fields));
    }

    private sealed record MeDto(bool SignedIn, string? Email, bool Approved, bool Admin);
    private sealed record NamedDto(string Id, string Name);
}
