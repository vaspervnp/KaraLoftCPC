using System.Security.Claims;

namespace CpcLevelEditor.Web.Services;

/// <summary>
/// Stops the signed-in who have not been approved yet.
/// </summary>
/// <remarks>
/// <para>
/// <b>Middleware and not an authorization policy</b>, because the refusal is
/// not "you may not" but "wait": it wants a page of its own with the reason
/// on it, and it wants to WRITE THE ADDRESS DOWN so the administrator sees
/// that somebody asked. A bare 403 leaves the person looking at a blank page
/// and the administrator not knowing anyone came.
/// </para>
/// <para>
/// It runs AFTER <c>UseAuthorization</c>, so who it is talking to is already
/// settled.
/// </para>
/// </remarks>
public sealed class ApprovalGate(RequestDelegate next)
{
    /// <summary>
    /// What has to work for somebody who is not approved: seeing why they are
    /// waiting, and being able to sign out and try another address.
    /// </summary>
    private static readonly string[] Open =
    [
        "/accounts/login", "/accounts/logout", "/accounts/pending", "/accounts/me",
        "/accounts/denied", "/accounts/google", "/accounts/google-login",
        "/accounts/code", "/accounts/verify",
    ];

    public async Task Invoke(HttpContext context, AccountStore accounts)
    {
        var path = context.Request.Path;
        if (context.User.Identity?.IsAuthenticated != true
            || Open.Any(open => path.StartsWithSegments(open)))
        {
            await next(context);
            return;
        }

        var email = context.User.FindFirstValue(ClaimTypes.Email);
        if (accounts.IsAllowed(email))
        {
            await next(context);
            return;
        }

        accounts.RecordPending(email);
        // The API says so in a status rather than handing a fetch() a page.
        if (path.StartsWithSegments("/api"))
        {
            context.Response.StatusCode = 403;
            return;
        }
        context.Response.Redirect("/accounts/pending");
    }
}
