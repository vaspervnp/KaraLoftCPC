namespace CpcLevelEditor.Domain;

/// <summary>
/// Which character an <see cref="EntityKind.Enemy"/> record is —
/// <c>p0</c>, under the rule that <c>p0</c> is always "which thing this is"
/// (CLAUDE.md 8.6).
/// </summary>
/// <remarks>
/// <para>
/// <b>This is the ENGINE's type table and not the art package's.</b>
/// <c>assets/sprites/</c> carries the named characters of six levels
/// (CLAUDE.md 7.1); <c>ENEMY_TYPES</c> in <c>src/enemy_types.asm</c> has
/// ten rows, and <c>p0</c> indexes that table. Everything else about an
/// enemy — its art, both facings' banks, the box, the speed, the fire
/// period and the hit points — comes from the row, which is why a designer
/// places a character rather than a set of numbers (CLAUDE.md 8.7).
/// </para>
/// <para>
/// <b>A <c>p0</c> at or past the end is not a different enemy, it is no
/// enemy at all.</b> <c>ENEMY_ADD</c> compares against <c>EN_KINDS</c> and
/// skips the record, so it sits in the table costing a slot of
/// <c>ENT_MAX</c> and nothing ever spawns. <see cref="Application"/>'s
/// validator says so; without this enum it could not, because the number
/// had no list behind it.
/// </para>
/// </remarks>
public enum EnemyKind : byte
{
    /// <summary>
    /// <c>EN_AGENT</c> — the City's, 12×64, and a <b>SENTRY</b>: it keeps
    /// its post, aims at her and fires, and is drawn by a COMPILED cel —
    /// 15,500 T where the span blitter took 35,000 — and redrawn only when
    /// it turns (CLAUDE.md 8.27). Where it may stand is a promise about
    /// video RAM: no line of its box may cross a 256-byte page, and
    /// <c>tools/sentries.py</c> checks the column. Level 4 places one.
    /// </summary>
    Agent = 0,

    /// <summary>
    /// <c>EN_DRONE</c> — 8×20, 17,144-19,240 T, and affordable only
    /// because it is a persistent sprite that is never redrawn on a
    /// scrolling frame. Level 1 ships three.
    /// </summary>
    Drone = 1,

    /// <summary>
    /// <c>EN_SNIPER</c> — the forest's, and a sentry like the agent
    /// (CLAUDE.md 8.27). Through the span blitter it was 80 game frames in
    /// 200 (CLAUDE.md 9); compiled and redrawn only when it turns, level 8
    /// places one - and level 7, whose field of eight traps has no time to
    /// spare even for the table's walk, does not.
    /// </summary>
    /// <remarks>
    /// <b>A row is a CHARACTER and not a level</b>, so this enum lists
    /// every character the engine knows and says nothing about which
    /// environment's banks are loaded. Placing a <see cref="Drone"/> in
    /// the forest is a legal record that draws out of the City's address
    /// in somebody else's banks — the same fault the pickups' art had
    /// (CLAUDE.md 8.6), and a rule this validator does not have yet.
    /// </remarks>
    Sniper = 2,

    /// <summary>
    /// <c>EN_SEADRONE</c> — the undersea's security drone, 32×16 pixels, and
    /// the City's drone's rules in the water: it follows her once it has
    /// been on the screen, with the follow's distances the swimmer's
    /// (CLAUDE.md 8.20).
    /// </summary>
    SeaDrone = 3,

    /// <summary>
    /// <c>EN_BAT</c> — the cave's, 16×16, and the first character that
    /// <b>bites</b>: where a drone fires, a bat swoops to her side and a
    /// box that reaches hers costs her 8 points (CLAUDE.md 8.24). One of
    /// her rounds brings it down.
    /// </summary>
    Bat = 4,

    /// <summary>
    /// <c>EN_WOLF</c> — the forest's, 32×24, on the ground it was placed
    /// on: it keeps its distance, lunges, and bites for 8 (CLAUDE.md 8.24).
    /// </summary>
    Wolf = 5,

    /// <summary>
    /// <c>EN_BOAR</c> — the forest's heavier beast: slower to charge,
    /// three rounds to stop, and a bite of 16 (CLAUDE.md 8.24).
    /// </summary>
    Boar = 6,

    /// <summary>
    /// <c>EN_MERC</c> — the desert's mercenary, 12×64, a sentry
    /// (CLAUDE.md 8.27). Two a level, standing on the sand.
    /// </summary>
    Mercenary = 7,

    /// <summary>
    /// <c>EN_GUARD</c> — the station's cyber guard, 12×64, a sentry with
    /// four hit points (CLAUDE.md 8.27).
    /// </summary>
    Guard = 8,

    /// <summary>
    /// <c>EN_TURRET</c> — the station's wall turret, 8×16: it keeps its
    /// post like a sentry and is drawn by the span blitter, because it is
    /// small enough to be cheap (CLAUDE.md 8.27).
    /// </summary>
    Turret = 9,
}
