using System.Security.Cryptography;
using System.Text;

namespace CpcLevelEditor.Web.Services;

/// <summary>What came of asking for a code.</summary>
public enum CodeRequest
{
    /// <summary>A code was made — send it.</summary>
    Sent,

    /// <summary>Asked again too soon; the last one is still good.</summary>
    TooSoon,

    /// <summary>Too many requests. No code is made.</summary>
    TooMany,
}

/// <summary>
/// The six-digit codes that stand in for a password.
/// </summary>
/// <remarks>
/// <para>
/// <b>The code in the mailbox IS the proof of identity</b>, so everything
/// true of a one-time password is true here: a short life, few attempts, and
/// only the HASH kept — a log or a memory dump must not hand anyone a
/// finished sign-in.
/// </para>
/// <para>
/// <b>It lives in memory.</b> A restart voids every code in flight and the
/// person asks for another. Writing live credentials to disc to save them
/// that would be a poor trade.
/// </para>
/// <para>
/// <b>The limits are not for the user, they are for the victims</b>: without
/// them the sign-in form is a machine for sending mail to any address
/// somebody types. Hence a cap per address, per IP and overall.
/// </para>
/// </remarks>
public sealed class LoginCodes(ILogger<LoginCodes> log)
{
    public static readonly TimeSpan Lifetime = TimeSpan.FromMinutes(10);
    public static readonly TimeSpan Cooldown = TimeSpan.FromSeconds(60);
    private static readonly TimeSpan Window = TimeSpan.FromHours(1);

    private const int MaxAttempts = 5;
    private const int PerEmailPerHour = 5;
    private const int PerIpPerHour = 10;
    private const int TotalPerHour = 100;

    private readonly Lock _gate = new();
    private readonly Dictionary<string, Entry> _live = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<(DateTime When, string Email, string Ip)> _recent = [];

    /// <summary>
    /// Makes a code for the address. It is returned ONCE, to be sent; nothing
    /// can read it back.
    /// </summary>
    public (CodeRequest Result, string? Code) Issue(string email, string ip)
    {
        var key = AccountStore.Normalise(email);
        var now = DateTime.UtcNow;
        lock (_gate)
        {
            Prune(now);

            if (_live.TryGetValue(key, out var live) && now - live.Sent < Cooldown)
                return (CodeRequest.TooSoon, null);

            if (_recent.Count >= TotalPerHour
                || _recent.Count(r => r.Email == key) >= PerEmailPerHour
                || _recent.Count(r => r.Ip == ip) >= PerIpPerHour)
            {
                log.LogWarning("Sign-in codes barred for {Email} from {Ip}.", key, ip);
                return (CodeRequest.TooMany, null);
            }

            // 000000..999999, evenly. RandomNumberGenerator and not Random,
            // because the code IS the credential.
            var code = RandomNumberGenerator.GetInt32(0, 1_000_000).ToString("D6");
            var salt = RandomNumberGenerator.GetBytes(16);
            _live[key] = new Entry
            {
                Salt = salt,
                Hash = Hash(code, salt),
                Expires = now + Lifetime,
                Sent = now,
                Attempts = MaxAttempts,
            };
            _recent.Add((now, key, ip));
            return (CodeRequest.Sent, code);
        }
    }

    /// <summary>
    /// Right code? It is spent on success — one code, one sign-in — and after
    /// <see cref="MaxAttempts"/> failures it is thrown away, so it cannot be
    /// guessed by repetition.
    /// </summary>
    public bool Verify(string email, string? code)
    {
        var key = AccountStore.Normalise(email);
        var given = (code ?? "").Trim();
        var now = DateTime.UtcNow;
        lock (_gate)
        {
            Prune(now);
            if (!_live.TryGetValue(key, out var entry)) return false;
            if (now > entry.Expires)
            {
                _live.Remove(key);
                return false;
            }

            // Fixed time: a comparison that stops at the first wrong digit
            // leaks how many digits were right.
            if (CryptographicOperations.FixedTimeEquals(Hash(given, entry.Salt), entry.Hash))
            {
                _live.Remove(key);
                return true;
            }

            if (--entry.Attempts <= 0)
            {
                _live.Remove(key);
                log.LogWarning("Too many wrong codes for {Email}.", key);
            }

            return false;
        }
    }

    /// <summary>Is a code in flight? The sign-in page is the only caller.</summary>
    public bool Pending(string email)
    {
        var key = AccountStore.Normalise(email);
        lock (_gate)
        {
            Prune(DateTime.UtcNow);
            return _live.ContainsKey(key);
        }
    }

    private void Prune(DateTime now)
    {
        _recent.RemoveAll(r => now - r.When > Window);
        foreach (var key in _live.Where(p => now > p.Value.Expires).Select(p => p.Key).ToList())
            _live.Remove(key);
    }

    private static byte[] Hash(string code, byte[] salt) =>
        SHA256.HashData([.. salt, .. Encoding.UTF8.GetBytes(code)]);

    private sealed class Entry
    {
        public byte[] Hash = [];
        public byte[] Salt = [];
        public DateTime Expires;
        public DateTime Sent;
        public int Attempts;
    }
}
