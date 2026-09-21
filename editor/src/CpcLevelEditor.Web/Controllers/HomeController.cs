using Microsoft.AspNetCore.Mvc;

namespace CpcLevelEditor.Web.Controllers;

/// <summary>
/// The painter itself.
/// </summary>
/// <remarks>
/// <b>It is a view and no longer a static file</b>, which is the whole point:
/// <c>UseStaticFiles</c> runs before authorization, so anything in
/// <c>wwwroot/</c> is public. As <c>index.html</c> the page came up for
/// anybody and then failed every API call it made, which reads as a broken
/// editor rather than as a closed one. Served from here it is behind the
/// fallback policy, so a stranger gets the sign-in page instead. The script
/// and the stylesheet stay in <c>wwwroot/</c> and stay public: there is
/// nothing in them.
/// </remarks>
public sealed class HomeController : Controller
{
    [HttpGet("/")]
    public IActionResult Index() => View();
}
