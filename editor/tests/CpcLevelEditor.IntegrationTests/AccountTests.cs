using CpcLevelEditor.Web.Services;
using Microsoft.Extensions.Logging.Abstractions;

namespace CpcLevelEditor.IntegrationTests;

/// <summary>
/// The account list and the sign-in codes, driven straight.
/// </summary>
/// <remarks>
/// They live in this project because it is the one that has the editor's web
/// assembly; neither needs a host. What they are about is the half of the
/// sign-in that an HTTP test can only see the outside of — a code being spent,
/// a guess being counted, a list that survives being reloaded.
/// </remarks>
public class AccountTests
{
    private const string Admin = "boss@example.invalid";

    private static AccountStore Store(string directory) => new(directory, Admin);

    private static LoginCodes Codes() => new(NullLogger<LoginCodes>.Instance);

    /// <summary>
    /// <b>The administrator is allowed without being on the list and cannot
    /// be taken off it</b> — otherwise one wrong call locks out the only
    /// account that can unlock anything.
    /// </summary>
    [Fact]
    public void The_administrator_is_always_allowed()
    {
        var root = Temporary();
        try
        {
            var accounts = Store(root);

            Assert.True(accounts.IsAllowed(Admin));
            Assert.True(accounts.IsAdmin("  BOSS@Example.Invalid "));   // normalised
            Assert.False(accounts.Revoke(Admin));
            Assert.False(accounts.Delete(Admin));
            Assert.True(accounts.IsAllowed(Admin));

            // ... and signing in as the administrator does not add a row
            accounts.RecordPending(Admin);
            Assert.Empty(accounts.All());
        }
        finally { Directory.Delete(root, recursive: true); }
    }

    /// <summary>
    /// <b>Revoking is not deleting.</b> A revoked account stays on the list as
    /// a "no", so asking again changes nothing — that is the block. Deleting
    /// forgets it, and the next sign-in shows up as a fresh request.
    /// </summary>
    [Fact]
    public void Revoking_blocks_and_deleting_forgets()
    {
        var root = Temporary();
        try
        {
            var accounts = Store(root);
            const string who = "painter@example.invalid";

            Assert.True(accounts.Invite(who));
            Assert.True(accounts.IsAllowed(who));

            Assert.True(accounts.Revoke(who));
            Assert.False(accounts.IsAllowed(who));
            accounts.RecordPending(who);                    // asks again
            Assert.False(accounts.IsAllowed(who));          // ... and is still out
            Assert.Equal("revoked", accounts.All().Single().Note);

            Assert.True(accounts.Delete(who));
            Assert.Empty(accounts.All());
            accounts.RecordPending(who);
            Assert.Equal("asked", accounts.All().Single().Note);
        }
        finally { Directory.Delete(root, recursive: true); }
    }

    [Fact]
    public void The_list_survives_a_restart_and_a_broken_file()
    {
        var root = Temporary();
        try
        {
            Store(root).Invite("kept@example.invalid");
            Assert.True(Store(root).IsAllowed("kept@example.invalid"));

            // A BROKEN FILE STARTS US EMPTY rather than stopping the editor:
            // the administrator is allowed whatever the file says, so they can
            // rebuild it. Refusing to start would lock everyone out over a
            // stray byte.
            File.WriteAllText(Path.Combine(root, "accounts.json"), "{ not json");
            var accounts = Store(root);
            Assert.Empty(accounts.All());
            Assert.True(accounts.IsAllowed(Admin));
        }
        finally { Directory.Delete(root, recursive: true); }
    }

    [Theory]
    [InlineData("someone@example.invalid", true)]
    [InlineData("no-at-sign", false)]
    [InlineData("a b@example.invalid", false)]
    [InlineData("", false)]
    public void Only_something_shaped_like_an_address_goes_on_the_list(string email, bool ok)
    {
        var root = Temporary();
        try
        {
            Assert.Equal(ok, Store(root).Invite(email));
        }
        finally { Directory.Delete(root, recursive: true); }
    }

