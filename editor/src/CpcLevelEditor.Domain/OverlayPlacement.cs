namespace CpcLevelEditor.Domain;

/// <summary>
/// A designer dropping an overlay tile on a cell: the lamp on the wall, the
/// water tank on the roof.
/// </summary>
/// <param name="X">Map column.</param>
/// <param name="Y">Map row.</param>
/// <param name="Overlay">The overlay tile's own index in the tileset.</param>
/// <remarks>
/// <para>
/// <b>What is NOT here is the background</b>, and that is deliberate: it is
/// whatever the map already holds at that cell when the bake runs, which is
/// how an overlay comes to stand on another composite (level 1's
/// <c>tank_21</c> sits on the cell holding <c>ac_unit_on_far_fill</c>). The
/// baker resolves that recursively.
/// </para>
/// <para>
/// The ENGINE never sees one of these. <c>DRAW_COLUMN</c>, <c>DRAW_ROW</c>
/// and <c>DRAW_CELL</c> are plain copies and stay that way — a masked cell
/// is 1,338-2,007 T against a scrolling frame's 3,548 of headroom, so two
/// overlay cells in one column would be the whole budget (CLAUDE.md 7.3).
/// The composite does not change between frames, so it is done once, here.
/// </para>
/// </remarks>
public readonly record struct OverlayPlacement(int X, int Y, byte Overlay);
