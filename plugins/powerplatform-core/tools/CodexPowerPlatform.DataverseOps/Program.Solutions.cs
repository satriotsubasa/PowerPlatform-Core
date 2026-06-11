using System.Text.Json;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static int RunSolution(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "list";

        return mode switch
        {
            "list" => RunSolutionList(client, options),
            "add-components" => RunSolutionAddComponents(client, options),
            _ => throw new InvalidOperationException($"Unsupported solution mode '{mode}'. Use --mode list or --mode add-components."),
        };
    }

    private static int RunSolutionList(ServiceClient client, Dictionary<string, string?> options)
    {
        var includeManaged = options.ContainsKey("include-managed");
        var includeSystem = options.ContainsKey("include-system");

        var query = new QueryExpression("solution")
        {
            ColumnSet = new ColumnSet("friendlyname", "uniquename", "version", "ismanaged", "parentsolutionid"),
            PageInfo = new PagingInfo
            {
                Count = 5000,
                PageNumber = 1,
            },
        };

        var entities = new List<Entity>();
        while (true)
        {
            var page = client.RetrieveMultiple(query);
            entities.AddRange(page.Entities);
            if (!page.MoreRecords)
            {
                break;
            }

            query.PageInfo.PageNumber++;
            query.PageInfo.PagingCookie = page.PagingCookie;
        }

        var uniqueNameById = entities
            .Where(entity => entity.Id != Guid.Empty)
            .Where(entity => !string.IsNullOrWhiteSpace(entity.GetAttributeValue<string>("uniquename")))
            .ToDictionary(
                entity => entity.Id,
                entity => entity.GetAttributeValue<string>("uniquename")!,
                comparer: EqualityComparer<Guid>.Default);

        var summaries = entities
            .Select(entity => ToSolutionSummary(entity, uniqueNameById))
            .Where(summary => ShouldIncludeSolution(summary, includeManaged, includeSystem))
            .OrderBy(summary => summary.IsManaged)
            .ThenBy(summary => summary.IsPatch ? 0 : 1)
            .ThenBy(summary => summary.FriendlyName, StringComparer.OrdinalIgnoreCase)
            .ThenBy(summary => summary.UniqueName, StringComparer.OrdinalIgnoreCase)
            .ToList();

        var payload = new
        {
            success = true,
            count = summaries.Count,
            solutions = summaries,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static SolutionSummary ToSolutionSummary(Entity entity, IReadOnlyDictionary<Guid, string> uniqueNameById)
    {
        var parentReference = entity.GetAttributeValue<EntityReference>("parentsolutionid");
        var parentSolutionId = parentReference?.Id == Guid.Empty ? null : parentReference?.Id;
        uniqueNameById.TryGetValue(parentSolutionId ?? Guid.Empty, out var parentUniqueName);

        var uniqueName = entity.GetAttributeValue<string>("uniquename") ?? entity.Id.ToString("D");
        var friendlyName = entity.GetAttributeValue<string>("friendlyname") ?? uniqueName;
        return new SolutionSummary
        {
            SolutionId = entity.Id,
            UniqueName = uniqueName,
            FriendlyName = friendlyName,
            Version = entity.GetAttributeValue<string>("version"),
            IsManaged = entity.GetAttributeValue<bool>("ismanaged"),
            ParentSolutionId = parentSolutionId,
            ParentSolutionUniqueName = parentUniqueName ?? parentReference?.Name,
            IsPatch = parentSolutionId.HasValue,
        };
    }

    private static bool ShouldIncludeSolution(SolutionSummary summary, bool includeManaged, bool includeSystem)
    {
        if (!includeManaged && summary.IsManaged)
        {
            return false;
        }

        if (includeSystem)
        {
            return true;
        }

        return !IsSystemSolution(summary);
    }

    private static bool IsSystemSolution(SolutionSummary summary)
    {
        return string.Equals(summary.UniqueName, "Active", StringComparison.OrdinalIgnoreCase)
               || string.Equals(summary.UniqueName, "Basic", StringComparison.OrdinalIgnoreCase)
               || string.Equals(summary.FriendlyName, "Active", StringComparison.OrdinalIgnoreCase)
               || string.Equals(summary.FriendlyName, "Active Solution", StringComparison.OrdinalIgnoreCase)
               || string.Equals(summary.FriendlyName, "Default Solution", StringComparison.OrdinalIgnoreCase)
               || string.Equals(summary.FriendlyName, "Basic Solution", StringComparison.OrdinalIgnoreCase)
               || string.Equals(summary.FriendlyName, "Common Data Services Default Solution", StringComparison.OrdinalIgnoreCase);
    }

    private sealed class SolutionSummary
    {
        public Guid SolutionId { get; init; }

        public string UniqueName { get; init; } = string.Empty;

        public string FriendlyName { get; init; } = string.Empty;

        public string? Version { get; init; }

        public bool IsManaged { get; init; }

        public bool IsPatch { get; init; }

        public Guid? ParentSolutionId { get; init; }

        public string? ParentSolutionUniqueName { get; init; }
    }
}