    /// <summary>One code, one sign-in: it is spent when it works.</summary>
    [Fact]
    public void A_code_works_once()
    {
        var codes = Codes();
        var (result, code) = codes.Issue("one@example.invalid", "10.0.0.1");

        Assert.Equal(CodeRequest.Sent, result);
        Assert.Matches("^[0-9]{6}$", code);
        Assert.True(codes.Pending("one@example.invalid"));
        Assert.True(codes.Verify("one@example.invalid", code));
        Assert.False(codes.Verify("one@example.invalid", code));
        Assert.False(codes.Pending("one@example.invalid"));
    }

    /// <summary>
    /// <b>And it cannot be guessed by repetition</b>: after five wrong
    /// answers the code is thrown away, so the right one stops working too.
    /// </summary>
    [Fact]
    public void Five_wrong_answers_throw_the_code_away()
    {
        var codes = Codes();
        var (_, code) = codes.Issue("two@example.invalid", "10.0.0.1");
        var wrong = code == "000000" ? "111111" : "000000";

        for (var i = 0; i < 5; i++)
            Assert.False(codes.Verify("two@example.invalid", wrong));

        Assert.False(codes.Verify("two@example.invalid", code));
    }

    /// <summary>
    /// <b>The limits are not for the user, they are for the victims</b>:
    /// without them the sign-in form is a machine for sending mail to any
    /// address somebody types.
    /// </summary>
    [Fact]
    public void There_is_a_cap_per_address_and_a_wider_one_per_machine()
    {
        var codes = Codes();

        // FIVE PER ADDRESS. Each code is spent before the next is asked for,
        // so the minute's cooldown is not what stops this — the hourly count
        // per address is.
        Spend(codes, "three@example.invalid", "10.0.0.1", 5);
        Assert.Equal(CodeRequest.TooMany,
                     codes.Issue("three@example.invalid", "10.0.0.1").Result);
        // ... and it is the ADDRESS that is barred, not the machine: somebody
        // else at the same desk can still sign in.
        Assert.Equal(CodeRequest.Sent,
                     codes.Issue("four@example.invalid", "10.0.0.1").Result);
        // ... and the same address from elsewhere is still that address
        Assert.Equal(CodeRequest.TooMany,
                     codes.Issue("three@example.invalid", "10.0.0.2").Result);

        // TEN PER MACHINE, which is the limit that matters: one sender, many
        // victims. Six have gone from this one already, and four more fill it.
        Spend(codes, "five@example.invalid", "10.0.0.1", 4);
        Assert.Equal(CodeRequest.TooMany,
                     codes.Issue("six@example.invalid", "10.0.0.1").Result);
        Assert.Equal(CodeRequest.Sent,
                     codes.Issue("six@example.invalid", "10.0.0.9").Result);
    }

    /// <summary>Ask for a code and use it, so the next ask is not too soon.</summary>
    private static void Spend(LoginCodes codes, string email, string ip, int times)
    {
        for (var i = 0; i < times; i++)
        {
            var (result, code) = codes.Issue(email, ip);
            Assert.Equal(CodeRequest.Sent, result);
            Assert.True(codes.Verify(email, code));
        }
    }

    /// <summary>Asking again straight away does not make a second code.</summary>
    [Fact]
    public void Asking_twice_in_a_minute_keeps_the_first_code()
    {
        var codes = Codes();
        var (_, first) = codes.Issue("five@example.invalid", "10.0.0.1");

        Assert.Equal(CodeRequest.TooSoon, codes.Issue("five@example.invalid", "10.0.0.1").Result);
        Assert.True(codes.Verify("five@example.invalid", first));
    }

    private static string Temporary() =>
        Directory.CreateTempSubdirectory("cpc-editor-accounts-").FullName;
}
