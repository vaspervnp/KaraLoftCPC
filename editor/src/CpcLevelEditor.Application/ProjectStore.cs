namespace CpcLevelEditor.Application;

/// <summary>What the editor keeps its levels in.</summary>
public interface IProjectStore
{
    IReadOnlyList<string> List();

    EditorProject? Load(string id);

    void Save(EditorProject project);
}

/// <summary>
/// One JSON file per project in a directory — see <see cref="ProjectJson"/>
/// for why a directory and not a database.
/// </summary>
public sealed class FileProjectStore(string root) : IProjectStore
{
    /// <summary>
    /// Ids are a slug because they become a file name. Anything else is a
    /// path the caller chose, and a store that takes one of those from an
    /// HTTP route is a directory traversal.
    /// </summary>
    public static bool IsValidId(string id) =>
        id.Length is > 0 and <= 64
        && id.All(c => char.IsAsciiLetterOrDigit(c) || c is '-' or '_');

    public string Root { get; } = root;

    public IReadOnlyList<string> List() =>
        Directory.Exists(Root)
            ? [.. Directory.GetFiles(Root, "*.json")
                .Select(Path.GetFileNameWithoutExtension)
                .OfType<string>()
                .Where(IsValidId)
                .Order()]
            : [];

    public EditorProject? Load(string id)
    {
        var path = PathOf(id);
        return File.Exists(path) ? ProjectJson.Read(File.ReadAllText(path)) : null;
    }

    public void Save(EditorProject project)
    {
        Directory.CreateDirectory(Root);
        // Written beside and moved over, so an interrupted save leaves the
        // last good level rather than half of this one.
        var path = PathOf(project.Id);
        var temporary = path + ".writing";
        File.WriteAllText(temporary, ProjectJson.Write(project));
        File.Move(temporary, path, overwrite: true);
    }

    private string PathOf(string id) =>
        IsValidId(id)
            ? Path.Combine(Root, id + ".json")
            : throw new ArgumentException(
                $"\"{id}\" is not a project id: letters, digits, - and _, up to 64", nameof(id));
}
