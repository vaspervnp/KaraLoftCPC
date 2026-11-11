namespace CpcLevelEditor.Domain;

/// <summary>
/// What a hazard IS — <c>p0</c> on an <see cref="EntityKind.Hazard"/> record,
/// because <c>p0</c> is always "which thing this is" (CLAUDE.md 8.6).
/// </summary>
/// <remarks>
/// <para>
/// <b>This is the ENGINE's table</b> — <c>HZ_KINDS</c> in
/// <c>src/hazard.asm</c> — and <c>HAZARD_SPAWN</c> skips any record at or
/// past its end, so the validator refuses one. <c>tools/test_forest7.py</c>
/// reads this file and compares it with the build.
/// </para>
/// <para>
/// <b>What a hazard does to her is its TILE's, not the record's.</b> A spike
/// trap is a map cell whose tile goes round four consecutive indexes —
/// composited at build time out of the artist's four cels — and the ones
/// that bite carry <see cref="TileFlags.Hazard"/>. So the record's
/// <c>p1</c> is the cel it starts on, and the damage and the period are the
/// type's (CLAUDE.md 8.17).
/// </para>
/// </remarks>
public enum HazardKind : byte
{
    /// <summary>The forest's retractable spike trap: retracted, half, full, half.</summary>
    SpikeTrap = 0,
}
