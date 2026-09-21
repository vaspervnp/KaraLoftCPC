using System.Security.Claims;
using CpcLevelEditor.Web.Services;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authentication.Google;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace CpcLevelEditor.Web.Controllers;

/// <summary>
/// Signing in and out: with a Google account, or with a code in an email.
/// </summary>
/// <remarks>
/// <para>
/// The return path <c>/accounts/google</c> has NO action here: Google's own
/// middleware handles it (its <c>CallbackPath</c>) before routing is reached.
/// It is declared in <see cref="EditorAuth"/> and has to match what is
/// written in the Google Cloud console.
/// </para>
/// <para>
/// <b>BOTH ROADS END IN THE SAME COOKIE</b>, with the same claims. Past this
/// controller nothing in the editor can tell which one anybody took.
/// </para>
/// </remarks>
[AllowAnonymous]
[Route("accounts")]
public sealed class AccountsController(
    AccountStore accounts, LoginCodes codes, IMailer mail, IConfiguration config,
    ILogger<AccountsController> log) : Controller
{
    /// <summary>
    /// The sign-in page: a Google button, and an email form if SMTP is set.
    /// Every anonymous request that is not an API call ends up here.
    /// </summary>
    [HttpGet("login")]
    public IActionResult Login(string? returnUrl = null, string? email = null)
    {
        ViewData["ReturnUrl"] = Local(returnUrl);
        ViewData["Google"] = EditorAuth.GoogleIsConfigured(config);
        ViewData["Mail"] = mail.IsConfigured;
        ViewData["Email"] = email ?? "";
        // A code already in flight for this address: show the code box
        // straight away, because they have come back from their mailbox.
        ViewData["Stage"] = email is not null && codes.Pending(email) ? "code" : "start";
        return View();
    }

    /// <summary>Starts the Google road; comes back where it was asked from.</summary>
    [HttpGet("google-login")]
    public IActionResult GoogleLogin(string? returnUrl = null) =>
        EditorAuth.GoogleIsConfigured(config)
            ? Challenge(new AuthenticationProperties { RedirectUri = Local(returnUrl) },
                        GoogleDefaults.AuthenticationScheme)
            : Back(returnUrl, "", "start", "Signing in with Google is not set up here.");

    /// <summary>Sends a six-digit code to the address.</summary>
    [HttpPost("code")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> SendCode(string email, string? returnUrl = null)
    {
        var to = AccountStore.Normalise(email);
        if (!mail.IsConfigured)
            return Back(returnUrl, to, "start", "Signing in by email is not available.");
        if (!AccountStore.LooksLikeEmail(to))
            return Back(returnUrl, to, "start", "That does not look like an email address.");

        var ip = HttpContext.Connection.RemoteIpAddress?.ToString() ?? "?";
        var (result, code) = codes.Issue(to, ip);

        if (result == CodeRequest.TooMany)
            return Back(returnUrl, to, "start", "Too many codes requested. Try again later.");

        if (result == CodeRequest.Sent
            && !await mail.SendAsync(to, "Your Kara Loft editor sign-in code",
                $"""
                 Your sign-in code is:

                     {code}

                 It lasts {LoginCodes.Lifetime.TotalMinutes:0} minutes and works once. If
                 you did not ask for it, ignore this message — nobody can sign in
                 without it.
                 """))
        {
            return Back(returnUrl, to, "start",
                "The code could not be sent. Tell the administrator to check the mail settings.");
        }

        // THE SAME ANSWER whether one was just sent or one was already in
        // flight: the difference would tell a stranger that the address is
        // waiting to sign in.
        return Back(returnUrl, to, "code",
            $"If {to} can sign in, a code is on its way. It lasts "
            + $"{LoginCodes.Lifetime.TotalMinutes:0} minutes.");
    }

    /// <summary>Checks the code and signs in.</summary>
    [HttpPost("verify")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> Verify(string email, string code, string? returnUrl = null)
    {
        var to = AccountStore.Normalise(email);
        if (!codes.Verify(to, code))
            return Back(returnUrl, to, "code", "Wrong or expired code.");

        var identity = new ClaimsIdentity(
            [new Claim(ClaimTypes.Email, to), new Claim(ClaimTypes.Name, to),
             new Claim(ClaimTypes.NameIdentifier, to)],
            CookieAuthenticationDefaults.AuthenticationScheme);
        await HttpContext.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme,
                                      new ClaimsPrincipal(identity));

        // An address nobody knows goes on the waiting list, exactly as it
        // would coming back from Google. One approval model, not two.
        if (!accounts.IsAllowed(to)) accounts.RecordPending(to);
        log.LogInformation("Signed in with an email code: {Email}", to);
        return Redirect(Local(returnUrl));
    }

    [HttpGet("logout")]
    [HttpPost("logout")]
    public async Task<IActionResult> Logout()
    {
        await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        return Redirect("/");
    }

    /// <summary>Who is signed in — the painter's own header reads this.</summary>
    [HttpGet("me")]
    public IActionResult Me()
    {
        var email = User.FindFirstValue(ClaimTypes.Email);
        return Ok(new
        {
            signedIn = User.Identity?.IsAuthenticated == true,
            email,
            approved = accounts.IsAllowed(email),
            admin = accounts.IsAdmin(email),
        });
    }

    /// <summary>
    /// Signed in, not approved. A page of its own and not a bare 403: the
    /// person has to learn that they are WAITING rather than that something
    /// broke — and to be able to sign out and try another address.
    /// </summary>
    [HttpGet("pending")]
    public IActionResult Pending()
    {
        if (User.Identity?.IsAuthenticated != true) return Redirect("/");
        var email = User.FindFirstValue(ClaimTypes.Email) ?? "";
        if (accounts.IsAllowed(email)) return Redirect("/");
        ViewData["Email"] = email;
        ViewData["Admin"] = accounts.AdminEmail;
        return View();
    }

    [HttpGet("denied")]
    public IActionResult Denied() =>
        Content("This account is not allowed to use the editor.", "text/plain");

    // LOCAL paths only: otherwise a "login?returnUrl=…" link could send
    // somebody to a stranger's site once they had signed in.
    private string Local(string? url) => Url.IsLocalUrl(url) ? url! : "/";

    private IActionResult Back(string? returnUrl, string email, string stage, string message)
    {
        TempData["Msg"] = message;
        TempData["Stage"] = stage;
        TempData["Email"] = email;
        return RedirectToAction(nameof(Login), new { returnUrl, email });
    }
}
