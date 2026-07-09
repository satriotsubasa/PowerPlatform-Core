using System.Text.Json;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static readonly string[] EnvironmentVariableDefinitionColumns =
    {
        "environmentvariabledefinitionid",
        "schemaname",
        "displayname",
        "description",
        "defaultvalue",
        "valueschema",
        "inputcontrolconfig",
        "secretstore",
        "type",
        "ownerid",
        "createdon",
        "modifiedon",
        "ismanaged",
    };

    private static readonly string[] EnvironmentVariableValueColumns =
    {
        "environmentvariablevalueid",
        "value",
        "environmentvariabledefinitionid",
        "createdon",
        "modifiedon",
    };

    private static int RunEnvironmentVariable(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "inspect";

        return mode switch
        {
            "inspect" => RunEnvironmentVariableInspect(client, options),
            "get-value" => RunEnvironmentVariableGetValue(client, options),
            "set-value" => RunEnvironmentVariableSetValue(client, options),
            "create-definition" => RunEnvironmentVariableCreateDefinition(client, options),
            _ => throw new InvalidOperationException("Unsupported envvar mode. Use --mode inspect, get-value, set-value, or create-definition."),
        };
    }

    private static int RunEnvironmentVariableInspect(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<EnvironmentVariableInspectSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for environment variable inspect spec.");

        var definition = ResolveEnvironmentVariableDefinition(client, spec.DefinitionId, spec.SchemaName, spec.DisplayName);
        var values = LoadEnvironmentVariableValues(client, definition.Id, spec.ValueId);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "inspect",
            environmentVariable = BuildEnvironmentVariablePayload(definition, values),
        }, JsonOptions));
        return 0;
    }

    private static int RunEnvironmentVariableGetValue(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<EnvironmentVariableInspectSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for environment variable get-value spec.");

        var definition = ResolveEnvironmentVariableDefinition(client, spec.DefinitionId, spec.SchemaName, spec.DisplayName);
        var values = LoadEnvironmentVariableValues(client, definition.Id, spec.ValueId);
        var currentValue = values.FirstOrDefault();

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "get-value",
            definitionId = definition.Id,
            schemaName = definition.GetAttributeValue<string>("schemaname"),
            displayName = definition.GetAttributeValue<string>("displayname"),
            valueId = currentValue?.Id,
            value = currentValue?.GetAttributeValue<string>("value"),
            defaultValue = definition.GetAttributeValue<string>("defaultvalue"),
            valueCount = values.Count,
        }, JsonOptions));
        return 0;
    }

    private static int RunEnvironmentVariableSetValue(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<EnvironmentVariableSetValueSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for environment variable set-value spec.");

        if (spec.Value is null)
        {
            throw new InvalidOperationException("Environment variable set-value spec requires a non-null 'value'.");
        }

        var definition = ResolveEnvironmentVariableDefinition(client, spec.DefinitionId, spec.SchemaName, spec.DisplayName);
        var values = LoadEnvironmentVariableValues(client, definition.Id, spec.ValueId);
        Entity? valueRecord = null;
        var recordCreated = false;

        if (!string.IsNullOrWhiteSpace(spec.ValueId))
        {
            valueRecord = values.SingleOrDefault(
                item => string.Equals(item.Id.ToString("D"), spec.ValueId, StringComparison.OrdinalIgnoreCase));
            if (valueRecord is null)
            {
                throw new InvalidOperationException("No environment variable value matched the supplied valueId.");
            }
        }
        else if (values.Count > 1)
        {
            throw new InvalidOperationException(
                "More than one environment variable value record matched the supplied selector. Pass valueId explicitly.");
        }
        else if (values.Count == 1)
        {
            valueRecord = values[0];
        }

        if (valueRecord is null)
        {
            var create = new Entity("environmentvariablevalue")
            {
                ["environmentvariabledefinitionid"] = definition.ToEntityReference(),
                ["value"] = spec.Value,
            };
            var createdId = client.Create(create);
            valueRecord = client.Retrieve("environmentvariablevalue", createdId, new ColumnSet(EnvironmentVariableValueColumns));
            recordCreated = true;
        }
        else
        {
            var update = new Entity("environmentvariablevalue", valueRecord.Id)
            {
                ["value"] = spec.Value,
            };
            client.Update(update);
            valueRecord = client.Retrieve("environmentvariablevalue", valueRecord.Id, new ColumnSet(EnvironmentVariableValueColumns));
        }

        var refreshedValues = LoadEnvironmentVariableValues(client, definition.Id, valueRecord.Id.ToString("D"));
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "set-value",
            recordCreated,
            environmentVariable = BuildEnvironmentVariablePayload(definition, refreshedValues),
        }, JsonOptions));
        return 0;
    }

    private static int RunEnvironmentVariableCreateDefinition(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<EnvironmentVariableDefinitionSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for environment variable definition spec.");

        ValidateRequired(spec.SchemaName, "schemaName");
        ValidateRequired(spec.DisplayName, "displayName");

        var existing = RetrieveSingleOrDefault(
            client,
            "environmentvariabledefinition",
            new ColumnSet("environmentvariabledefinitionid", "schemaname"),
            new ConditionExpression("schemaname", ConditionOperator.Equal, spec.SchemaName));
        if (existing is not null)
        {
            throw new InvalidOperationException(
                $"An environment variable definition with schema name '{spec.SchemaName}' already exists ({existing.Id}). " +
                "Use --mode set-value to change its value instead.");
        }

        // Env-var definitions are solution-aware components, so they must carry the owning
        // solution's publisher prefix. Validate locally with an actionable message (bypass with
        // allowPrefixMismatch).
        var publisherPrefix = spec.AllowPrefixMismatch == true ? null : ResolvePublisherPrefix(client, spec.SolutionUniqueName);
        if (!string.IsNullOrWhiteSpace(publisherPrefix)
            && !spec.SchemaName!.StartsWith(publisherPrefix + "_", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException(
                $"Environment variable schemaName '{spec.SchemaName}' does not start with the publisher prefix " +
                $"'{publisherPrefix}_' of solution '{spec.SolutionUniqueName}'. Use '{publisherPrefix}_...' as the schema " +
                "name or set allowPrefixMismatch=true to bypass this check.");
        }

        var definition = new Entity("environmentvariabledefinition")
        {
            ["schemaname"] = spec.SchemaName,
            ["displayname"] = spec.DisplayName,
            ["type"] = new OptionSetValue(EnvironmentVariableTypes.Parse(spec.Type)),
        };
        if (!string.IsNullOrWhiteSpace(spec.Description))
        {
            definition["description"] = spec.Description;
        }
        if (spec.DefaultValue is not null)
        {
            definition["defaultvalue"] = spec.DefaultValue;
        }

        var createRequest = new CreateRequest { Target = definition };
        ApplySolutionParameter(createRequest, spec.SolutionUniqueName);
        var definitionId = ((CreateResponse)client.Execute(createRequest)).id;

        Entity? initialValue = null;
        var valueCreated = false;
        if (spec.Value is not null)
        {
            var valueEntity = new Entity("environmentvariablevalue")
            {
                ["environmentvariabledefinitionid"] = new EntityReference("environmentvariabledefinition", definitionId),
                ["value"] = spec.Value,
            };
            // The current value is environment-specific and should NOT be packaged into the
            // solution (only the definition and its defaultValue travel between environments), so
            // this create is intentionally unscoped — matching set-value's behavior.
            var valueId = client.Create(valueEntity);
            initialValue = client.Retrieve("environmentvariablevalue", valueId, new ColumnSet(EnvironmentVariableValueColumns));
            valueCreated = true;
        }

        var created = client.Retrieve(
            "environmentvariabledefinition",
            definitionId,
            new ColumnSet(EnvironmentVariableDefinitionColumns));
        var values = initialValue is null ? new List<Entity>() : new List<Entity> { initialValue };
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "create-definition",
            valueCreated,
            environmentVariable = BuildEnvironmentVariablePayload(created, values),
        }, JsonOptions));
        return 0;
    }

    private static Entity ResolveEnvironmentVariableDefinition(
        ServiceClient client,
        string? definitionId,
        string? schemaName,
        string? displayName)
    {
        if (!string.IsNullOrWhiteSpace(definitionId))
        {
            return RetrieveSingle(
                client,
                "environmentvariabledefinition",
                new ColumnSet(EnvironmentVariableDefinitionColumns),
                new ConditionExpression("environmentvariabledefinitionid", ConditionOperator.Equal, Guid.Parse(definitionId)));
        }

        var query = new QueryExpression("environmentvariabledefinition")
        {
            ColumnSet = new ColumnSet(EnvironmentVariableDefinitionColumns),
            TopCount = 2,
        };

        var selectorCount = 0;
        if (!string.IsNullOrWhiteSpace(schemaName))
        {
            query.Criteria.AddCondition("schemaname", ConditionOperator.Equal, schemaName);
            selectorCount++;
        }

        if (!string.IsNullOrWhiteSpace(displayName))
        {
            query.Criteria.AddCondition("displayname", ConditionOperator.Equal, displayName);
            selectorCount++;
        }

        if (selectorCount == 0)
        {
            throw new InvalidOperationException(
                "Environment variable operations require definitionId, schemaName, or displayName.");
        }

        var results = client.RetrieveMultiple(query).Entities;
        if (results.Count == 0)
        {
            throw new InvalidOperationException("No environment variable definition matched the supplied selector.");
        }

        if (results.Count > 1)
        {
            throw new InvalidOperationException(
                "More than one environment variable definition matched the supplied selector. Use definitionId or schemaName explicitly.");
        }

        return results[0];
    }

    private static List<Entity> LoadEnvironmentVariableValues(ServiceClient client, Guid definitionId, string? valueId)
    {
        var query = new QueryExpression("environmentvariablevalue")
        {
            ColumnSet = new ColumnSet(EnvironmentVariableValueColumns),
            TopCount = string.IsNullOrWhiteSpace(valueId) ? 10 : 2,
        };
        query.Criteria.AddCondition("environmentvariabledefinitionid", ConditionOperator.Equal, definitionId);
        if (!string.IsNullOrWhiteSpace(valueId))
        {
            query.Criteria.AddCondition("environmentvariablevalueid", ConditionOperator.Equal, Guid.Parse(valueId));
        }

        return client
            .RetrieveMultiple(query)
            .Entities
            .OrderByDescending(item => item.GetAttributeValue<DateTime?>("modifiedon") ?? DateTime.MinValue)
            .ThenByDescending(item => item.GetAttributeValue<DateTime?>("createdon") ?? DateTime.MinValue)
            .ToList();
    }

    private static object BuildEnvironmentVariablePayload(Entity definition, IReadOnlyList<Entity> values)
    {
        var currentValue = values.FirstOrDefault();
        return new
        {
            definitionId = definition.Id,
            schemaName = definition.GetAttributeValue<string>("schemaname"),
            displayName = definition.GetAttributeValue<string>("displayname"),
            description = definition.GetAttributeValue<string>("description"),
            defaultValue = definition.GetAttributeValue<string>("defaultvalue"),
            valueSchema = definition.GetAttributeValue<string>("valueschema"),
            inputControlConfig = definition.GetAttributeValue<string>("inputcontrolconfig"),
            type = definition.GetAttributeValue<OptionSetValue>("type")?.Value,
            secretStore = definition.GetAttributeValue<OptionSetValue>("secretstore")?.Value,
            isManaged = ReadBoolAttribute(definition, "ismanaged"),
            valueId = currentValue?.Id,
            value = currentValue?.GetAttributeValue<string>("value"),
            effectiveValue = currentValue?.GetAttributeValue<string>("value") ?? definition.GetAttributeValue<string>("defaultvalue"),
            valueCount = values.Count,
            values = values.Select(BuildEnvironmentVariableValuePayload).ToList(),
        };
    }

    private static object BuildEnvironmentVariableValuePayload(Entity value)
    {
        return new
        {
            valueId = value.Id,
            value = value.GetAttributeValue<string>("value"),
            createdOn = value.GetAttributeValue<DateTime?>("createdon"),
            modifiedOn = value.GetAttributeValue<DateTime?>("modifiedon"),
        };
    }

    private sealed class EnvironmentVariableInspectSpec
    {
        public string? DefinitionId { get; init; }

        public string? SchemaName { get; init; }

        public string? DisplayName { get; init; }

        public string? ValueId { get; init; }
    }

    private sealed class EnvironmentVariableSetValueSpec
    {
        public string? DefinitionId { get; init; }

        public string? SchemaName { get; init; }

        public string? DisplayName { get; init; }

        public string? ValueId { get; init; }

        public string? Value { get; init; }
    }

    private sealed class EnvironmentVariableDefinitionSpec
    {
        public string? SchemaName { get; init; }

        public string? DisplayName { get; init; }

        public string? Description { get; init; }

        // string | number | boolean | json | datasource | secret (or a raw option-set value).
        public string? Type { get; init; }

        public string? DefaultValue { get; init; }

        // Optional initial current value to create alongside the definition.
        public string? Value { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? AllowPrefixMismatch { get; init; }
    }
}

/// <summary>Maps friendly environment-variable type names to Dataverse option-set values.</summary>
public static class EnvironmentVariableTypes
{
    public static int Parse(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "string" or "text" => 100000000,
            "number" or "int" or "integer" or "decimal" or "double" => 100000001,
            "boolean" or "bool" or "yesno" or "twooptions" => 100000002,
            "json" => 100000003,
            "datasource" or "data-source" => 100000004,
            "secret" => 100000005,
            _ => int.TryParse(rawValue, out var numeric)
                ? numeric
                : throw new InvalidOperationException(
                    $"Unsupported environment variable type '{rawValue}'. Use string, number, boolean, json, datasource, or secret."),
        };
    }
}
