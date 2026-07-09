using System;

/// <summary>
/// Guards against attempts to create computed columns (Power Fx formula / calculated / rollup)
/// headlessly. Per Microsoft, Power Fx formula columns are authored only in the maker portal, and
/// calculated/rollup columns rely on an unsupported hand-authored WWF XAML definition. The supported
/// headless delivery is: author once in the maker portal, then move via solution import. This tool
/// therefore refuses to create them and redirects to that path instead of silently creating a plain
/// (or Invalid) column.
/// </summary>
public static class ComputedColumns
{
    public static void RejectHeadlessCreation(string? sourceType, string? formulaDefinition)
    {
        if (string.IsNullOrWhiteSpace(sourceType) && string.IsNullOrWhiteSpace(formulaDefinition))
        {
            return;
        }

        var kind = string.IsNullOrWhiteSpace(sourceType) ? "computed" : sourceType!.Trim().ToLowerInvariant();
        throw new InvalidOperationException(
            $"Computed columns ({kind}) cannot be created headlessly. Power Fx formula columns are authored " +
            "only in the Power Apps maker portal (make.powerapps.com); calculated and rollup columns rely on " +
            "an unsupported hand-authored XAML definition. Create the column once in the maker portal, add it " +
            "to your unmanaged solution, and deliver it to other environments via solution import " +
            "(deploy_solution.py / pac solution import).");
    }
}
