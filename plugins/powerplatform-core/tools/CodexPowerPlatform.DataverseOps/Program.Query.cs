using System.Text.Json;
using System.Text.Json.Nodes;
using System.Xml.Linq;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private const int DefaultQueryMaxRows = 100;
    private const int DataversePageSizeCap = 5000;

    // row --mode retrieve : read a single record by --id or alternate --key. Read-only.
    private static object ExecuteRetrieve(ServiceClient client, string table, Dictionary<string, string?> options)
    {
        var reference = ResolveRowReference(table, options);
        var columnSet = BuildColumnSet(options);

        try
        {
            var response = (RetrieveResponse)client.Execute(new RetrieveRequest
            {
                Target = reference,
                ColumnSet = columnSet,
            });

            return new
            {
                success = true,
                mode = "retrieve",
                table,
                found = true,
                row = SerializeEntity(response.Entity),
            };
        }
        catch (Exception ex) when (ex.Message.Contains("Does Not Exist", StringComparison.OrdinalIgnoreCase))
        {
            return new
            {
                success = true,
                mode = "retrieve",
                table,
                found = false,
                row = (object?)null,
            };
        }
    }

    // row --mode delete : delete a single record by --id or alternate --key. Mutating: the
    // caller must clear the orchestrator live-mutation preflight before invoking this.
    private static object ExecuteDelete(ServiceClient client, string table, Dictionary<string, string?> options)
    {
        var reference = ResolveRowReference(table, options);
        client.Execute(new DeleteRequest { Target = reference });

        return new
        {
            success = true,
            mode = "delete",
            table,
            id = reference.Id == Guid.Empty ? (Guid?)null : reference.Id,
            key = reference.KeyAttributes.Count > 0
                ? reference.KeyAttributes.ToDictionary(pair => pair.Key, pair => SimplifyValue(pair.Value))
                : null,
            deleted = true,
        };
    }

    // query : list rows for a FetchXML query with bounded paging and total-count reporting.
    // Read-only; no preflight required.
    private static int RunQuery(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var fetchXml = Require(options, "fetchxml");
        var maxRows = ReadPositiveInt(options, "max-rows", DefaultQueryMaxRows);
        var pageSize = Math.Min(
            ReadPositiveInt(options, "page-size", Math.Min(maxRows, DataversePageSizeCap)),
            DataversePageSizeCap);

        var rows = new List<object?>();
        var pageNumber = 1;
        string? pagingCookie = null;
        var moreRecords = false;
        var totalRecordCount = -1;
        var totalRecordCountLimitExceeded = false;

        while (rows.Count < maxRows)
        {
            var thisPageSize = Math.Min(pageSize, maxRows - rows.Count);
            var pagedFetch = FetchXmlPaging.ApplyPage(fetchXml, pageNumber, thisPageSize, pagingCookie);
            var page = client.RetrieveMultiple(new FetchExpression(pagedFetch));

            foreach (var entity in page.Entities)
            {
                rows.Add(SerializeEntity(entity));
                if (rows.Count >= maxRows)
                {
                    break;
                }
            }

            // returntotalrecordcount populates the metadata on the first page.
            if (pageNumber == 1)
            {
                totalRecordCount = page.TotalRecordCount;
                totalRecordCountLimitExceeded = page.TotalRecordCountLimitExceeded;
            }

            moreRecords = page.MoreRecords;
            if (!page.MoreRecords)
            {
                break;
            }

            pagingCookie = page.PagingCookie;
            pageNumber++;
        }

        var tableTotal = options.ContainsKey("exact-total")
            ? TryRetrieveTableTotal(client, fetchXml)
            : null;

        var payload = new
        {
            success = true,
            mode = "query",
            returnedCount = rows.Count,
            moreRecords,
            totalRecordCount = totalRecordCount < 0 ? (int?)null : totalRecordCount,
            totalRecordCountLimitExceeded,
            tableTotalRecordCount = tableTotal,
            rows,
        };

        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static EntityReference ResolveRowReference(string table, Dictionary<string, string?> options)
    {
        if (options.TryGetValue("id", out var rawId) && !string.IsNullOrWhiteSpace(rawId))
        {
            return new EntityReference(table, Guid.Parse(rawId));
        }

        if (options.TryGetValue("key", out var keyText) && !string.IsNullOrWhiteSpace(keyText))
        {
            var keyObject = JsonNode.Parse(keyText)?.AsObject()
                ?? throw new InvalidOperationException("Expected a JSON object for --key.");
            var keys = new KeyAttributeCollection();
            foreach (var pair in keyObject)
            {
                if (pair.Value is null)
                {
                    throw new InvalidOperationException($"Alternate key '{pair.Key}' cannot be null.");
                }

                keys[pair.Key] = ConvertJsonValue(pair.Key, pair.Value);
            }

            return new EntityReference(table, keys);
        }

        throw new InvalidOperationException("retrieve and delete require either --id or --key.");
    }

    private static ColumnSet BuildColumnSet(Dictionary<string, string?> options)
    {
        if (options.ContainsKey("all-columns"))
        {
            return new ColumnSet(true);
        }

        if (options.TryGetValue("columns", out var columns) && !string.IsNullOrWhiteSpace(columns))
        {
            var names = columns.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
            return new ColumnSet(names);
        }

        // Default to every column. Callers that care about payload size should pass --columns.
        return new ColumnSet(true);
    }

    private static object SerializeEntity(Entity record)
    {
        var attributes = record.Attributes.ToDictionary(
            pair => pair.Key,
            pair => SimplifyValue(pair.Value));

        return new
        {
            id = record.Id,
            columns = attributes,
        };
    }

    private static int ReadPositiveInt(Dictionary<string, string?> options, string key, int fallback)
    {
        if (options.TryGetValue(key, out var raw) && int.TryParse(raw, out var value) && value > 0)
        {
            return value;
        }

        return fallback;
    }

    private static object? TryRetrieveTableTotal(ServiceClient client, string fetchXml)
    {
        var entityName = FetchXmlPaging.GetEntityName(fetchXml);
        if (string.IsNullOrWhiteSpace(entityName))
        {
            return null;
        }

        try
        {
            var response = (RetrieveTotalRecordCountResponse)client.Execute(
                new RetrieveTotalRecordCountRequest { EntityNames = new[] { entityName } });
            var count = response.EntityRecordCountCollection[entityName];
            return new
            {
                entity = entityName,
                count,
                note = "Unfiltered table total from RetrieveTotalRecordCount; a snapshot that can be up to ~24h stale and ignores the query filter.",
            };
        }
        catch
        {
            return null;
        }
    }
}

