using System.Text.Json;

namespace CpcLevelEditor.Web.Services;

/// <summary>One account and where it stands.</summary>
/// <param name="Email">Lower case, the way Google hands it over.</param>
/// <param name="Allowed">Approved? Otherwise it is waiting.</param>
/// <param name="Note">How it got on the list: invited, asked, approved, revoked.</param>
public sealed record Account(string Email, bool Allowed, string Note, DateTime Seen);

/// <summary>
/// Which accounts may use the editor.
/// </summary>
/// <remarks>
/// <para>
/// <b>SIGNING IN PROVES WHO YOU ARE, NOT THAT YOU HAVE BUSINESS HERE.</b>
/// Anyone with a Google account or a mailbox can reach the sign-in page; what
/// gets them past it is this list, and until the administrator says so they
/// see the waiting page and nothing else (<see cref="ApprovalGate"/>).
/// </para>
/// <para>
/// <b>The list lives OUTSIDE the repository</b>, in <c>App_Data/</c>, and is
/// not committed: they are real people's email addresses.
/// </para>
/// <para>
/// The administrator is always allowed and cannot be removed — otherwise one
/// wrong call locks out the only account that can unlock anything.
/// </para>
/// <para>
/// <b>There is no publish right here and the reference has one.</b>
/// GRAVASSIST's editor writes into a SHARED <c>levels/</c> that everybody
/// reads, so who may write there is a second decision. This editor's accounts
/// never write outside their own workspace: the four files an export makes
/// land in the account's own folder and a person moves them into
/// <c>build/</c>. A flag guarding an action that does not exist is a setting
/// that goes stale.
/// </para>
/// </remarks>
public sealed class AccountStore
{
    private const string DefaultAdmin = "vassilisnperantzakis@gmail.com";

    /// <summary>Where the list lives, if not beside the application.</summary>
    public const string DirectoryVar = "karaAccounts";

    private static readonly JsonSerializerOptions Json = new() { WriteIndented = true };

    private readonly string _path;
    private readonly Lock _gate = new();
    private Dictionary<string, Account> _all = new(StringComparer.OrdinalIgnoreCase);

    public string AdminEmail { get; }

    /// <param name="directory">Where <c>accounts.json</c> lives.</param>
    /// <param name="adminEmail">The administrator, or null for the default.</param>
    public AccountStore(string directory, string? adminEmail)
    {
        AdminEmail = Normalise(string.IsNullOrWhiteSpace(adminEmail) ? DefaultAdmin : adminEmail);
        Directory.CreateDirectory(directory);
        _path = Path.Combine(directory, "accounts.json");
        Load();
    }

    /// <summary>
    /// The one the editor runs with: <c>App_Data/</c> beside the application
    /// unless <see cref="DirectoryVar"/> says otherwise.
    /// </summary>
    public static AccountStore From(IConfiguration config, IHostEnvironment environment) =>
        new(config[DirectoryVar] is { Length: > 0 } set
                ? set
                : Path.Combine(environment.ContentRootPath, "App_Data"),
            config[EditorAuth.AdminVar]);

    public static string Normalise(string? email) => (email ?? "").Trim().ToLowerInvariant();

    /// <summary>
    /// A shape check and nothing more. The file is read by a person, and one
    /// line of rubbish in it looks like a fault in the program.
    /// </summary>
    public static bool LooksLikeEmail(string email) =>
        email.Length >= 3 && email.Contains('@') && !email.Contains(' ');

    public bool IsAdmin(string? email) => Normalise(email) == AdminEmail;

    public bool IsAllowed(string? email)
    {
        var key = Normalise(email);
        if (key.Length == 0) return false;
        if (key == AdminEmail) return true;
        lock (_gate)
            return _all.TryGetValue(key, out var account) && account.Allowed;
    }

    /// <summary>Everyone, with the ones still waiting first.</summary>
    public IReadOnlyList<Account> All()
    {
        lock (_gate)
            return [.. _all.Values
                .OrderBy(a => a.Allowed)
                .ThenBy(a => a.Email, StringComparer.OrdinalIgnoreCase)];
    }

    /// <summary>The administrator invites an address: it arrives approved.</summary>
    public bool Invite(string? email) => Set(email, allowed: true, note: "invited");

    /// <summary>... and approves one that asked for itself.</summary>
    public bool Approve(string? email) => Set(email, allowed: true, note: "approved");

    /// <summary>Takes access away. The account's workspace is NOT touched.</summary>
    public bool Revoke(string? email) => Change(email, a => a with
    {
        Allowed = false,
        Note = "revoked",
        Seen = DateTime.UtcNow,
    });

    /// <summary>
    /// Forgets the account entirely.
    /// </summary>
    /// <remarks>
    /// <b>Not the same as revoking.</b> A revoked account stays on the list as
    /// a "no", so asking again changes nothing — that is the block. Deleting
    /// FORGETS it: sign in again and it shows up as a fresh request. For
    /// tidying the list, not for shutting anyone out. Its files are left
    /// alone; a click on an admin screen must not destroy anyone's work.
    /// </remarks>
    public bool Delete(string? email)
    {
        var key = Normalise(email);
        if (key.Length == 0 || key == AdminEmail) return false;
        lock (_gate)
        {
            if (!_all.Remove(key)) return false;
            Save();
        }
        return true;
    }

    /// <summary>
    /// Writes down somebody who signed in and is not allowed yet, so the
    /// administrator can see them and decide. It grants nothing.
    /// </summary>
    public void RecordPending(string? email)
    {
        var key = Normalise(email);
        if (key.Length == 0 || key == AdminEmail || !LooksLikeEmail(key)) return;
        lock (_gate)
        {
            if (_all.ContainsKey(key)) return;      // do not tread on a decision
            _all[key] = new Account(key, false, "asked", DateTime.UtcNow);
            Save();
        }
    }

    private bool Set(string? email, bool allowed, string note)
    {
        var key = Normalise(email);
        if (!LooksLikeEmail(key)) return false;
        lock (_gate)
        {
            _all[key] = new Account(key, allowed, note, DateTime.UtcNow);
            Save();
        }
        return true;
    }

    private bool Change(string? email, Func<Account, Account> how)
    {
        var key = Normalise(email);
        if (key.Length == 0 || key == AdminEmail) return false;
        lock (_gate)
        {
            if (!_all.TryGetValue(key, out var account)) return false;
            _all[key] = how(account);
            Save();
        }
        return true;
    }

    private void Load()
    {
        if (!File.Exists(_path)) return;
        try
        {
            var list = JsonSerializer.Deserialize<List<Account>>(File.ReadAllText(_path)) ?? [];
            _all = list.ToDictionary(a => a.Email, a => a, StringComparer.OrdinalIgnoreCase);
        }
        catch (JsonException)
        {
            // A broken file starts us empty rather than stopping the editor.
            // The administrator is always allowed, so they can rebuild it.
            _all = new Dictionary<string, Account>(StringComparer.OrdinalIgnoreCase);
        }
    }

    private void Save() =>
        File.WriteAllText(_path, JsonSerializer.Serialize(_all.Values.ToList(), Json));
}
