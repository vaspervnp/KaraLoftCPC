using System.Net;
using System.Net.Mail;

namespace CpcLevelEditor.Web.Services;

/// <summary>
/// Somewhere to send a sign-in code.
/// </summary>
/// <remarks>
/// <b>An interface, where the reference has a class</b>, and for this
/// project's own reason: the email road is a credential path, and a
/// credential path nothing can test is one nobody has checked. With this the
/// suite drives the whole of it — ask for a code, read it out of the message
/// that was "sent", and sign in — instead of testing the two halves either
/// side of an SMTP call.
/// </remarks>
public interface IMailer
{
    /// <summary>Can mail be sent at all? If not, the editor hides that road.</summary>
    bool IsConfigured { get; }

    /// <summary>The sender, for the administrator's own screen.</summary>
    string? From { get; }

    /// <summary>
    /// Sends one text message and says whether it worked. It does NOT throw:
    /// the caller has to answer the person, not fall over.
    /// </summary>
    Task<bool> SendAsync(string to, string subject, string body);
}

/// <summary>
/// SMTP, with the framework's own client and no package.
/// </summary>
/// <remarks>
/// <para>
/// The editor has no dependency on any service or CDN and there is no reason
/// for it to gain one in order to send two kinds of message. <b>Note</b>:
/// <see cref="SmtpClient"/> does STARTTLS (port 587) and does NOT do implicit
/// TLS (port 465).
/// </para>
/// <para>
/// <b>Unconfigured, the editor still runs</b> — it simply does not offer the
/// email road. That is deliberately unlike the sign-in configuration as a
/// whole, which stops the start-up: there, nothing configured means an OPEN
/// editor; here it means one road fewer (<see cref="EditorAuth"/>).
/// </para>
/// </remarks>
public sealed class SmtpMailer(IConfiguration config, ILogger<SmtpMailer> log) : IMailer
{
    public const string HostVar = "karaSmtpHost";
    public const string PortVar = "karaSmtpPort";
    public const string UserVar = "karaSmtpUser";
    public const string PassVar = "karaSmtpPass";
    public const string FromVar = "karaMailFrom";
    public const string NameVar = "karaMailName";
    public const string TlsVar = "karaSmtpTls";

    private string? Host => Blank(config[HostVar]);
    private string? User => Blank(config[UserVar]);
    private string? Pass => Blank(config[PassVar]);

    /// <summary>The sender; if unset, the SMTP account itself.</summary>
    public string? From => Blank(config[FromVar]) ?? User;

    public string DisplayName => Blank(config[NameVar]) ?? "Kara Loft level editor";

    public int Port =>
        int.TryParse(config[PortVar], out var port) && port is > 0 and < 65536 ? port : 587;

    /// <summary>
    /// STARTTLS, OFF by default; <c>karaSmtpTls=true</c> turns it on.
    /// <para>
    /// <b>Know what that means</b>: without it the SMTP account's password and
    /// every sign-in code travel in clear text. It is fine only for a relay on
    /// the same machine, which is why <see cref="SendAsync"/> complains in the
    /// log when the server is somewhere else.
    /// </para>
    /// </summary>
    public bool UseTls =>
        string.Equals(config[TlsVar], "true", StringComparison.OrdinalIgnoreCase);

    public bool IsConfigured => Host is not null && From is not null;

    private bool HostIsLocal => Host is "localhost" or "127.0.0.1" or "::1";

    public async Task<bool> SendAsync(string to, string subject, string body)
    {
        if (!IsConfigured)
        {
            log.LogWarning("No mail sent to {To}: {Host} and {From} are not set.",
                           to, HostVar, FromVar);
            return false;
        }

        // An unprotected connection to somebody ELSE'S machine: not forbidden
        // — it is the administrator's setting — but not silent either, because
        // the SMTP account's password goes out with the message.
        if (!UseTls && !HostIsLocal)
            log.LogWarning("SMTP WITHOUT TLS to {Host}:{Port}. The account's password and "
                           + "the sign-in codes go in clear text. Set {Var}=true if the "
                           + "server supports it.", Host, Port, TlsVar);

        try
        {
            using var client = new SmtpClient(Host!, Port)
            {
                EnableSsl = UseTls,
                DeliveryMethod = SmtpDeliveryMethod.Network,
                Timeout = 20_000,
            };
            // Without credentials SmtpClient would send anonymously, which
            // some internal relays accept, so it is not forced.
            if (User is not null && Pass is not null)
                client.Credentials = new NetworkCredential(User, Pass);

            using var message = new MailMessage
            {
                From = new MailAddress(From!, DisplayName),
                Subject = subject,
                Body = body,
                IsBodyHtml = false,
            };
            message.To.Add(to);

            await client.SendMailAsync(message);
            log.LogInformation("Mail to {To}: {Subject}", to, subject);
            return true;
        }
        catch (Exception e) when (e is SmtpException or InvalidOperationException
                                    or FormatException or IOException)
        {
            // THE WHOLE error in the log: an SMTP failure is almost always a
            // setting — wrong port, an app password, a sender that does not
            // match the account — and the provider's own message says which.
            log.LogError(e, "Could not send mail to {To} through {Host}:{Port}.",
                         to, Host, Port);
            return false;
        }
    }

    private static string? Blank(string? s) => string.IsNullOrWhiteSpace(s) ? null : s.Trim();
}
