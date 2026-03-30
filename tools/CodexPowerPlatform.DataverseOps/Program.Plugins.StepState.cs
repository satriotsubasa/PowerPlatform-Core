using System.Text.Json;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static readonly string[] PluginStepColumns =
    {
        "sdkmessageprocessingstepid",
        "name",
        "stage",
        "mode",
        "rank",
        "filteringattributes",
        "supporteddeployment",
        "invocationsource",
        "asyncautodelete",
        "canusereadonlyconnection",
        "statecode",
        "statuscode",
    };

    private static int RunPluginListSteps(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<PluginStepListSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for plug-in step list spec.");

        var steps = LoadPluginSteps(client, spec);
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "list-steps",
            solutionUniqueName = spec.SolutionUniqueName,
            count = steps.Count,
            steps = steps.Select(BuildPluginStepPayload).ToList(),
        }, JsonOptions));
        return 0;
    }

    private static int RunPluginEnsureStepState(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<PluginStepEnsureStateSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for plug-in step ensure-state spec.");

        if (spec.Steps.Count == 0)
        {
            throw new InvalidOperationException("Plug-in step ensure-state requires at least one step selector.");
        }

        var currentSteps = LoadPluginSteps(client, spec);
        var changed = new List<object>();
        var unchanged = new List<object>();
        var missing = new List<object>();

        foreach (var desired in spec.Steps)
        {
            var desiredState = NormalizePluginStepState(desired.DesiredState)
                ?? throw new InvalidOperationException("Each desired plug-in step state must be Enabled or Disabled.");
            var matches = currentSteps.Where(step => PluginStepMatchesSelector(step, desired)).ToList();
            if (matches.Count == 0)
            {
                if (desired.FailIfMissing != false)
                {
                    throw new InvalidOperationException(
                        $"No plug-in step matched the selector '{DescribePluginStepSelector(desired)}'.");
                }

                missing.Add(new
                {
                    selector = DescribePluginStepSelector(desired),
                    desiredState,
                });
                continue;
            }

            if (matches.Count > 1 && desired.AllowMultipleMatches != true)
            {
                throw new InvalidOperationException(
                    $"More than one plug-in step matched the selector '{DescribePluginStepSelector(desired)}'.");
            }

            foreach (var match in matches)
            {
                var currentState = PluginStepStateLabel(match.GetAttributeValue<OptionSetValue>("statecode")?.Value) ?? "Unknown";
                if (string.Equals(currentState, desiredState, StringComparison.Ordinal))
                {
                    unchanged.Add(new
                    {
                        selector = DescribePluginStepSelector(desired),
                        desiredState,
                        step = BuildPluginStepPayload(match),
                    });
                    continue;
                }

                SetPluginStepState(client, match.Id, string.Equals(desiredState, "Enabled", StringComparison.Ordinal));
                changed.Add(new
                {
                    selector = DescribePluginStepSelector(desired),
                    desiredState,
                    previousState = currentState,
                    stepId = match.Id,
                });
            }
        }

        var refreshed = LoadPluginSteps(client, spec);
        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "ensure-step-state",
            solutionUniqueName = spec.SolutionUniqueName,
            changedCount = changed.Count,
            unchangedCount = unchanged.Count,
            missingCount = missing.Count,
            changed,
            unchanged,
            missing,
            steps = refreshed.Select(BuildPluginStepPayload).ToList(),
        }, JsonOptions));
        return 0;
    }

    private static List<Entity> LoadPluginSteps(ServiceClient client, PluginStepScopeSpec spec)
    {
        var query = new QueryExpression("sdkmessageprocessingstep")
        {
            ColumnSet = new ColumnSet(PluginStepColumns),
            PageInfo = new PagingInfo
            {
                Count = 5000,
                PageNumber = 1,
            },
        };

        var pluginTypeLink = query.AddLink("plugintype", "eventhandler", "plugintypeid", JoinOperator.Inner);
        pluginTypeLink.Columns = new ColumnSet("typename", "name", "pluginassemblyid");
        pluginTypeLink.EntityAlias = "plugintype";

        var assemblyLink = pluginTypeLink.AddLink("pluginassembly", "pluginassemblyid", "pluginassemblyid", JoinOperator.Inner);
        assemblyLink.Columns = new ColumnSet("pluginassemblyid", "name", "packageid");
        assemblyLink.EntityAlias = "pluginassembly";

        var packageLink = assemblyLink.AddLink("pluginpackage", "packageid", "pluginpackageid", JoinOperator.LeftOuter);
        packageLink.Columns = new ColumnSet("pluginpackageid", "uniquename", "name");
        packageLink.EntityAlias = "pluginpackage";

        var messageLink = query.AddLink("sdkmessage", "sdkmessageid", "sdkmessageid", JoinOperator.Inner);
        messageLink.Columns = new ColumnSet("name");
        messageLink.EntityAlias = "sdkmessage";

        var filterLink = query.AddLink("sdkmessagefilter", "sdkmessagefilterid", "sdkmessagefilterid", JoinOperator.LeftOuter);
        filterLink.Columns = new ColumnSet("primaryobjecttypecode");
        filterLink.EntityAlias = "sdkmessagefilter";

        ApplyPluginScopeFilter(spec, assemblyLink, packageLink);
        if (spec.IncludeDisabled == false)
        {
            query.Criteria.AddCondition("statecode", ConditionOperator.Equal, 0);
        }
        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            AddSolutionComponentFilter(query, "sdkmessageprocessingstepid", spec.SolutionUniqueName!, 92);
        }

        return RetrieveAll(client, query);
    }

    private static void ApplyPluginScopeFilter(PluginStepScopeSpec spec, LinkEntity assemblyLink, LinkEntity packageLink)
    {
        if (!string.IsNullOrWhiteSpace(spec.PluginId))
        {
            var pluginId = Guid.Parse(spec.PluginId);
            if (PluginScopeTargetsPackage(spec.PluginType))
            {
                packageLink.LinkCriteria.AddCondition("pluginpackageid", ConditionOperator.Equal, pluginId);
            }
            else
            {
                assemblyLink.LinkCriteria.AddCondition("pluginassemblyid", ConditionOperator.Equal, pluginId);
            }

            return;
        }

        if (!string.IsNullOrWhiteSpace(spec.PackageUniqueName))
        {
            packageLink.LinkCriteria.AddCondition("uniquename", ConditionOperator.Equal, spec.PackageUniqueName);
            return;
        }

        if (!string.IsNullOrWhiteSpace(spec.AssemblyName))
        {
            assemblyLink.LinkCriteria.AddCondition("name", ConditionOperator.Equal, spec.AssemblyName);
            return;
        }

        throw new InvalidOperationException(
            "Plug-in step operations require pluginId plus pluginType, assemblyName, or packageUniqueName.");
    }

    private static bool PluginStepMatchesSelector(Entity step, PluginStepStateTargetSpec selector)
    {
        var selectorId = !string.IsNullOrWhiteSpace(selector.SdkMessageProcessingStepId)
            ? selector.SdkMessageProcessingStepId
            : selector.StepId;
        if (!string.IsNullOrWhiteSpace(selectorId)
            && !string.Equals(step.Id.ToString("D"), selectorId, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        if (!MatchesOptionalString(selector.Name, step.GetAttributeValue<string>("name")))
        {
            return false;
        }

        if (!MatchesOptionalString(selector.PluginTypeName, ReadAliasedString(step, "plugintype.typename")))
        {
            return false;
        }

        if (!MatchesOptionalString(selector.MessageName, ReadAliasedString(step, "sdkmessage.name")))
        {
            return false;
        }

        if (!MatchesOptionalString(selector.PrimaryEntityLogicalName, ReadAliasedString(step, "sdkmessagefilter.primaryobjecttypecode")))
        {
            return false;
        }

        var selectorStage = NormalizePluginStepStage(selector.Stage);
        if (selectorStage is not null
            && !string.Equals(
                selectorStage,
                NormalizePluginStepStage(step.GetAttributeValue<OptionSetValue>("stage")?.Value.ToString()),
                StringComparison.Ordinal))
        {
            return false;
        }

        var selectorMode = NormalizePluginStepMode(selector.Mode);
        if (selectorMode is not null
            && !string.Equals(
                selectorMode,
                NormalizePluginStepMode(step.GetAttributeValue<OptionSetValue>("mode")?.Value.ToString()),
                StringComparison.Ordinal))
        {
            return false;
        }

        return true;
    }

    private static bool MatchesOptionalString(string? expected, string? actual)
    {
        if (string.IsNullOrWhiteSpace(expected))
        {
            return true;
        }

        return string.Equals(expected.Trim(), actual?.Trim(), StringComparison.OrdinalIgnoreCase);
    }

    private static object BuildPluginStepPayload(Entity step)
    {
        var stage = step.GetAttributeValue<OptionSetValue>("stage")?.Value;
        var mode = step.GetAttributeValue<OptionSetValue>("mode")?.Value;
        var supportedDeployment = step.GetAttributeValue<OptionSetValue>("supporteddeployment")?.Value;
        var invocationSource = step.GetAttributeValue<OptionSetValue>("invocationsource")?.Value;
        var stateCode = step.GetAttributeValue<OptionSetValue>("statecode")?.Value;
        var statusCode = step.GetAttributeValue<OptionSetValue>("statuscode")?.Value;
        var filteringAttributes = step.GetAttributeValue<string>("filteringattributes");

        return new
        {
            sdkMessageProcessingStepId = step.Id,
            name = step.GetAttributeValue<string>("name"),
            pluginTypeName = ReadAliasedString(step, "plugintype.typename"),
            pluginTypeDisplayName = ReadAliasedString(step, "plugintype.name"),
            pluginAssemblyId = ReadAliasedGuid(step, "pluginassembly.pluginassemblyid"),
            pluginAssemblyName = ReadAliasedString(step, "pluginassembly.name"),
            pluginPackageId = ReadAliasedGuid(step, "pluginpackage.pluginpackageid"),
            pluginPackageUniqueName = ReadAliasedString(step, "pluginpackage.uniquename"),
            pluginPackageName = ReadAliasedString(step, "pluginpackage.name"),
            messageName = ReadAliasedString(step, "sdkmessage.name"),
            primaryEntityLogicalName = ReadAliasedString(step, "sdkmessagefilter.primaryobjecttypecode"),
            stage,
            stageLabel = PluginStepStageLabel(stage),
            mode,
            modeLabel = PluginStepModeLabel(mode),
            rank = step.Attributes.TryGetValue("rank", out var rankValue) ? rankValue : null,
            filteringAttributes,
            filteringAttributeList = string.IsNullOrWhiteSpace(filteringAttributes)
                ? Array.Empty<string>()
                : filteringAttributes.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries),
            supportedDeployment,
            supportedDeploymentLabel = PluginSupportedDeploymentLabel(supportedDeployment),
            invocationSource,
            invocationSourceLabel = PluginInvocationSourceLabel(invocationSource),
            asyncAutoDelete = ReadBoolAttribute(step, "asyncautodelete"),
            canUseReadOnlyConnection = ReadBoolAttribute(step, "canusereadonlyconnection"),
            stateCode,
            stateLabel = PluginStepStateLabel(stateCode),
            statusCode,
        };
    }

    private static Guid? ReadAliasedGuid(Entity entity, string alias)
    {
        return entity.Attributes.TryGetValue(alias, out var value) && value is AliasedValue aliased && aliased.Value is Guid guid
            ? guid
            : null;
    }

    private static bool PluginScopeTargetsPackage(string? pluginType)
    {
        return pluginType?.Trim().ToLowerInvariant() switch
        {
            "nuget" or "package" => true,
            null or "" or "assembly" => false,
            _ => throw new InvalidOperationException("Plug-in step operations support pluginType Assembly or Nuget."),
        };
    }

    private static void ApplyRequestedPluginStepState(ServiceClient client, Guid stepId, string? desiredState)
    {
        var normalized = NormalizePluginStepState(desiredState) ?? "Enabled";
        if (string.Equals(normalized, "Disabled", StringComparison.Ordinal))
        {
            SetPluginStepState(client, stepId, enabled: false);
        }
    }

    private static void SetPluginStepState(ServiceClient client, Guid stepId, bool enabled)
    {
        client.Execute(new SetStateRequest
        {
            EntityMoniker = new EntityReference("sdkmessageprocessingstep", stepId),
            State = new OptionSetValue(enabled ? 0 : 1),
            Status = new OptionSetValue(enabled ? 1 : 2),
        });
    }

    private static string? NormalizePluginStepState(string? value)
    {
        return value?.Trim().ToLowerInvariant() switch
        {
            null or "" => null,
            "enabled" or "enable" or "active" or "0" => "Enabled",
            "disabled" or "disable" or "inactive" or "1" => "Disabled",
            _ => throw new InvalidOperationException("Plug-in step desiredState must be Enabled or Disabled."),
        };
    }

    private static string? NormalizePluginStepStage(string? value)
    {
        return value?.Trim().ToLowerInvariant().Replace(" ", string.Empty).Replace("-", string.Empty) switch
        {
            null or "" => null,
            "10" or "prevalidation" => "PreValidation",
            "20" or "preoperation" or "pre" => "PreOperation",
            "30" or "mainoperation" or "main" => "MainOperation",
            "40" or "postoperation" or "post" => "PostOperation",
            _ => value,
        };
    }

    private static string? NormalizePluginStepMode(string? value)
    {
        return value?.Trim().ToLowerInvariant().Replace(" ", string.Empty).Replace("-", string.Empty) switch
        {
            null or "" => null,
            "0" or "sync" or "synchronous" => "Synchronous",
            "1" or "async" or "asynchronous" => "Asynchronous",
            _ => value,
        };
    }

    private static string? PluginStepStateLabel(int? stateCode)
    {
        return stateCode switch
        {
            0 => "Enabled",
            1 => "Disabled",
            _ => stateCode?.ToString(),
        };
    }

    private static string? PluginStepStageLabel(int? stage)
    {
        return stage switch
        {
            10 => "PreValidation",
            20 => "PreOperation",
            30 => "MainOperation",
            40 => "PostOperation",
            _ => stage?.ToString(),
        };
    }

    private static string? PluginStepModeLabel(int? mode)
    {
        return mode switch
        {
            0 => "Synchronous",
            1 => "Asynchronous",
            _ => mode?.ToString(),
        };
    }

    private static string? PluginSupportedDeploymentLabel(int? value)
    {
        return value switch
        {
            0 => "ServerOnly",
            1 => "OfflineOnly",
            2 => "Both",
            _ => value?.ToString(),
        };
    }

    private static string? PluginInvocationSourceLabel(int? value)
    {
        return value switch
        {
            0 => "Parent",
            1 => "Child",
            _ => value?.ToString(),
        };
    }

    private static string DescribePluginStepSelector(PluginStepStateTargetSpec selector)
    {
        var parts = new List<string>();
        if (!string.IsNullOrWhiteSpace(selector.Name))
        {
            parts.Add($"name={selector.Name}");
        }
        if (!string.IsNullOrWhiteSpace(selector.PluginTypeName))
        {
            parts.Add($"pluginTypeName={selector.PluginTypeName}");
        }
        if (!string.IsNullOrWhiteSpace(selector.MessageName))
        {
            parts.Add($"messageName={selector.MessageName}");
        }
        if (!string.IsNullOrWhiteSpace(selector.PrimaryEntityLogicalName))
        {
            parts.Add($"primaryEntityLogicalName={selector.PrimaryEntityLogicalName}");
        }
        if (NormalizePluginStepStage(selector.Stage) is { } stage)
        {
            parts.Add($"stage={stage}");
        }
        if (NormalizePluginStepMode(selector.Mode) is { } mode)
        {
            parts.Add($"mode={mode}");
        }
        var selectorId = !string.IsNullOrWhiteSpace(selector.SdkMessageProcessingStepId)
            ? selector.SdkMessageProcessingStepId
            : selector.StepId;
        if (!string.IsNullOrWhiteSpace(selectorId))
        {
            parts.Add($"id={selectorId}");
        }

        return parts.Count == 0 ? "<unknown-step>" : string.Join(", ", parts);
    }

    private class PluginStepScopeSpec
    {
        public string? PluginId { get; init; }

        public string? PluginType { get; init; }

        public string? AssemblyName { get; init; }

        public string? PackageUniqueName { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? IncludeDisabled { get; init; }
    }

    private sealed class PluginStepListSpec : PluginStepScopeSpec
    {
    }

    private sealed class PluginStepEnsureStateSpec : PluginStepScopeSpec
    {
        public List<PluginStepStateTargetSpec> Steps { get; init; } = new();
    }

    private sealed class PluginStepStateTargetSpec
    {
        public string? SdkMessageProcessingStepId { get; init; }

        public string? StepId { get; init; }

        public string? Name { get; init; }

        public string? PluginTypeName { get; init; }

        public string? MessageName { get; init; }

        public string? PrimaryEntityLogicalName { get; init; }

        public string? Stage { get; init; }

        public string? Mode { get; init; }

        public string? DesiredState { get; init; }

        public bool? FailIfMissing { get; init; }

        public bool? AllowMultipleMatches { get; init; }
    }
}
