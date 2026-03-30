using System.Reflection;
using System.Text.Json;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static int RunPlugin(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "register-assembly";

        return mode switch
        {
            "register-assembly" => RunPluginRegisterAssembly(client, options),
            "register-package" => RunPluginRegisterPackage(client, options),
            "list-steps" => RunPluginListSteps(client, options),
            "ensure-step-state" => RunPluginEnsureStepState(client, options),
            _ => throw new InvalidOperationException(
                $"Unsupported plugin mode '{mode}'. Use --mode register-assembly, register-package, list-steps, or ensure-step-state."),
        };
    }

    private static int RunPluginRegisterAssembly(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = Require(options, "spec");
        var spec = JsonSerializer.Deserialize<PluginAssemblyRegistrationSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for plug-in assembly registration spec.");

        ValidateRequired(spec.AssemblyPath, "assemblyPath");
        var assemblyPath = Path.GetFullPath(spec.AssemblyPath);
        if (!File.Exists(assemblyPath))
        {
            throw new InvalidOperationException($"Assembly file '{assemblyPath}' does not exist.");
        }

        var assemblyIdentity = AssemblyName.GetAssemblyName(assemblyPath);
        var assemblyName = !string.IsNullOrWhiteSpace(spec.AssemblyName)
            ? spec.AssemblyName.Trim()
            : assemblyIdentity.Name ?? throw new InvalidOperationException("Could not infer the assembly name from the DLL.");
        var version = !string.IsNullOrWhiteSpace(spec.Version)
            ? spec.Version.Trim()
            : assemblyIdentity.Version?.ToString() ?? "1.0.0.0";
        var culture = !string.IsNullOrWhiteSpace(spec.Culture)
            ? spec.Culture.Trim()
            : string.IsNullOrWhiteSpace(assemblyIdentity.CultureName) ? "neutral" : assemblyIdentity.CultureName;
        var publicKeyToken = ToPublicKeyTokenString(assemblyIdentity);
        if (string.IsNullOrWhiteSpace(publicKeyToken))
        {
            throw new InvalidOperationException(
                $"Assembly '{assemblyPath}' is not strong-named. Assembly-based Dataverse plug-in registration requires a signed DLL. " +
                "Use a signed assembly or move to a package-based flow.");
        }

        var existingAssembly = RetrieveSingleOrDefault(
            client,
            "pluginassembly",
            new ColumnSet("pluginassemblyid", "name", "version"),
            new ConditionExpression("name", ConditionOperator.Equal, assemblyName));
        if (existingAssembly is not null)
        {
            throw new InvalidOperationException(
                $"A plug-in assembly named '{assemblyName}' already exists with ID {existingAssembly.Id}. " +
                "Use the update flow instead of first registration.");
        }

        var assemblyEntity = new Entity("pluginassembly")
        {
            ["name"] = assemblyName,
            ["content"] = Convert.ToBase64String(File.ReadAllBytes(assemblyPath)),
            ["culture"] = culture,
            ["publickeytoken"] = publicKeyToken,
            ["version"] = version,
            ["sourcetype"] = new OptionSetValue(ParsePluginAssemblySourceType(spec.SourceType)),
            ["isolationmode"] = new OptionSetValue(ParsePluginAssemblyIsolationMode(spec.IsolationMode)),
        };
        var description = EmptyToNull(spec.Description);
        if (description is not null)
        {
            assemblyEntity["description"] = description;
        }

        var createAssemblyRequest = new CreateRequest
        {
            Target = assemblyEntity,
        };
        ApplySolutionParameter(createAssemblyRequest, spec.SolutionUniqueName);
        var assemblyId = ((CreateResponse)client.Execute(createAssemblyRequest)).id;

        var requiredTypeNames = GetRequiredPluginTypeNames(spec.Steps);
        var pluginTypes = requiredTypeNames.Length == 0
            ? new Dictionary<string, Entity>(StringComparer.Ordinal)
            : WaitForAssemblyPluginTypes(client, assemblyId, requiredTypeNames);
        var createdSteps = CreatePluginSteps(client, spec.SolutionUniqueName, pluginTypes, spec.Steps);

        var payload = new
        {
            success = true,
            mode = "register-assembly",
            assemblyId,
            assemblyName,
            assemblyPath,
            version,
            culture,
            publicKeyToken,
            sourceType = ParsePluginAssemblySourceType(spec.SourceType),
            isolationMode = ParsePluginAssemblyIsolationMode(spec.IsolationMode),
            solutionUniqueName = spec.SolutionUniqueName,
            stepCount = createdSteps.Count,
            steps = createdSteps,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static int RunPluginRegisterPackage(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = Require(options, "spec");
        var spec = JsonSerializer.Deserialize<PluginPackageRegistrationSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for plug-in package registration spec.");

        ValidateRequired(spec.PackagePath, "packagePath");
        ValidateRequired(spec.UniqueName, "uniqueName");
        ValidateRequired(spec.Name, "name");
        ValidateRequired(spec.Version, "version");

        var packagePath = Path.GetFullPath(spec.PackagePath);
        if (!File.Exists(packagePath))
        {
            throw new InvalidOperationException($"Package file '{packagePath}' does not exist.");
        }

        var existingPackage = RetrieveSingleOrDefault(
            client,
            "pluginpackage",
            new ColumnSet("pluginpackageid", "uniquename", "version"),
            new ConditionExpression("uniquename", ConditionOperator.Equal, spec.UniqueName));
        if (existingPackage is not null)
        {
            throw new InvalidOperationException(
                $"A plug-in package with unique name '{spec.UniqueName}' already exists with ID {existingPackage.Id}. " +
                "Use the package update flow instead of first registration.");
        }

        var packageEntity = new Entity("pluginpackage")
        {
            ["name"] = spec.Name,
            ["uniquename"] = spec.UniqueName,
            ["version"] = spec.Version,
            ["content"] = Convert.ToBase64String(File.ReadAllBytes(packagePath)),
        };

        var createPackageRequest = new CreateRequest
        {
            Target = packageEntity,
        };
        ApplySolutionParameter(createPackageRequest, spec.SolutionUniqueName);
        var packageId = ((CreateResponse)client.Execute(createPackageRequest)).id;

        var requiredTypeNames = GetRequiredPluginTypeNames(spec.Steps);
        var pluginTypes = requiredTypeNames.Length == 0
            ? new Dictionary<string, Entity>(StringComparer.Ordinal)
            : WaitForPackagePluginTypes(client, packageId, requiredTypeNames);
        var createdSteps = CreatePluginSteps(client, spec.SolutionUniqueName, pluginTypes, spec.Steps);

        var payload = new
        {
            success = true,
            mode = "register-package",
            pluginPackageId = packageId,
            packagePath,
            uniqueName = spec.UniqueName,
            name = spec.Name,
            version = spec.Version,
            solutionUniqueName = spec.SolutionUniqueName,
            stepCount = createdSteps.Count,
            steps = createdSteps,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static string[] GetRequiredPluginTypeNames(IReadOnlyCollection<PluginStepRegistrationSpec> steps)
    {
        return steps
            .Select(step => step.PluginTypeName)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Distinct(StringComparer.Ordinal)
            .ToArray()!;
    }

    private static List<object> CreatePluginSteps(
        ServiceClient client,
        string? solutionUniqueName,
        IReadOnlyDictionary<string, Entity> pluginTypes,
        IReadOnlyCollection<PluginStepRegistrationSpec> steps)
    {
        var createdSteps = new List<object>();
        foreach (var step in steps)
        {
            ValidateRequired(step.PluginTypeName, "steps[].pluginTypeName");
            ValidateRequired(step.MessageName, "steps[].messageName");

            var pluginType = pluginTypes.TryGetValue(step.PluginTypeName, out var typeEntity)
                ? typeEntity
                : throw new InvalidOperationException(
                    $"Plug-in type '{step.PluginTypeName}' was not found after registration.");
            var message = ResolveSdkMessage(client, step.MessageName);
            var filter = ResolveSdkMessageFilter(client, message.Id, step.PrimaryEntityLogicalName);

            var stage = ParsePluginStage(step.Stage);
            var mode = ParsePluginMode(step.Mode);
            if (mode == 1 && stage != 40)
            {
                throw new InvalidOperationException(
                    $"Async mode is only supported for post-operation steps. Step '{step.PluginTypeName}' uses stage '{step.Stage}'.");
            }

            Guid? secureConfigId = null;
            var secureConfig = EmptyToNull(step.SecureConfig);
            if (secureConfig is not null)
            {
                secureConfigId = client.Create(new Entity("sdkmessageprocessingstepsecureconfig")
                {
                    ["secureconfig"] = secureConfig,
                });
            }

            var stepName = !string.IsNullOrWhiteSpace(step.Name)
                ? step.Name.Trim()
                : BuildPluginStepName(step);
            var stepEntity = new Entity("sdkmessageprocessingstep")
            {
                ["name"] = stepName,
                ["eventhandler"] = pluginType.ToEntityReference(),
                ["sdkmessageid"] = message.ToEntityReference(),
                ["stage"] = new OptionSetValue(stage),
                ["mode"] = new OptionSetValue(mode),
                ["rank"] = step.Rank ?? 1,
                ["supporteddeployment"] = new OptionSetValue(ParsePluginSupportedDeployment(step.SupportedDeployment)),
                ["invocationsource"] = new OptionSetValue(ParsePluginInvocationSource(step.InvocationSource)),
                ["asyncautodelete"] = step.AsyncAutoDelete ?? mode == 1,
            };

            if (filter is not null)
            {
                stepEntity["sdkmessagefilterid"] = filter.ToEntityReference();
            }

            var descriptionValue = EmptyToNull(step.Description);
            if (descriptionValue is not null)
            {
                stepEntity["description"] = descriptionValue;
            }

            var filteringAttributes = NormalizeFilteringAttributes(step.FilteringAttributes);
            if (filteringAttributes is not null)
            {
                stepEntity["filteringattributes"] = filteringAttributes;
            }

            var unsecureConfig = EmptyToNull(step.UnsecureConfig);
            if (unsecureConfig is not null)
            {
                stepEntity["configuration"] = unsecureConfig;
            }

            if (secureConfigId.HasValue)
            {
                stepEntity["sdkmessageprocessingstepsecureconfigid"] =
                    new EntityReference("sdkmessageprocessingstepsecureconfig", secureConfigId.Value);
            }

            if (step.CanUseReadOnlyConnection.HasValue)
            {
                stepEntity["canusereadonlyconnection"] = step.CanUseReadOnlyConnection.Value;
            }

            var stepCreateRequest = new CreateRequest
            {
                Target = stepEntity,
            };
            ApplySolutionParameter(stepCreateRequest, solutionUniqueName);
            var stepId = ((CreateResponse)client.Execute(stepCreateRequest)).id;
            ApplyRequestedPluginStepState(client, stepId, step.DesiredState);
            var persistedStep = client.Retrieve("sdkmessageprocessingstep", stepId, new ColumnSet(PluginStepColumns));

            var createdImages = new List<object>();
            foreach (var image in step.Images)
            {
                ValidateRequired(image.Name, "steps[].images[].name");
                var imageName = image.Name.Trim();
                var entityAlias = !string.IsNullOrWhiteSpace(image.EntityAlias)
                    ? image.EntityAlias.Trim()
                    : imageName;
                var imageEntity = new Entity("sdkmessageprocessingstepimage")
                {
                    ["name"] = imageName,
                    ["entityalias"] = entityAlias,
                    ["imagetype"] = new OptionSetValue(ParsePluginImageType(image.ImageType)),
                    ["messagepropertyname"] = string.IsNullOrWhiteSpace(image.MessagePropertyName)
                        ? "Target"
                        : image.MessagePropertyName.Trim(),
                    ["sdkmessageprocessingstepid"] = new EntityReference("sdkmessageprocessingstep", stepId),
                };

                var imageAttributes = NormalizeFilteringAttributes(image.Attributes);
                if (imageAttributes is not null)
                {
                    imageEntity["attributes"] = imageAttributes;
                }

                var imageDescription = EmptyToNull(image.Description);
                if (imageDescription is not null)
                {
                    imageEntity["description"] = imageDescription;
                }

                var imageCreateRequest = new CreateRequest
                {
                    Target = imageEntity,
                };
                ApplySolutionParameter(imageCreateRequest, solutionUniqueName);
                var imageId = ((CreateResponse)client.Execute(imageCreateRequest)).id;

                createdImages.Add(new
                {
                    sdkMessageProcessingStepImageId = imageId,
                    name = imageName,
                    entityAlias,
                    imageType = ParsePluginImageType(image.ImageType),
                });
            }

            createdSteps.Add(new
            {
                sdkMessageProcessingStepId = stepId,
                name = stepName,
                pluginTypeName = step.PluginTypeName,
                messageName = step.MessageName,
                primaryEntityLogicalName = EmptyToNull(step.PrimaryEntityLogicalName),
                stage,
                stageLabel = PluginStepStageLabel(stage),
                mode,
                modeLabel = PluginStepModeLabel(mode),
                stateCode = persistedStep.GetAttributeValue<OptionSetValue>("statecode")?.Value,
                stateLabel = PluginStepStateLabel(persistedStep.GetAttributeValue<OptionSetValue>("statecode")?.Value),
                statusCode = persistedStep.GetAttributeValue<OptionSetValue>("statuscode")?.Value,
                imageCount = step.Images.Count,
                images = createdImages,
            });
        }

        return createdSteps;
    }

    private static Dictionary<string, Entity> WaitForAssemblyPluginTypes(
        ServiceClient client,
        Guid assemblyId,
        IReadOnlyCollection<string> typeNames)
    {
        return WaitForPluginTypes(
            client,
            typeNames,
            query =>
            {
                query.Criteria.AddCondition("pluginassemblyid", ConditionOperator.Equal, assemblyId);
            },
            "plug-in assembly");
    }

    private static Dictionary<string, Entity> WaitForPackagePluginTypes(
        ServiceClient client,
        Guid packageId,
        IReadOnlyCollection<string> typeNames)
    {
        return WaitForPluginTypes(
            client,
            typeNames,
            query =>
            {
                var assemblyLink = query.AddLink("pluginassembly", "pluginassemblyid", "pluginassemblyid", JoinOperator.Inner);
                assemblyLink.LinkCriteria.AddCondition("packageid", ConditionOperator.Equal, packageId);
            },
            "plug-in package");
    }

    private static Dictionary<string, Entity> WaitForPluginTypes(
        ServiceClient client,
        IReadOnlyCollection<string> typeNames,
        Action<QueryExpression> applyScope,
        string registrationKind)
    {
        var deadline = DateTime.UtcNow.AddSeconds(30);
        while (DateTime.UtcNow <= deadline)
        {
            var query = new QueryExpression("plugintype")
            {
                ColumnSet = new ColumnSet("plugintypeid", "typename", "name", "pluginassemblyid"),
            };
            applyScope(query);
            var results = client.RetrieveMultiple(query).Entities;
            var byTypeName = results
                .Where(entity => !string.IsNullOrWhiteSpace(entity.GetAttributeValue<string>("typename")))
                .ToDictionary(
                    entity => entity.GetAttributeValue<string>("typename"),
                    entity => entity,
                    StringComparer.Ordinal);

            if (typeNames.All(name => byTypeName.ContainsKey(name)))
            {
                return byTypeName;
            }

            Thread.Sleep(1000);
        }

        throw new InvalidOperationException(
            $"The {registrationKind} was created, but Dataverse did not surface all requested plug-in types within the expected time window. " +
            $"Requested types: {string.Join(", ", typeNames)}");
    }

    private static void ApplySolutionParameter(OrganizationRequest request, string? solutionUniqueName)
    {
        if (!string.IsNullOrWhiteSpace(solutionUniqueName))
        {
            request.Parameters["SolutionUniqueName"] = solutionUniqueName;
        }
    }

    private static Entity ResolveSdkMessage(ServiceClient client, string messageName)
    {
        var query = new QueryExpression("sdkmessage")
        {
            ColumnSet = new ColumnSet("sdkmessageid", "name"),
            TopCount = 2,
        };
        query.Criteria.AddCondition("name", ConditionOperator.Equal, messageName);
        query.Criteria.AddCondition("isprivate", ConditionOperator.Equal, false);
        var results = client.RetrieveMultiple(query).Entities;
        return results.Count switch
        {
            0 => throw new InvalidOperationException($"Could not find a public Dataverse message named '{messageName}'."),
            > 1 => throw new InvalidOperationException($"More than one public Dataverse message matched '{messageName}'."),
            _ => results[0],
        };
    }

    private static Entity? ResolveSdkMessageFilter(ServiceClient client, Guid sdkMessageId, string? primaryEntityLogicalName)
    {
        var entityName = EmptyToNull(primaryEntityLogicalName);
        if (entityName is null)
        {
            return null;
        }

        var query = new QueryExpression("sdkmessagefilter")
        {
            ColumnSet = new ColumnSet("sdkmessagefilterid", "primaryobjecttypecode"),
            TopCount = 2,
        };
        query.Criteria.AddCondition("sdkmessageid", ConditionOperator.Equal, sdkMessageId);
        query.Criteria.AddCondition("primaryobjecttypecode", ConditionOperator.Equal, entityName);
        query.Criteria.AddCondition("iscustomprocessingstepallowed", ConditionOperator.Equal, true);
        query.Criteria.AddCondition("isvisible", ConditionOperator.Equal, true);
        var results = client.RetrieveMultiple(query).Entities;
        return results.Count switch
        {
            0 => throw new InvalidOperationException(
                $"Could not find a plug-in eligible sdkmessagefilter for entity '{entityName}'."),
            > 1 => throw new InvalidOperationException(
                $"More than one sdkmessagefilter matched entity '{entityName}'. Narrow the registration spec."),
            _ => results[0],
        };
    }

    private static string BuildPluginStepName(PluginStepRegistrationSpec step)
    {
        var entitySuffix = string.IsNullOrWhiteSpace(step.PrimaryEntityLogicalName)
            ? "global"
            : step.PrimaryEntityLogicalName.Trim();
        return $"{step.MessageName} on {entitySuffix} :: {step.PluginTypeName}";
    }

    private static string? NormalizeFilteringAttributes(List<string>? values)
    {
        if (values is null || values.Count == 0)
        {
            return null;
        }

        var normalized = values
            .Where(value => !string.IsNullOrWhiteSpace(value))
            .Select(value => value.Trim())
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToArray();
        return normalized.Length == 0 ? null : string.Join(",", normalized);
    }

    private static int ParsePluginAssemblySourceType(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "database" => 0,
            "disk" => 1,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in assembly sourceType '{rawValue}'. Use database or a numeric source type."),
        };
    }

    private static int ParsePluginAssemblyIsolationMode(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "sandbox" => 2,
            "none" => 1,
            "external" => 3,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in assembly isolationMode '{rawValue}'. Use sandbox, none, external, or a numeric isolation mode."),
        };
    }

    private static int ParsePluginStage(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "postoperation" or "post" => 40,
            "prevalidation" => 10,
            "preoperation" or "pre" => 20,
            "mainoperation" or "main" => 30,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in stage '{rawValue}'. Use prevalidation, preoperation, postoperation, or a numeric stage."),
        };
    }

    private static int ParsePluginMode(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "sync" or "synchronous" => 0,
            "async" or "asynchronous" => 1,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in mode '{rawValue}'. Use synchronous, asynchronous, or a numeric mode."),
        };
    }

    private static int ParsePluginSupportedDeployment(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "serveronly" or "server" => 0,
            "offlineonly" or "offline" or "clientonly" or "client" => 1,
            "both" => 2,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in supportedDeployment '{rawValue}'. Use serveronly, offlineonly, both, or a numeric value."),
        };
    }

    private static int ParsePluginInvocationSource(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "parent" or "primary" => 0,
            "child" => 1,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in invocationSource '{rawValue}'. Use parent, child, or a numeric value."),
        };
    }

    private static int ParsePluginImageType(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "preimage" or "pre" => 0,
            "postimage" or "post" => 1,
            "both" => 2,
            _ when int.TryParse(rawValue, out var numericValue) => numericValue,
            _ => throw new InvalidOperationException(
                $"Unsupported plug-in imageType '{rawValue}'. Use preimage, postimage, both, or a numeric value."),
        };
    }

    private static string? ToPublicKeyTokenString(AssemblyName assemblyName)
    {
        var token = assemblyName.GetPublicKeyToken();
        if (token is null || token.Length == 0)
        {
            return null;
        }

        return string.Concat(token.Select(value => value.ToString("x2")));
    }

    private sealed class PluginAssemblyRegistrationSpec
    {
        public string AssemblyPath { get; init; } = string.Empty;

        public string? AssemblyName { get; init; }

        public string? Description { get; init; }

        public string? Version { get; init; }

        public string? Culture { get; init; }

        public string? SourceType { get; init; }

        public string? IsolationMode { get; init; }

        public string? SolutionUniqueName { get; init; }

        public List<PluginStepRegistrationSpec> Steps { get; init; } = new();
    }

    private sealed class PluginPackageRegistrationSpec
    {
        public string PackagePath { get; init; } = string.Empty;

        public string UniqueName { get; init; } = string.Empty;

        public string Name { get; init; } = string.Empty;

        public string Version { get; init; } = string.Empty;

        public string? SolutionUniqueName { get; init; }

        public List<PluginStepRegistrationSpec> Steps { get; init; } = new();
    }

    private sealed class PluginStepRegistrationSpec
    {
        public string PluginTypeName { get; init; } = string.Empty;

        public string MessageName { get; init; } = string.Empty;

        public string? PrimaryEntityLogicalName { get; init; }

        public string? Name { get; init; }

        public string? Description { get; init; }

        public string? Stage { get; init; }

        public string? Mode { get; init; }

        public int? Rank { get; init; }

        public string? SupportedDeployment { get; init; }

        public string? InvocationSource { get; init; }

        public List<string>? FilteringAttributes { get; init; }

        public string? UnsecureConfig { get; init; }

        public string? SecureConfig { get; init; }

        public bool? AsyncAutoDelete { get; init; }

        public bool? CanUseReadOnlyConnection { get; init; }

        public string? DesiredState { get; init; }

        public List<PluginStepImageSpec> Images { get; init; } = new();
    }

    private sealed class PluginStepImageSpec
    {
        public string Name { get; init; } = string.Empty;

        public string? EntityAlias { get; init; }

        public string? ImageType { get; init; }

        public string? MessagePropertyName { get; init; }

        public string? Description { get; init; }

        public List<string>? Attributes { get; init; }
    }
}
