namespace CpcLevelEditor.Exporters;

/// <summary>
/// One (overlay, background) pair the designer placed, after the bake has
/// decided what to do with it. The same shape as <c>build/city_baked.json</c>,
/// which is the record the build already keeps.
/// </summary>
/// <param name="Index">
/// The FINAL tile index the map's cells now point at. For a dropped pair
/// this is the overlay's own index, not a new one.
/// </param>
/// <param name="Over">The overlay's index in the artist's own tileset.</param>
/// <param name="Under">The final index of what it was composited onto.</param>
/// <param name="Name">The new tile's name, or the overlay's if it was dropped.</param>
/// <param name="Baked">
/// False when the composite came out byte for byte the overlay — the
/// background contributed nothing, so there is no reason to spend 64 bytes
/// of bank on a copy. Level 1 has exactly one of these, <c>tank_10</c>.
/// </param>
public readonly record struct BakedPair(int Index, int Over, int Under, string Name, bool Baked);
