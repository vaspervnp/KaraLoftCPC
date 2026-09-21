using System.Security.Claims;
using System.Text;
using CpcLevelEditor.Application;

namespace CpcLevelEditor.Web.Services;

/// <summary>
/// One account's own projects: <c>workspace/&lt;account&gt;/</c>.
/// </summary>
/// <remarks>
/// <para>
/// <b>It is SCOPED and not a singleton</b>, because its root depends on WHO
/// is asking. As a singleton it would pin the first account that signed in
/// and everybody afterwards would paint on that one's levels.
/// </para>
/// <para>
/// <b>It starts EMPTY, and the reference's does not.</b> GRAVASSIST seeds a
/// new folder from the shared <c>levels/</c> so a designer opens on the
/// existing rooms. Here the shared thing is not a folder of projects, it is
/// the level the game already plays — and any account can open that whenever
/// it likes, straight out of <c>build/</c>. There is nothing to copy.
/// </para>
/// <para>
/// <b>THE FOLDER'S NAME COMES FROM THE EMAIL, CLEANED.</b> The check is not a
/// matter of taste: a <c>..</c> or a <c>/</c> inside a claim would write
/// outside the workspace, so only safe characters are kept and the path that
/// comes out is verified to be under the root.
/// </para>
/// </remarks>
public sealed class UserWorkspace
{
    private readonly string _root;

    public UserWorkspace(EditorOptions options, IHttpContextAccessor http)
    {
        var user = http.HttpContext?.User;
        var key = user is null ? "unknown" : KeyFor(user);
        var root = Path.GetFullPath(Path.Combine(options.Workspace, key));
        var parent = Path.GetFullPath(options.Workspace);
        // Belt as well as braces: KeyFor cannot produce a separator, and this
        // is what says so at run time rather than in a comment.
        if (!root.StartsWith(parent + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            throw new InvalidOperationException($"\"{key}\" is not a folder name");
        _root = root;
    }

    /// <summary>Where this account's projects and exports live.</summary>
    public string Root
    {
        get
        {
            Directory.CreateDirectory(_root);
            return _root;
        }
    }

    /// <summary>
    /// An account into a safe folder name: letters, digits, dot, dash and
    /// underscore, with <c>@</c> spelled out so two addresses cannot collide
    /// by losing it.
    /// </summary>
    public static string KeyFor(ClaimsPrincipal user)
    {
        var raw = user.FindFirstValue(ClaimTypes.Email)
                  ?? user.FindFirstValue(ClaimTypes.NameIdentifier)
                  ?? "";
        var name = new StringBuilder(raw.Length);
        foreach (var c in raw.ToLowerInvariant())
        {
            if (char.IsAsciiLetterOrDigit(c) || c is '.' or '-' or '_') name.Append(c);
            else if (c == '@') name.Append("_at_");
        }

        var key = name.ToString().Trim('.');
        return key.Length == 0 ? "unknown" : key;
    }
}
