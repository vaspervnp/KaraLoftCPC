using CpcLevelEditor.Domain;

namespace CpcLevelEditor.Exporters;

/// <param name="Map">The map with every cell pointing at a finished tile.</param>
/// <param name="Tileset">The artist's tiles with the composites appended.</param>
/// <param name="Pairs">What was placed, in the order it was placed.</param>
public readonly record struct OverlayBakeResult(
    byte[] Map, Tileset Tileset, IReadOnlyList<BakedPair> Pairs);
