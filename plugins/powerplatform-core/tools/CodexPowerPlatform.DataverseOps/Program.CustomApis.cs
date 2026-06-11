using System.Text.Json;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static int RunCustomApi(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "create";

        return mode switch
        {
            "create" => RunCustomApiCreate(client, options),
            _ => throw new InvalidOperationException($"Unsupported customapi mode '{mode}'. Use --mode create."),
        };
    }

    private static int RunCustomApiCreate(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = Require(options, "spec");
        var spec = JsonSerializer.Deserialize<CustomApiCreateSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for custom API create spec.");
        NormalizeCustomApiSpec(spec);

        ValidateRequired(spec.UniqueName, "uniqueName");
        ValidateRequired(spec.Name, "name");
        ValidateRequired(spec.DisplayName, "displayName");
        ValidateRequired(spec.Description, "description");

        var bindingType = ParseCustomApiBindingType(spec.BindingType);
        if (bindingType != 0)
        {
            ValidateRequired(spec.BoundEntityLogicalName, "boundEntityLogicalName");
        }

        ValidateUniqueNames(spec.RequestParameters.Select(item => item.UniqueName), "requestParameters[].uniqueName");
        ValidateUniqueNames(spec.ResponseProperties.Select(item => item.UniqueName), "responseProperties[].uniqueName");

        var existing = RetrieveSingleOrDefault(
            client,
            "customapi",
            new ColumnSet("customapiid", "uniquename"),
            new ConditionExpression("uniquename", ConditionOperator.Equal, spec.UniqueName));
        if (existing is not null)
        {
            throw new InvalidOperationException(
                $"A custom API with unique name '{spec.UniqueName}' already exists in this environment.");
        }

        var pluginTypeId = ResolveCustomApiPluginType(client, spec.PluginType);
        var customApiId = spec.CustomApiId ?? Guid.NewGuid();

        var requests = new OrganizationRequestCollection();
        requests.Add(BuildCustomApiCreateRequest(spec, customApiId, bindingType, pluginTypeId));
        foreach (var parameter in spec.RequestParameters)
        {
            requests.Add(BuildCustomApiRequestParameterCreateRequest(spec, customApiId, parameter));
        }

        foreach (var property in spec.ResponseProperties)
        {
            requests.Add(BuildCustomApiResponsePropertyCreateRequest(spec, customApiId, property));
        }

        client.Execute(new ExecuteTransactionRequest
        {
            Requests = requests,
            ReturnResponses = false,
        });

        var payload = new
        {
            success = true,
            mode = "create",
            customApiId,
            uniqueName = spec.UniqueName,
            name = spec.Name,
            displayName = spec.DisplayName,
            description = spec.Description,
            bindingType = bindingType,
            boundEntityLogicalName = EmptyToNull(spec.BoundEntityLogicalName),
            allowedCustomProcessingStepType = ParseAllowedCustomProcessingStepType(spec.AllowedCustomProcessingStepType),
            isFunction = spec.IsFunction ?? false,
            isPrivate = spec.IsPrivate ?? false,
            workflowSdkStepEnabled = spec.WorkflowSdkStepEnabled ?? false,
            pluginTypeId,
            requestParameterCount = spec.RequestParameters.Count,
            responsePropertyCount = spec.ResponseProperties.Count,
            solutionUniqueName = spec.SolutionUniqueName,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static void NormalizeCustomApiSpec(CustomApiCreateSpec spec)
    {
        spec.Name ??= spec.UniqueName;
        spec.DisplayName ??= spec.Name ?? spec.UniqueName;
        spec.Description ??= spec.DisplayName ?? spec.Name ?? spec.UniqueName;

        foreach (var parameter in spec.RequestParameters)
        {
            parameter.Name ??= parameter.UniqueName;
            parameter.DisplayName ??= parameter.Name ?? parameter.UniqueName;
            parameter.Description ??= parameter.DisplayName ?? parameter.Name ?? parameter.UniqueName;
        }

        foreach (var property in spec.ResponseProperties)
        {
            property.Name ??= property.UniqueName;
            property.DisplayName ??= property.Name ?? property.UniqueName;
            property.Description ??= property.DisplayName ?? property.Name ?? property.UniqueName;
        }
    }

    private static void ValidateUniqueNames(IEnumerable<string?> values, string label)
    {
        var normalized = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var value in values)
        {
            ValidateRequired(value, label);
            if (!normalized.Add(value!))
            {
                throw new InvalidOperationException($"Duplicate value '{value}' detected for {label}.");
            }
        }
    }

    private static CreateRequest BuildCustomApiCreateRequest(
        CustomApiCreateSpec spec,
        Guid customApiId,
        int bindingType,
        Guid? pluginTypeId)
    {
        var entity = new Entity("customapi", customApiId)
        {
            ["uniquename"] = spec.UniqueName,
            ["name"] = spec.Name,
            ["displayname"] = spec.DisplayName,
            ["description"] = spec.Description,
            ["bindingtype"] = new OptionSetValue(bindingType),
            ["allowedcustomprocessingsteptype"] = new OptionSetValue(ParseAllowedCustomProcessingStepType(spec.AllowedCustomProcessingStepType)),
            ["isfunction"] = spec.IsFunction ?? false,
            ["isprivate"] = spec.IsPrivate ?? false,
            ["workflowsdkstepenabled"] = spec.WorkflowSdkStepEnabled ?? false,
        };

        var boundEntityLogicalName = EmptyToNull(spec.BoundEntityLogicalName);
        if (boundEntityLogicalName is not null)
        {
            entity["boundentitylogicalname"] = boundEntityLogicalName;
        }

        var executePrivilegeName = EmptyToNull(spec.ExecutePrivilegeName);
        if (executePrivilegeName is not null)
        {
            entity["executeprivilegename"] = executePrivilegeName;
        }

        if (pluginTypeId.HasValue)
        {
            entity["plugintypeid"] = new EntityReference("plugintype", pluginTypeId.Value);
        }

        var request = new CreateRequest
        {
            Target = entity,
        };
        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            request.Parameters["SolutionUniqueName"] = spec.SolutionUniqueName;
        }

        return request;
    }

    private static CreateRequest BuildCustomApiRequestParameterCreateRequest(
        CustomApiCreateSpec spec,
        Guid customApiId,
        CustomApiParameterSpec parameter)
    {
        ValidateRequired(parameter.UniqueName, "requestParameters[].uniqueName");
        ValidateRequired(parameter.Name, "requestParameters[].name");
        ValidateRequired(parameter.DisplayName, "requestParameters[].displayName");
        ValidateRequired(parameter.Description, "requestParameters[].description");

        var typeCode = ParseCustomApiFieldType(parameter.Type);
        ValidateLogicalEntityNameRequirement(typeCode, parameter.LogicalEntityName, "requestParameters");

        var entity = new Entity("customapirequestparameter", parameter.CustomApiRequestParameterId ?? Guid.NewGuid())
        {
            ["customapiid"] = new EntityReference("customapi", customApiId),
            ["uniquename"] = parameter.UniqueName,
            ["name"] = parameter.Name,
            ["displayname"] = parameter.DisplayName,
            ["description"] = parameter.Description,
            ["type"] = new OptionSetValue(typeCode),
            ["isoptional"] = parameter.IsOptional ?? false,
        };

        var logicalEntityName = EmptyToNull(parameter.LogicalEntityName);
        if (logicalEntityName is not null)
        {
            entity["logicalentityname"] = logicalEntityName;
        }

        var request = new CreateRequest
        {
            Target = entity,
        };
        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            request.Parameters["SolutionUniqueName"] = spec.SolutionUniqueName;
        }

        return request;
    }

    private static CreateRequest BuildCustomApiResponsePropertyCreateRequest(
        CustomApiCreateSpec spec,
        Guid customApiId,
        CustomApiResponsePropertySpec property)
    {
        ValidateRequired(property.UniqueName, "responseProperties[].uniqueName");
        ValidateRequired(property.Name, "responseProperties[].name");
        ValidateRequired(property.DisplayName, "responseProperties[].displayName");
        ValidateRequired(property.Description, "responseProperties[].description");

        var typeCode = ParseCustomApiFieldType(property.Type);
        ValidateLogicalEntityNameRequirement(typeCode, property.LogicalEntityName, "responseProperties");

        var entity = new Entity("customapiresponseproperty", property.CustomApiResponsePropertyId ?? Guid.NewGuid())
        {
            ["customapiid"] = new EntityReference("customapi", customApiId),
            ["uniquename"] = property.UniqueName,
            ["name"] = property.Name,
            ["displayname"] = property.DisplayName,
            ["description"] = property.Description,
            ["type"] = new OptionSetValue(typeCode),
        };

        var logicalEntityName = EmptyToNull(property.LogicalEntityName);
        if (logicalEntityName is not null)
        {
            entity["logicalentityname"] = logicalEntityName;
        }

        var request = new CreateRequest
        {
            Target = entity,
        };
        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            request.Parameters["SolutionUniqueName"] = spec.SolutionUniqueName;
        }

        return request;
    }

    private static void ValidateLogicalEntityNameRequirement(int typeCode, string? logicalEntityName, string label)
    {
        if (typeCode is 3 or 4 or 5 && string.IsNullOrWhiteSpace(logicalEntityName))
        {
            throw new InvalidOperationException(
                $"{label} entries with type Entity, EntityCollection, or EntityReference require logicalEntityName.");
        }
    }

    private static int ParseCustomApiBindingType(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "global" or "unbound" => 0,
            "entity" or "table" => 1,
            "entitycollection" or "tablecollection" => 2,
            _ => throw new InvalidOperationException(
                $"Unsupported bindingType '{rawValue}'. Use global, entity, or entitycollection."),
        };
    }

    private static int ParseAllowedCustomProcessingStepType(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "none" => 0,
            "asynconly" or "async" => 1,
            "syncandasync" or "sync" => 2,
            _ => throw new InvalidOperationException(
                $"Unsupported allowedCustomProcessingStepType '{rawValue}'. Use none, asynconly, or syncandasync."),
        };
    }

    private static int ParseCustomApiFieldType(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "boolean" => 0,
            "datetime" => 1,
            "decimal" => 2,
            "entity" => 3,
            "entitycollection" => 4,
            "entityreference" or "lookup" => 5,
            "float" or "double" => 6,
            "integer" or "int" => 7,
            "money" => 8,
            "picklist" or "choice" => 9,
            "string" => 10,
            "stringarray" => 11,
            "guid" => 12,
            _ => throw new InvalidOperationException(
                $"Unsupported custom API field type '{rawValue}'. Use boolean, datetime, decimal, entity, entitycollection, entityreference, float, integer, money, picklist, string, stringarray, or guid."),
        };
    }

    private static Guid? ResolveCustomApiPluginType(ServiceClient client, CustomApiPluginTypeSpec? pluginTypeSpec)
    {
        if (pluginTypeSpec is null)
        {
            return null;
        }

        if (pluginTypeSpec.PluginTypeId.HasValue)
        {
            return pluginTypeSpec.PluginTypeId.Value;
        }

        if (string.IsNullOrWhiteSpace(pluginTypeSpec.TypeName))
        {
            return null;
        }

        var query = new QueryExpression("plugintype")
        {
            ColumnSet = new ColumnSet("plugintypeid", "typename", "name"),
            TopCount = 2,
        };
        query.Criteria.AddCondition("typename", ConditionOperator.Equal, pluginTypeSpec.TypeName);

        if (!string.IsNullOrWhiteSpace(pluginTypeSpec.AssemblyName))
        {
            var assembly = query.AddLink("pluginassembly", "pluginassemblyid", "pluginassemblyid", JoinOperator.Inner);
            assembly.LinkCriteria.AddCondition("name", ConditionOperator.Equal, pluginTypeSpec.AssemblyName);
        }

        var results = client.RetrieveMultiple(query).Entities;
        if (results.Count == 0)
        {
            throw new InvalidOperationException(
                $"Could not find plug-in type '{pluginTypeSpec.TypeName}'"
                + (string.IsNullOrWhiteSpace(pluginTypeSpec.AssemblyName) ? string.Empty : $" in assembly '{pluginTypeSpec.AssemblyName}'")
                + ".");
        }

        if (results.Count > 1)
        {
            throw new InvalidOperationException(
                $"More than one plug-in type matched '{pluginTypeSpec.TypeName}'. Supply pluginTypeId or narrow the assemblyName.");
        }

        return results[0].Id;
    }

    private sealed class CustomApiCreateSpec
    {
        public Guid? CustomApiId { get; init; }

        public string UniqueName { get; init; } = string.Empty;

        public string? Name { get; set; }

        public string? DisplayName { get; set; }

        public string? Description { get; set; }

        public string? BindingType { get; init; }

        public string? BoundEntityLogicalName { get; init; }

        public string? AllowedCustomProcessingStepType { get; init; }

        public bool? IsFunction { get; init; }

        public bool? IsPrivate { get; init; }

        public bool? WorkflowSdkStepEnabled { get; init; }

        public string? ExecutePrivilegeName { get; init; }

        public string? SolutionUniqueName { get; init; }

        public CustomApiPluginTypeSpec? PluginType { get; init; }

        public List<CustomApiParameterSpec> RequestParameters { get; init; } = new();

        public List<CustomApiResponsePropertySpec> ResponseProperties { get; init; } = new();
    }

    private sealed class CustomApiPluginTypeSpec
    {
        public Guid? PluginTypeId { get; init; }

        public string? TypeName { get; init; }

        public string? AssemblyName { get; init; }
    }

    private sealed class CustomApiParameterSpec
    {
        public Guid? CustomApiRequestParameterId { get; init; }

        public string UniqueName { get; init; } = string.Empty;

        public string? Name { get; set; }

        public string? DisplayName { get; set; }

        public string? Description { get; set; }

        public string Type { get; init; } = string.Empty;

        public bool? IsOptional { get; init; }

        public string? LogicalEntityName { get; init; }
    }

    private sealed class CustomApiResponsePropertySpec
    {
        public Guid? CustomApiResponsePropertyId { get; init; }

        public string UniqueName { get; init; } = string.Empty;

        public string? Name { get; set; }

        public string? DisplayName { get; set; }

        public string? Description { get; set; }

        public string Type { get; init; } = string.Empty;

        public string? LogicalEntityName { get; init; }
    }
}
