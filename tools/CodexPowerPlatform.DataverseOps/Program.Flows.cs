using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static readonly string[] FlowColumns =
    {
        "workflowid",
        "workflowidunique",
        "name",
        "uniquename",
        "description",
        "category",
        "type",
        "statecode",
        "statuscode",
        "primaryentity",
        "clientdata",
        "ownerid",
        "createdon",
        "modifiedon",
        "ismanaged",
    };

    private static int RunFlow(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "list";

        return mode switch
        {
            "list" => RunFlowList(client, options),
            "inspect" => RunFlowInspect(client, options),
            "create" => RunFlowCreate(client, options),
            "update" => RunFlowUpdate(client, options),
            _ => throw new InvalidOperationException("Unsupported flow mode. Use --mode list, inspect, create, or update."),
        };
    }

    private static int RunFlowList(ServiceClient client, Dictionary<string, string?> options)
    {
        var solutionUniqueName = ReadOptional(options, "solution-unique-name") ?? ReadOptional(options, "solution-name");
        var includeClientData = options.ContainsKey("include-client-data");
        var query = BuildFlowQuery(solutionUniqueName);
        var flows = RetrieveAll(client, query)
            .Select(flow => BuildFlowPayload(flow, includeClientData))
            .ToList();

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "list",
            solutionUniqueName,
            count = flows.Count,
            flows,
        }, JsonOptions));
        return 0;
    }

    private static int RunFlowInspect(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<FlowInspectSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for flow inspect spec.");

        var flow = ResolveFlow(client, spec.WorkflowId, spec.WorkflowUniqueId, spec.UniqueName, spec.Name, spec.SolutionUniqueName);
        var payload = BuildFlowPayload(flow, spec.IncludeClientData ?? true);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "inspect",
            flow = payload,
        }, JsonOptions));
        return 0;
    }

    private static int RunFlowCreate(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<FlowCreateSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for flow create spec.");

        ValidateRequired(spec.Name, "name");
        var clientData = ResolveClientData(spec.ClientData, "clientData");
        if (string.IsNullOrWhiteSpace(clientData))
        {
            throw new InvalidOperationException("Flow create spec requires a non-empty clientData value.");
        }

        var entity = new Entity("workflow")
        {
            ["category"] = new OptionSetValue(5),
            ["name"] = spec.Name,
            ["type"] = new OptionSetValue(1),
            ["primaryentity"] = string.IsNullOrWhiteSpace(spec.PrimaryEntity) ? "none" : spec.PrimaryEntity!,
            ["clientdata"] = clientData,
        };
        if (!string.IsNullOrWhiteSpace(spec.UniqueName))
        {
            entity["uniquename"] = spec.UniqueName;
        }
        if (!string.IsNullOrWhiteSpace(spec.Description))
        {
            entity["description"] = spec.Description;
        }

        var workflowId = client.Create(entity);
        EnsureFlowInSolution(client, workflowId, spec.SolutionUniqueName);

        if (spec.Activate == true)
        {
            SetFlowState(client, workflowId, true);
        }

        var created = ResolveFlow(client, workflowId.ToString("D"), null, spec.UniqueName, spec.Name, spec.SolutionUniqueName);
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "create",
            solutionUniqueName = spec.SolutionUniqueName,
            flow = BuildFlowPayload(created, includeClientData: true),
        }, JsonOptions));
        return 0;
    }

    private static int RunFlowUpdate(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<FlowUpdateSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for flow update spec.");

        var existing = ResolveFlow(client, spec.WorkflowId, spec.WorkflowUniqueId, spec.UniqueName, spec.Name, spec.SolutionUniqueName);
        var update = new Entity("workflow", existing.Id);

        if (!string.IsNullOrWhiteSpace(spec.NewName))
        {
            update["name"] = spec.NewName;
        }
        if (spec.Description is not null)
        {
            update["description"] = spec.Description;
        }
        if (!string.IsNullOrWhiteSpace(spec.OwnerUserId))
        {
            update["ownerid"] = new EntityReference("systemuser", Guid.Parse(spec.OwnerUserId));
        }
        if (spec.ClientData.HasValue && spec.ClientData.Value.ValueKind != JsonValueKind.Undefined)
        {
            update["clientdata"] = ResolveClientData(spec.ClientData, "clientData");
        }

        if (update.Attributes.Count > 0)
        {
            client.Update(update);
        }

        if (spec.Activate == true && spec.Deactivate == true)
        {
            throw new InvalidOperationException("Flow update spec cannot set both activate and deactivate.");
        }
        if (spec.Activate == true)
        {
            SetFlowState(client, existing.Id, true);
        }
        else if (spec.Deactivate == true)
        {
            SetFlowState(client, existing.Id, false);
        }

        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            EnsureFlowInSolution(client, existing.Id, spec.SolutionUniqueName);
        }

        var refreshed = ResolveFlow(
            client,
            existing.Id.ToString("D"),
            null,
            null,
            null,
            spec.SolutionUniqueName);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "update",
            solutionUniqueName = spec.SolutionUniqueName,
            flow = BuildFlowPayload(refreshed, includeClientData: true),
        }, JsonOptions));
        return 0;
    }

    private static QueryExpression BuildFlowQuery(string? solutionUniqueName)
    {
        var query = new QueryExpression("workflow")
        {
            ColumnSet = new ColumnSet(FlowColumns),
            PageInfo = new PagingInfo
            {
                Count = 5000,
                PageNumber = 1,
            },
        };
        query.Criteria.AddCondition("category", ConditionOperator.Equal, 5);
        query.Criteria.AddCondition("type", ConditionOperator.Equal, 1);

        if (!string.IsNullOrWhiteSpace(solutionUniqueName))
        {
            AddSolutionFilter(query, solutionUniqueName!);
        }

        return query;
    }

    private static List<Entity> RetrieveAll(ServiceClient client, QueryExpression query)
    {
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

        return entities;
    }

    private static Entity ResolveFlow(
        ServiceClient client,
        string? workflowId,
        string? workflowUniqueId,
        string? uniqueName,
        string? name,
        string? solutionUniqueName)
    {
        var query = BuildFlowQuery(solutionUniqueName);
        query.PageInfo = null;
        query.TopCount = 2;

        var selectorCount = 0;
        if (!string.IsNullOrWhiteSpace(workflowId))
        {
            query.Criteria.AddCondition("workflowid", ConditionOperator.Equal, Guid.Parse(workflowId));
            selectorCount++;
        }
        if (!string.IsNullOrWhiteSpace(workflowUniqueId))
        {
            query.Criteria.AddCondition("workflowidunique", ConditionOperator.Equal, Guid.Parse(workflowUniqueId));
            selectorCount++;
        }
        if (!string.IsNullOrWhiteSpace(uniqueName))
        {
            query.Criteria.AddCondition("uniquename", ConditionOperator.Equal, uniqueName);
            selectorCount++;
        }
        if (!string.IsNullOrWhiteSpace(name))
        {
            query.Criteria.AddCondition("name", ConditionOperator.Equal, name);
            selectorCount++;
        }

        if (selectorCount == 0)
        {
            throw new InvalidOperationException(
                "Flow operations require at least one identifier: workflowId, workflowUniqueId, uniqueName, or name.");
        }

        var matches = client.RetrieveMultiple(query).Entities;
        if (matches.Count == 0)
        {
            throw new InvalidOperationException("No matching cloud flow was found for the supplied selector.");
        }
        if (matches.Count > 1)
        {
            throw new InvalidOperationException(
                "More than one cloud flow matched the supplied selector. Refine the selector or include solutionUniqueName.");
        }

        return matches[0];
    }

    private static void AddSolutionFilter(QueryExpression query, string solutionUniqueName)
    {
        var componentLink = query.AddLink("solutioncomponent", "workflowid", "objectid");
        componentLink.LinkCriteria.AddCondition("componenttype", ConditionOperator.Equal, 29);
        var solutionLink = componentLink.AddLink("solution", "solutionid", "solutionid");
        solutionLink.LinkCriteria.AddCondition("uniquename", ConditionOperator.Equal, solutionUniqueName);
    }

    private static void EnsureFlowInSolution(ServiceClient client, Guid workflowId, string? solutionUniqueName)
    {
        if (string.IsNullOrWhiteSpace(solutionUniqueName))
        {
            return;
        }

        var solution = RetrieveSingle(
            client,
            "solution",
            new ColumnSet("uniquename", "friendlyname"),
            new ConditionExpression("uniquename", ConditionOperator.Equal, solutionUniqueName));

        if (IsComponentAlreadyInSolution(client, solution.Id, workflowId, 29))
        {
            return;
        }

        client.Execute(new AddSolutionComponentRequest
        {
            ComponentId = workflowId,
            ComponentType = 29,
            SolutionUniqueName = solutionUniqueName,
            AddRequiredComponents = true,
            DoNotIncludeSubcomponents = false,
        });
    }

    private static void SetFlowState(ServiceClient client, Guid workflowId, bool activate)
    {
        var update = new Entity("workflow", workflowId)
        {
            ["statecode"] = new OptionSetValue(activate ? 1 : 0),
        };
        client.Update(update);
    }

    private static object BuildFlowPayload(Entity flow, bool includeClientData)
    {
        var clientDataText = flow.GetAttributeValue<string>("clientdata");
        var clientDataNode = TryParseJsonNode(clientDataText);
        var connectionReferences = ExtractConnectionReferences(clientDataNode);
        var definitionSummary = BuildDefinitionSummary(clientDataNode);
        var owner = flow.GetAttributeValue<EntityReference>("ownerid");

        return new
        {
            workflowId = flow.Id,
            workflowUniqueId = ReadGuidAttribute(flow, "workflowidunique"),
            uniqueName = flow.GetAttributeValue<string>("uniquename"),
            name = flow.GetAttributeValue<string>("name"),
            description = flow.GetAttributeValue<string>("description"),
            category = flow.GetAttributeValue<OptionSetValue>("category")?.Value,
            categoryLabel = FlowCategoryLabel(flow.GetAttributeValue<OptionSetValue>("category")?.Value),
            type = flow.GetAttributeValue<OptionSetValue>("type")?.Value,
            typeLabel = FlowTypeLabel(flow.GetAttributeValue<OptionSetValue>("type")?.Value),
            stateCode = flow.GetAttributeValue<OptionSetValue>("statecode")?.Value,
            stateLabel = FlowStateLabel(flow.GetAttributeValue<OptionSetValue>("statecode")?.Value),
            primaryEntity = flow.GetAttributeValue<string>("primaryentity"),
            isManaged = ReadBoolAttribute(flow, "ismanaged"),
            ownerId = owner?.Id,
            ownerName = owner?.Name,
            createdOn = flow.GetAttributeValue<DateTime?>("createdon"),
            modifiedOn = flow.GetAttributeValue<DateTime?>("modifiedon"),
            connectionReferenceCount = connectionReferences.Count,
            connectionReferences,
            definitionSummary,
            clientData = includeClientData ? clientDataText : null,
        };
    }

    private static List<object> ExtractConnectionReferences(JsonNode? clientDataNode)
    {
        var connectionReferences = new List<object>();
        if (clientDataNode?["properties"]?["connectionReferences"] is not JsonObject references)
        {
            return connectionReferences;
        }

        foreach (var reference in references)
        {
            var details = reference.Value;
            connectionReferences.Add(new
            {
                alias = reference.Key,
                apiName = details?["api"]?["name"]?.GetValue<string>(),
                connectionName = details?["connection"]?["name"]?.GetValue<string>(),
                connectionReferenceLogicalName = details?["connection"]?["connectionReferenceLogicalName"]?.GetValue<string>(),
                runtimeSource = details?["runtimeSource"]?.GetValue<string>(),
            });
        }

        return connectionReferences;
    }

    private static object BuildDefinitionSummary(JsonNode? clientDataNode)
    {
        var definition = clientDataNode?["properties"]?["definition"];
        var triggers = definition?["triggers"] as JsonObject;
        var actions = definition?["actions"] as JsonObject;
        var parameters = definition?["parameters"] as JsonObject;

        return new
        {
            triggerCount = triggers?.Count ?? 0,
            triggerNames = triggers?.Select(pair => pair.Key).ToArray() ?? Array.Empty<string>(),
            actionCount = actions?.Count ?? 0,
            actionNames = actions?.Select(pair => pair.Key).ToArray() ?? Array.Empty<string>(),
            parameterNames = parameters?.Select(pair => pair.Key).ToArray() ?? Array.Empty<string>(),
        };
    }

    private static JsonNode? TryParseJsonNode(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return null;
        }

        try
        {
            return JsonNode.Parse(text);
        }
        catch
        {
            return null;
        }
    }

    private static string? ResolveClientData(JsonElement? element, string propertyName)
    {
        if (!element.HasValue || element.Value.ValueKind == JsonValueKind.Undefined || element.Value.ValueKind == JsonValueKind.Null)
        {
            return null;
        }

        if (element.Value.ValueKind == JsonValueKind.String)
        {
            var text = element.Value.GetString();
            ValidateRequired(text, propertyName);
            return text;
        }

        return element.Value.GetRawText();
    }

    private static string? ReadOptional(Dictionary<string, string?> options, string key)
    {
        return options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value)
            ? value
            : null;
    }

    private static string ReadSpecText(Dictionary<string, string?> options)
    {
        if (options.TryGetValue("spec-file", out var specFile) && !string.IsNullOrWhiteSpace(specFile))
        {
            return File.ReadAllText(specFile);
        }

        return Require(options, "spec");
    }

    private static Guid? ReadGuidAttribute(Entity entity, string logicalName)
    {
        return entity.Attributes.TryGetValue(logicalName, out var value) && value is Guid guid && guid != Guid.Empty
            ? guid
            : null;
    }

    private static bool? ReadBoolAttribute(Entity entity, string logicalName)
    {
        return entity.Attributes.TryGetValue(logicalName, out var value) && value is bool boolean
            ? boolean
            : null;
    }

    private static string? FlowCategoryLabel(int? category)
    {
        return category switch
        {
            5 => "Modern Flow",
            _ => category?.ToString(),
        };
    }

    private static string? FlowTypeLabel(int? type)
    {
        return type switch
        {
            1 => "Definition",
            _ => type?.ToString(),
        };
    }

    private static string? FlowStateLabel(int? stateCode)
    {
        return stateCode switch
        {
            0 => "Draft",
            1 => "Activated",
            _ => stateCode?.ToString(),
        };
    }

    private sealed class FlowInspectSpec
    {
        public string? WorkflowId { get; init; }

        public string? WorkflowUniqueId { get; init; }

        public string? UniqueName { get; init; }

        public string? Name { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? IncludeClientData { get; init; }
    }

    private sealed class FlowCreateSpec
    {
        public string Name { get; init; } = string.Empty;

        public string? UniqueName { get; init; }

        public string? Description { get; init; }

        public string? PrimaryEntity { get; init; }

        public JsonElement? ClientData { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? Activate { get; init; }
    }

    private sealed class FlowUpdateSpec
    {
        public string? WorkflowId { get; init; }

        public string? WorkflowUniqueId { get; init; }

        public string? UniqueName { get; init; }

        public string? Name { get; init; }

        public string? NewName { get; init; }

        public string? Description { get; init; }

        public string? OwnerUserId { get; init; }

        public JsonElement? ClientData { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? Activate { get; init; }

        public bool? Deactivate { get; init; }
    }
}