// Pure FetchXML paging helpers, separated so they can be unit-tested without a live connection.
internal static class FetchXmlPaging
{
    // Injects paging (count/page/paging-cookie) and returntotalrecordcount onto the <fetch>
    // root so RetrieveMultiple returns a bounded page plus its total-count metadata. Any
    // existing top is removed because top is incompatible with paging + returntotalrecordcount.
    public static string ApplyPage(string fetchXml, int page, int count, string? pagingCookie)
    {
        var document = XDocument.Parse(fetchXml);
        var fetch = document.Root
            ?? throw new InvalidOperationException("FetchXML is missing its root <fetch> element.");
        if (!string.Equals(fetch.Name.LocalName, "fetch", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Expected a <fetch> root element.");
        }

        fetch.SetAttributeValue("top", null);
        fetch.SetAttributeValue("count", count);
        fetch.SetAttributeValue("page", page);
        fetch.SetAttributeValue("returntotalrecordcount", "true");
        fetch.SetAttributeValue("paging-cookie", string.IsNullOrEmpty(pagingCookie) ? null : pagingCookie);

        return document.ToString(SaveOptions.DisableFormatting);
    }

    public static string? GetEntityName(string fetchXml)
    {
        var document = XDocument.Parse(fetchXml);
        var entity = document.Descendants()
            .FirstOrDefault(element => string.Equals(element.Name.LocalName, "entity", StringComparison.OrdinalIgnoreCase));
        return entity?.Attribute("name")?.Value;
    }
}
