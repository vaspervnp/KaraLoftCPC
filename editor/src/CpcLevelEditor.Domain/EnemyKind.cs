namespace CpcLevelEditor.Domain;

/// <summary>
/// Which character an <see cref="EntityKind.Enemy"/> record is —
/// <c>p0</c>, under the rule that <c>p0</c> is always "which thing this is"
/// (CLAUDE.md 8.6).
/// </summary>
/// <remarks>
/// <para>
/// <b>This is the ENGINE's type table and not the art package's.</b>
/// <c>assets/sprites/</c> carries seven named characters across the six
/// levels (CLAUDE.md 7.1); <c>ENEMY_TYPES</c> in <c>src/enemy.asm</c> has
/// two rows, and <c>p0</c> indexes that table. Everything else about an
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
    /// <c>EN_AGENT</c> — 12×64, 194-274 span bytes, <b>40,760-48,820 T
    /// drawn and erased.</b> Its row is in the table and its art is on the
    /// disc; nothing places one, because the frame has not got it
    /// (CLAUDE.md 8.7).
    /// </summary>
    Agent = 0,

    /// <summary>
    /// <c>EN_DRONE</c> — 8×20, 17,144-19,240 T, and affordable only
    /// because it is a persistent sprite that is never redrawn on a
    /// scrolling frame. Level 1 ships three.
    /// </summary>
    Drone = 1,
}
