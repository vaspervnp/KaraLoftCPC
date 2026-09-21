using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.Google;
using Microsoft.AspNetCore.Authorization;

namespace CpcLevelEditor.Web.Services;

/// <summary>
/// Signing in: a Google account, or a code in an email.
/// </summary>
/// <remarks>
/// <para>
/// <b>THE SECRETS COME FROM THE ENVIRONMENT AND FROM NOWHERE ELSE.</b> Not
/// <c>appsettings.json</c>, not any file in the repository: whatever goes
/// into a file here is committed by accident one day and then lives in the
/// git history for ever.
/// </para>
/// <para>
/// <b>IF NO ROAD IS CONFIGURED THE EDITOR DOES NOT START</b>, and says which
/// variables are missing. Starting open would be worse than not starting at
/// all: you would think it was protected. That is the one rule this is
/// copied from — an editor that writes files onto a disc must not be quietly
/// reachable.
/// </para>
/// <para>
/// <b>BOTH ROADS END IN THE SAME COOKIE.</b> The approval gate, the
/// account's own workspace and the administrator's screen do not know which
/// one anybody took; they read the email claim and nothing else.
/// </para>
/// </remarks>
public static class EditorAuth
{
    public const string IdVar = "karaGid";
    public const string SecretVar = "karaGscrt";
    public const string AdminVar = "karaGadmin";

    /// <summary>The return path, which must match the Google Cloud console.</summary>
    public const string CallbackPath = "/accounts/google";

    public static bool GoogleIsConfigured(IConfiguration config) =>
        !string.IsNullOrWhiteSpace(config[IdVar])
        && !string.IsNullOrWhiteSpace(config[SecretVar]);

    public static bool MailIsConfigured(IConfiguration config) =>
        !string.IsNullOrWhiteSpace(config[SmtpMailer.HostVar])
        && (!string.IsNullOrWhiteSpace(config[SmtpMailer.FromVar])
            || !string.IsNullOrWhiteSpace(config[SmtpMailer.UserVar]));

    public static void Add(WebApplicationBuilder builder)
    {
        var config = builder.Configuration;
        var google = GoogleIsConfigured(config);
        if (!google && !MailIsConfigured(config))
        {
            throw new InvalidOperationException(
                $"""
                 The level editor has no way for anyone to sign in, so it will not start.

                 Set EITHER a Google client — {IdVar} and {SecretVar}, with
                 <your address>{CallbackPath} as the redirect URI in the Google Cloud
                 console — OR an SMTP server for the email codes:
                 {SmtpMailer.HostVar} and {SmtpMailer.FromVar}.

                 {AdminVar} is the administrator's address; it is the only account
                 that is allowed without being approved by somebody else.
                 """);
        }

        var auth = builder.Services
            .AddAuthentication(o =>
            {
                o.DefaultScheme = CookieAuthenticationDefaults.AuthenticationScheme;
                // THE COOKIE, NOT GOOGLE. With Google as the challenge scheme
                // every anonymous request is thrown straight at Google and the
                // sign-in page is never seen — so neither is the email road.
                // The cookie sends them to LoginPath, and the button there
                // calls Google explicitly.
                o.DefaultChallengeScheme = CookieAuthenticationDefaults.AuthenticationScheme;
            })
            .AddCookie(o =>
            {
                o.LoginPath = "/accounts/login";
                o.LogoutPath = "/accounts/logout";
                o.AccessDeniedPath = "/accounts/denied";
                // Painting a level is long work, and a session that expires in
                // the middle of it would lose unsaved strokes.
                o.ExpireTimeSpan = TimeSpan.FromDays(14);
                o.SlidingExpiration = true;
                // THE API ANSWERS 401 AND DOES NOT REDIRECT. A fetch() that
                // follows a 302 to the login page gets HTML with status 200,
                // and the canvas would report "Unexpected token <" instead of
                // "you are signed out".
                o.Events.OnRedirectToLogin = ctx => Status(ctx, 401);
                o.Events.OnRedirectToAccessDenied = ctx => Status(ctx, 403);
            });

        if (google)
        {
            auth.AddGoogle(o =>
            {
                o.ClientId = config[IdVar]!;
                o.ClientSecret = config[SecretVar]!;
                o.CallbackPath = CallbackPath;
                o.SaveTokens = false;       // no Google API is ever called
            });
        }

        // EVERYTHING SHUT BY DEFAULT: an editor that writes files onto a disc
        // must not have an endpoint somebody forgot to protect.
        builder.Services.AddAuthorization(o =>
            o.FallbackPolicy = new AuthorizationPolicyBuilder()
                .RequireAuthenticatedUser()
                .Build());
    }

    private static Task Status(RedirectContext<CookieAuthenticationOptions> ctx, int code)
    {
        if (ctx.Request.Path.StartsWithSegments("/api"))
        {
            ctx.Response.StatusCode = code;
            return Task.CompletedTask;
        }
        ctx.Response.Redirect(ctx.RedirectUri);
        return Task.CompletedTask;
    }
}
