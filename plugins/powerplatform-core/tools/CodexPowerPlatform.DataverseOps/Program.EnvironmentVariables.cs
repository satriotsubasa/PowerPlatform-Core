using System.Text.Json;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
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
            _ => throw new InvalidOperationException("Unsupported envvar mode. Use --mode inspect, get-value, or set-value."),
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
}
