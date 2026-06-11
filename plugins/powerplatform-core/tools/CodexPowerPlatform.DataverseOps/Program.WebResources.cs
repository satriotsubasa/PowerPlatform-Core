using System.Security;
using System.Text.Json;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static int RunWebResource(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "sync-file";

        return mode switch
        {
            "sync-file" => RunWebResourceSync(client, options),
            "publish-many" => RunWebResourcePublishMany(client, options),
            _ => throw new InvalidOperationException($"Unsupported webresource mode '{mode}'. Use --mode sync-file or publish-many."),
        };
    }

    private static int RunWebResourceSync(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = Require(options, "spec");
        var spec = JsonSerializer.Deserialize<WebResourceSyncSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for web resource sync spec.");

        ValidateRequired(spec.Name, "name");
        ValidateRequired(spec.FilePath, "filePath");

        var filePath = Path.GetFullPath(spec.FilePath);
        if (!File.Exists(filePath))
        {
            throw new InvalidOperationException($"Web resource file '{filePath}' does not exist.");
        }

        var content = Convert.ToBase64String(File.ReadAllBytes(filePath));
        var typeCode = ResolveWebResourceTypeCode(spec, filePath);

        var existing = RetrieveSingleOrDefault(
            client,
            "webresource",
            new ColumnSet("webresourceid", "name", "displayname", "description", "content", "dependencyxml", "webresourcetype"),
            new ConditionExpression("name", ConditionOperator.Equal, spec.Name));

        var operation = existing is null ? "create" : "update";
        var entity = existing is null
            ? new Entity("webresource")
            : new Entity("webresource", existing.Id);

        entity["name"] = spec.Name;
        entity["content"] = content;
        entity["webresourcetype"] = new OptionSetValue(typeCode);
        if (spec.DisplayName is not null)
        {
            entity["displayname"] = EmptyToNull(spec.DisplayName);
        }

        if (spec.Description is not null)
        {
            entity["description"] = EmptyToNull(spec.Description);
        }

        if (spec.DependencyXml is not null)
        {
            entity["dependencyxml"] = EmptyToNull(spec.DependencyXml);
        }

        var hasChanges = existing is null || WebResourceHasChanges(existing, entity, spec, content, typeCode);
        Guid webResourceId;
        if (existing is null)
        {
            var createRequest = new CreateRequest
            {
                Target = entity,
            };
            if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
            {
                createRequest.Parameters["SolutionUniqueName"] = spec.SolutionUniqueName;
            }

            webResourceId = ((CreateResponse)client.Execute(createRequest)).id;
        }
        else
        {
            webResourceId = existing.Id;
            if (hasChanges)
            {
                var updateRequest = new UpdateRequest
                {
                    Target = entity,
                };
                if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
                {
                    updateRequest.Parameters["SolutionUniqueName"] = spec.SolutionUniqueName;
                }

                client.Execute(updateRequest);
            }
        }

        var published = false;
        if (spec.Publish && (hasChanges || existing is null))
        {
            client.Execute(new PublishXmlRequest
            {
                ParameterXml =
                    $"<importexportxml><webresources><webresource>{SecurityElement.Escape(spec.Name)}</webresource></webresources></importexportxml>",
            });
            published = true;
        }

        var payload = new
        {
            success = true,
            mode = "sync-file",
            operation,
            changed = hasChanges,
            webResourceId = webResourceId,
            name = spec.Name,
            filePath,
            webResourceType = typeCode,
            solutionUniqueName = spec.SolutionUniqueName,
            published,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static int RunWebResourcePublishMany(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = Require(options, "spec");
        var spec = JsonSerializer.Deserialize<WebResourcePublishManySpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for web resource publish-many spec.");
        if (spec.Names.Count == 0)
        {
            throw new InvalidOperationException("publish-many requires at least one web resource name.");
        }

        var escaped = spec.Names
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => $"<webresource>{SecurityElement.Escape(name.Trim())}</webresource>")
            .ToList();
        if (escaped.Count == 0)
        {
            throw new InvalidOperationException("publish-many requires at least one non-empty web resource name.");
        }

        client.Execute(new PublishXmlRequest
        {
            ParameterXml = $"<importexportxml><webresources>{string.Join(string.Empty, escaped)}</webresources></importexportxml>",
        });

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "publish-many",
            names = spec.Names,
            count = escaped.Count,
        }, JsonOptions));
        return 0;
    }

    private static Entity? RetrieveSingleOrDefault(
        ServiceClient client,
        string entityName,
        ColumnSet columns,
        params ConditionExpression[] conditions)
    {
        var query = new QueryExpression(entityName)
        {
            ColumnSet = columns,
            TopCount = 2,
        };
        foreach (var condition in conditions)
        {
            query.Criteria.AddCondition(condition);
        }

        var results = client.RetrieveMultiple(query).Entities;
        if (results.Count == 0)
        {
            return null;
        }

        if (results.Count > 1)
        {
            throw new InvalidOperationException($"More than one {entityName} record matched the requested filters.");
        }

        return results[0];
    }

    private static bool WebResourceHasChanges(Entity existing, Entity desired, WebResourceSyncSpec spec, string content, int typeCode)
    {
        if (!string.Equals(existing.GetAttributeValue<string>("content"), content, StringComparison.Ordinal))
        {
            return true;
        }

        if (existing.GetAttributeValue<OptionSetValue>("webresourcetype")?.Value != typeCode)
        {
            return true;
        }

        if (spec.DisplayName is not null
            && !string.Equals(
                NormalizeOptionalString(existing.GetAttributeValue<string>("displayname")),
                NormalizeOptionalString(spec.DisplayName),
                StringComparison.Ordinal))
        {
            return true;
        }

        if (spec.Description is not null
            && !string.Equals(
                NormalizeOptionalString(existing.GetAttributeValue<string>("description")),
                NormalizeOptionalString(spec.Description),
                StringComparison.Ordinal))
        {
            return true;
        }

        if (spec.DependencyXml is not null
            && !string.Equals(
                NormalizeOptionalString(existing.GetAttributeValue<string>("dependencyxml")),
                NormalizeOptionalString(spec.DependencyXml),
                StringComparison.Ordinal))
        {
            return true;
        }

        return false;
    }

    private static string? NormalizeOptionalString(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    private static int ResolveWebResourceTypeCode(WebResourceSyncSpec spec, string filePath)
    {
        if (spec.WebResourceTypeCode.HasValue)
        {
            return spec.WebResourceTypeCode.Value;
        }

        var rawType = spec.Type;
        if (string.IsNullOrWhiteSpace(rawType))
        {
            rawType = Path.GetExtension(filePath).TrimStart('.');
        }

        return rawType.Trim().ToLowerInvariant() switch
        {
            "html" or "htm" => 1,
            "css" => 2,
            "js" or "javascript" or "script" => 3,
            "xml" => 4,
            "png" => 5,
            "jpg" or "jpeg" => 6,
            "gif" => 7,
            "xap" or "silverlight" => 8,
            "xsl" or "xslt" => 9,
            "ico" => 10,
            "svg" or "vector" => 11,
            "resx" or "string" => 12,
            _ => throw new InvalidOperationException(
                $"Unsupported web resource type '{rawType}'. Supply type as html, css, js, xml, png, jpg, gif, xap, xsl, ico, svg, or resx."),
        };
    }

    private sealed class WebResourceSyncSpec
    {
        public string Name { get; init; } = string.Empty;

        public string FilePath { get; init; } = string.Empty;

        public string? DisplayName { get; init; }

        public string? Description { get; init; }

        public string? Type { get; init; }

        public int? WebResourceTypeCode { get; init; }

        public string? DependencyXml { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool Publish { get; init; }
    }

    private sealed class WebResourcePublishManySpec
    {
        public List<string> Names { get; init; } = new();
    }
}
