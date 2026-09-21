using System.Security.Claims;
using CpcLevelEditor.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace CpcLevelEditor.Web.Controllers;

/// <summary>
/// The accounts screen — the administrator's alone.
/// </summary>
/// <remarks>
/// The check is in each action through <see cref="Guard"/> rather than in an
/// attribute: an attribute would want a policy and a role of its own, and a
/// check that fits in two lines does not deserve three places to configure
/// where one of them can be forgotten.
/// </remarks>
[Route("admin")]
public sealed class AdminController(AccountStore accounts, IMailer mail) : Controller
{
    [HttpGet("")]
    public IActionResult Index()
    {
        if (Guard() is { } stop) return stop;
        ViewData["Admin"] = accounts.AdminEmail;
        ViewData["Mail"] = mail.IsConfigured;
        ViewData["From"] = mail.From ?? "";
        return View(accounts.All());
    }

    [HttpPost("invite")]
    [ValidateAntiForgeryToken]
    public IActionResult Invite(string email) => Act(
        () => accounts.Invite(email),
        $"{AccountStore.Normalise(email)} can sign in.",
        "That does not look like an email address.");

    [HttpPost("approve")]
    [ValidateAntiForgeryToken]
    public IActionResult Approve(string email) => Act(
        () => accounts.Approve(email),
        $"{AccountStore.Normalise(email)} is approved.",
        "That address is not on the list.");

    [HttpPost("revoke")]
    [ValidateAntiForgeryToken]
    public IActionResult Revoke(string email) => Act(
        () => accounts.Revoke(email),
        $"{AccountStore.Normalise(email)} can no longer sign in. Their files are untouched.",
        "That address cannot be revoked.");

    [HttpPost("delete")]
    [ValidateAntiForgeryToken]
    public IActionResult Delete(string email) => Act(
        () => accounts.Delete(email),
        $"{AccountStore.Normalise(email)} is off the list. Asking again shows up as new.",
        "That address cannot be deleted.");

    /// <summary>
    /// Sends a test message to the administrator.
    /// </summary>
    /// <remarks>
    /// <b>Why it exists</b>: an SMTP setting rarely works first time — wrong
    /// port, an app password, a sender that does not match the account —  and
    /// without this you would find out through the sign-in form, where the
    /// answer is deliberately vague so it cannot leak which addresses exist.
    /// </remarks>
    [HttpPost("mailtest")]
    [ValidateAntiForgeryToken]
    public async Task<IActionResult> MailTest()
    {
        if (Guard() is { } stop) return stop;
        if (!mail.IsConfigured)
        {
            TempData["Msg"] = $"No mail settings: {SmtpMailer.HostVar} and "
                            + $"{SmtpMailer.FromVar} must be set in the environment.";
            return RedirectToAction(nameof(Index));
        }

        var sent = await mail.SendAsync(accounts.AdminEmail,
            "Kara Loft editor — test message",
            $"""
             This is a test from the Kara Loft level editor.

             If you are reading it, the mail settings work and sign-in codes
             will go out.

             Sent from: {mail.From}
             """);
        TempData["Msg"] = sent
            ? $"Test message sent to {accounts.AdminEmail}."
            : "Sending failed. The mail server's own error is in the editor's log.";
        return RedirectToAction(nameof(Index));
    }

    private bool IsAdmin => accounts.IsAdmin(User.FindFirstValue(ClaimTypes.Email));

    // 404 and not 403: that the page exists is nobody else's business.
    private IActionResult? Guard() => IsAdmin ? null : StatusCode(404);

    private IActionResult Act(Func<bool> change, string done, string failed)
    {
        if (Guard() is { } stop) return stop;
        TempData["Msg"] = change() ? done : failed;
        return RedirectToAction(nameof(Index));
    }
}
