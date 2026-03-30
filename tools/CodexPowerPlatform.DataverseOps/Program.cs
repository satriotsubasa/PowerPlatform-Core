using System.Globalization;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.Identity.Client;
using Microsoft.Identity.Client.Broker;
using Microsoft.Identity.Client.Extensions.Msal;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private const string DefaultAppId = "51f81489-12ee-4a9e-aaae-a2591f45987d";
    private const string DefaultRedirectUri = "app://58145B91-0C36-4500-8554-080854F2AC97";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
    };

    public static int Main(string[] args)
    {
        try
        {
            if (args.Length == 0)
            {
                throw new InvalidOperationException("Expected a command. Supported commands: whoami, row, solution, webresource, customapi, plugin, metadata, flow, securityrole, envvar.");
            }

            var command = args[0].ToLowerInvariant();

            return command switch
            {
                "whoami" => RunWhoAmI(ParseOptions(args.Skip(1).ToArray())),
                "row" => RunRow(ParseOptions(args.Skip(1).ToArray())),
                "solution" => RunSolution(ParseOptions(args.Skip(1).ToArray())),
                "webresource" => RunWebResource(ParseOptions(args.Skip(1).ToArray())),
                "customapi" => RunCustomApi(ParseOptions(args.Skip(1).ToArray())),
                "plugin" => RunPlugin(ParseOptions(args.Skip(1).ToArray())),
                "metadata" => RunMetadataCommand(args.Skip(1).ToArray()),
                "flow" => RunFlow(ParseOptions(args.Skip(1).ToArray())),
                "securityrole" => RunSecurityRole(ParseOptions(args.Skip(1).ToArray())),
                "envvar" => RunEnvironmentVariable(ParseOptions(args.Skip(1).ToArray())),
                _ => throw new InvalidOperationException($"Unknown command '{command}'."),
            };
        }
        catch (Exception ex)
        {
            var payload = new
            {
                success = false,
                error = ex.Message,
            };
            Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
            return 1;
        }
    }

    private static int RunWhoAmI(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var request = new WhoAmIRequest();
        var response = (WhoAmIResponse)client.Execute(request);

        var payload = new
        {
            success = true,
            organizationUrl = client.ConnectedOrgUriActual?.ToString(),
            organizationUniqueName = client.ConnectedOrgUniqueName,
            organizationFriendlyName = client.ConnectedOrgFriendlyName,
            userId = response.UserId,
            businessUnitId = response.BusinessUnitId,
            organizationId = response.OrganizationId,
        };
        Console.WriteLine(JsonSerializer.Serialize(payload, JsonOptions));
        return 0;
    }

    private static int RunRow(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = Require(options, "mode").ToLowerInvariant();
        var table = Require(options, "table");
        var dataText = Require(options, "data");
        var data = JsonNode.Parse(dataText)?.AsObject() ?? throw new InvalidOperationException("Expected a JSON object for --data.");

        var recordId = options.TryGetValue("id", out var rawId) && !string.IsNullOrWhiteSpace(rawId)
            ? Guid.Parse(rawId)
            : (Guid?)null;

        JsonObject? alternateKey = null;
        if (options.TryGetValue("key", out var keyText) && !string.IsNullOrWhiteSpace(keyText))
        {
            alternateKey = JsonNode.Parse(keyText)?.AsObject()
                ?? throw new InvalidOperationException("Expected a JSON object for --key.");
        }

        var entity = new Entity(table);
        ApplyRowIdentity(entity, recordId, alternateKey);
        ApplyAttributes(entity, data);

        var verify = options.ContainsKey("verify");
        var result = mode switch
        {
            "create" => ExecuteCreate(client, entity, data, verify),
            "update" => ExecuteUpdate(client, entity, data, verify),
            "upsert" => ExecuteUpsert(client, entity, data, verify),
            _ => throw new InvalidOperationException($"Unsupported row mode '{mode}'. Use create, update, or upsert."),
        };

        Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions));
        return 0;
    }

    private static int RunMetadataCommand(string[] args)
    {
        if (args.Length == 0)
        {
            throw new InvalidOperationException(
                "Metadata commands require a subcommand. Supported subcommands: create-table, create-field, create-lookup.");
        }

        var subcommand = args[0].ToLowerInvariant();
        var options = ParseOptions(args.Skip(1).ToArray());
        return RunMetadata(subcommand, options);
    }

    private static object ExecuteCreate(ServiceClient client, Entity entity, JsonObject data, bool verify)
    {
        var createdId = client.Create(entity);
        var verification = verify ? RetrieveVerification(client, entity.LogicalName, createdId, data) : null;
        return new
        {
            success = true,
            mode = "create",
            table = entity.LogicalName,
            id = createdId,
            recordCreated = true,
            verification,
        };
    }

    private static object ExecuteUpdate(ServiceClient client, Entity entity, JsonObject data, bool verify)
    {
        if (entity.Id == Guid.Empty && entity.KeyAttributes.Count == 0)
        {
            throw new InvalidOperationException("Update requires either --id or --key.");
        }

        client.Update(entity);
        var verification = verify && entity.Id != Guid.Empty
            ? RetrieveVerification(client, entity.LogicalName, entity.Id, data)
            : null;
        Guid? outputId = entity.Id == Guid.Empty ? null : entity.Id;

        return new
        {
            success = true,
            mode = "update",
            table = entity.LogicalName,
            id = outputId,
            recordCreated = false,
            verification,
        };
    }

    private static object ExecuteUpsert(ServiceClient client, Entity entity, JsonObject data, bool verify)
    {
        if (entity.Id == Guid.Empty && entity.KeyAttributes.Count == 0)
        {
            throw new InvalidOperationException("Upsert requires either --id or --key.");
        }

        var response = (UpsertResponse)client.Execute(new UpsertRequest { Target = entity });
        var targetId = response.Target?.Id ?? entity.Id;
        var verification = verify && targetId != Guid.Empty
            ? RetrieveVerification(client, entity.LogicalName, targetId, data)
            : null;
        Guid? outputId = targetId == Guid.Empty ? null : targetId;

        return new
        {
            success = true,
            mode = "upsert",
            table = entity.LogicalName,
            id = outputId,
            recordCreated = response.RecordCreated,
            verification,
        };
    }

    private static object? RetrieveVerification(ServiceClient client, string table, Guid recordId, JsonObject data)
    {
        var columns = data.Select(item => item.Key).Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
        if (columns.Length == 0)
        {
            return null;
        }

        var record = client.Retrieve(table, recordId, new ColumnSet(columns));
        var attributes = record.Attributes.ToDictionary(
            pair => pair.Key,
            pair => SimplifyValue(pair.Value));

        return new
        {
            id = record.Id,
            columns = attributes,
        };
    }

    private static void ApplyRowIdentity(Entity entity, Guid? recordId, JsonObject? alternateKey)
    {
        if (recordId.HasValue)
        {
            entity.Id = recordId.Value;
        }

        if (alternateKey is null)
        {
            return;
        }

        foreach (var pair in alternateKey)
        {
            if (pair.Value is null)
            {
                throw new InvalidOperationException($"Alternate key '{pair.Key}' cannot be null.");
            }

            entity.KeyAttributes[pair.Key] = ConvertJsonValue(pair.Key, pair.Value);
        }
    }

    private static void ApplyAttributes(Entity entity, JsonObject data)
    {
        foreach (var pair in data)
        {
            if (pair.Value is null)
            {
                entity[pair.Key] = null!;
                continue;
            }

            entity[pair.Key] = ConvertJsonValue(pair.Key, pair.Value);
        }
    }

    private static object ConvertJsonValue(string attributeName, JsonNode node)
    {
        if (node is JsonValue value)
        {
            if (value.TryGetValue<string>(out var stringValue))
            {
                return stringValue;
            }

            if (value.TryGetValue<bool>(out var boolValue))
            {
                return boolValue;
            }

            if (value.TryGetValue<int>(out var intValue))
            {
                return intValue;
            }

            if (value.TryGetValue<long>(out var longValue))
            {
                return longValue;
            }

            if (value.TryGetValue<decimal>(out var decimalValue))
            {
                return decimalValue;
            }

            if (value.TryGetValue<double>(out var doubleValue))
            {
                return doubleValue;
            }
        }

        if (node is not JsonObject obj)
        {
            throw new InvalidOperationException(
                $"Attribute '{attributeName}' uses an unsupported JSON shape. Use a primitive value or a typed object.");
        }

        var type = obj["type"]?.GetValue<string>()?.Trim().ToLowerInvariant()
            ?? throw new InvalidOperationException(
                $"Attribute '{attributeName}' uses an object value but is missing a 'type' property.");

        return type switch
        {
            "lookup" => new EntityReference(
                RequireJsonString(obj, "entity"),
                Guid.Parse(RequireJsonString(obj, "id"))),
            "money" => new Money(RequireJsonDecimal(obj, "value")),
            "choice" => new OptionSetValue(RequireJsonInt(obj, "value")),
            "datetime" => DateTime.Parse(
                RequireJsonString(obj, "value"),
                CultureInfo.InvariantCulture,
                DateTimeStyles.RoundtripKind),
            "guid" => Guid.Parse(RequireJsonString(obj, "value")),
            _ => throw new InvalidOperationException(
                $"Attribute '{attributeName}' uses unsupported typed value '{type}'."),
        };
    }

    private static object? SimplifyValue(object? value)
    {
        return value switch
        {
            null => null,
            Money money => money.Value,
            OptionSetValue option => option.Value,
            EntityReference reference => new
            {
                logicalName = reference.LogicalName,
                id = reference.Id,
                name = reference.Name,
            },
            AliasedValue aliased => SimplifyValue(aliased.Value),
            DateTime dateTime => dateTime.ToString("O", CultureInfo.InvariantCulture),
            Guid guid => guid.ToString(),
            _ => value,
        };
    }

    private static ServiceClient Connect(Dictionary<string, string?> options)
    {
        var environmentUrl = Require(options, "environment-url");
        options.TryGetValue("username", out var username);
        var appId = options.TryGetValue("app-id", out var rawAppId) && !string.IsNullOrWhiteSpace(rawAppId)
            ? rawAppId!
            : DefaultAppId;
        var redirectUri = options.TryGetValue("redirect-uri", out var rawRedirectUri) && !string.IsNullOrWhiteSpace(rawRedirectUri)
            ? rawRedirectUri!
            : DefaultRedirectUri;
        var tenantId = options.TryGetValue("tenant-id", out var rawTenantId) && !string.IsNullOrWhiteSpace(rawTenantId)
            ? rawTenantId!
            : "organizations";
        var authFlow = options.TryGetValue("auth-flow", out var rawAuthFlow) && !string.IsNullOrWhiteSpace(rawAuthFlow)
            ? rawAuthFlow!.Trim().ToLowerInvariant()
            : "auto";
        var forcePrompt = options.ContainsKey("force-prompt");
        var verbose = options.ContainsKey("verbose");
        var parentWindowHandle = options.TryGetValue("parent-window-handle", out var rawParentWindowHandle)
            && !string.IsNullOrWhiteSpace(rawParentWindowHandle)
            ? ParseParentWindowHandle(rawParentWindowHandle!)
            : (nint?)null;

        Log(verbose, $"Connecting to {environmentUrl} with auth flow '{authFlow}'.");
        if (!string.IsNullOrWhiteSpace(username))
        {
            Log(verbose, $"Username hint: {username}");
        }
        Log(verbose, $"ClientId: {appId}");
        Log(verbose, $"RedirectUri: {redirectUri}");
        if (forcePrompt)
        {
            Log(verbose, "Force interactive prompt is enabled.");
        }
        if (parentWindowHandle is not null)
        {
            Log(verbose, $"Parent window handle: 0x{parentWindowHandle.Value.ToInt64():X}");
        }

        if (authFlow is not ("auto" or "interactive" or "devicecode"))
        {
            throw new InvalidOperationException("Supported auth flows are auto, interactive, and devicecode.");
        }

        var publicClient = BuildPublicClientApplication(appId, redirectUri, tenantId);
        Log(verbose, $"Acquiring preflight token with MSAL {authFlow} flow.");
        _ = AcquireAccessTokenAsync(publicClient, environmentUrl, username, authFlow, forcePrompt, verbose, parentWindowHandle).GetAwaiter().GetResult();
        Log(verbose, "Preflight token acquired. Creating ServiceClient with external token provider.");
        var client = new ServiceClient(
            new Uri(environmentUrl),
            instanceUri =>
            {
                Log(verbose, $"ServiceClient requested token for {instanceUri}");
                return AcquireAccessTokenAsync(publicClient, instanceUri, username, authFlow, forcePrompt: false, verbose, parentWindowHandle);
            },
            useUniqueInstance: true,
            logger: null);

        if (!client.IsReady)
        {
            throw new InvalidOperationException(
                $"Failed to connect to Dataverse. {client.LastError ?? client.LastException?.ToString() ?? "Unknown error."}");
        }

        return client;
    }

    private static IPublicClientApplication BuildPublicClientApplication(string appId, string redirectUri, string tenantId)
    {
        var app = PublicClientApplicationBuilder
            .Create(appId)
            .WithAuthority(AzureCloudInstance.AzurePublic, tenantId)
            .WithRedirectUri(redirectUri)
            .WithBroker(new BrokerOptions(BrokerOptions.OperatingSystems.Windows))
            .Build();

        var cacheDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "CodexPowerPlatform",
            "Dataverse");
        Directory.CreateDirectory(cacheDirectory);

        var storageProperties = new StorageCreationPropertiesBuilder("msal_token_cache.bin", cacheDirectory).Build();
        var cacheHelper = MsalCacheHelper.CreateAsync(storageProperties).GetAwaiter().GetResult();
        cacheHelper.RegisterCache(app.UserTokenCache);

        return app;
    }

    private static async Task<string> AcquireAccessTokenAsync(
        IPublicClientApplication publicClient,
        string instanceUri,
        string? username,
        string authFlow,
        bool forcePrompt,
        bool verbose,
        nint? parentWindowHandle)
    {
        var resource = NormalizeResourceUri(instanceUri);
        var scope = $"{resource}/user_impersonation";
        Log(verbose, $"Requesting token for scope {scope}");
        if (authFlow == "interactive" && forcePrompt)
        {
            Log(verbose, "Skipping silent token acquisition because force prompt is enabled.");
            return await AcquireInteractiveTokenAsync(publicClient, scope, username, authFlow, verbose, parentWindowHandle).ConfigureAwait(false);
        }

        var accounts = await publicClient.GetAccountsAsync();
        var preferredAccount = accounts.FirstOrDefault(
                                 account => !string.IsNullOrWhiteSpace(username)
                                            && string.Equals(account.Username, username, StringComparison.OrdinalIgnoreCase))
                             ?? accounts.FirstOrDefault();

        try
        {
            var silent = await publicClient
                .AcquireTokenSilent(new[] { scope }, preferredAccount)
                .ExecuteAsync()
                .ConfigureAwait(false);
            Log(verbose, "MSAL silent token acquisition succeeded.");
            return silent.AccessToken;
        }
        catch (MsalUiRequiredException)
        {
            Log(verbose, "MSAL silent token acquisition requires user interaction.");
            return await AcquireInteractiveTokenAsync(publicClient, scope, username, authFlow, verbose, parentWindowHandle).ConfigureAwait(false);
        }
    }

    private static async Task<string> AcquireInteractiveTokenAsync(
        IPublicClientApplication publicClient,
        string scope,
        string? username,
        string authFlow,
        bool verbose,
        nint? parentWindowHandle)
    {
        if (authFlow == "interactive")
        {
            Log(verbose, "Launching broker-backed interactive sign-in.");
            var interactiveBuilder = publicClient
                .AcquireTokenInteractive(new[] { scope })
                .WithPrompt(Prompt.SelectAccount);
            if (parentWindowHandle is not null && parentWindowHandle.Value != 0)
            {
                interactiveBuilder = interactiveBuilder.WithParentActivityOrWindow(parentWindowHandle.Value);
            }
            if (!string.IsNullOrWhiteSpace(username))
            {
                interactiveBuilder = interactiveBuilder.WithLoginHint(username);
            }

            var interactiveResult = await interactiveBuilder.ExecuteAsync().ConfigureAwait(false);
            Log(verbose, "Interactive token acquisition succeeded.");
            return interactiveResult.AccessToken;
        }

        Log(verbose, "Starting device code sign-in.");
        var deviceCode = await publicClient
            .AcquireTokenWithDeviceCode(
                new[] { scope },
                callback =>
                {
                    Console.Error.WriteLine(callback.Message);
                    return Task.CompletedTask;
                })
            .ExecuteAsync()
            .ConfigureAwait(false);
        Log(verbose, "Device code token acquisition succeeded.");
        return deviceCode.AccessToken;
    }

    private static nint ParseParentWindowHandle(string rawParentWindowHandle)
    {
        if (long.TryParse(rawParentWindowHandle, NumberStyles.Integer, CultureInfo.InvariantCulture, out var decimalHandle))
        {
            return new nint(decimalHandle);
        }

        if (rawParentWindowHandle.StartsWith("0x", StringComparison.OrdinalIgnoreCase)
            && long.TryParse(rawParentWindowHandle[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out var hexHandle))
        {
            return new nint(hexHandle);
        }

        throw new InvalidOperationException(
            $"Invalid parent window handle '{rawParentWindowHandle}'. Expected a decimal or 0x-prefixed hexadecimal integer.");
    }

    private static string NormalizeResourceUri(string instanceUri)
    {
        if (!Uri.TryCreate(instanceUri, UriKind.Absolute, out var uri))
        {
            throw new InvalidOperationException($"Invalid instance URI '{instanceUri}'.");
        }

        return uri.GetLeftPart(UriPartial.Authority).TrimEnd('/');
    }

    private static void Log(bool verbose, string message)
    {
        if (!verbose)
        {
            return;
        }

        Console.Error.WriteLine($"[dataverse-ops] {message}");
    }

    private static string Require(Dictionary<string, string?> options, string key)
    {
        if (options.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value))
        {
            return value!;
        }

        throw new InvalidOperationException($"Missing required option '--{key}'.");
    }

    private static string RequireJsonString(JsonObject obj, string key)
    {
        return obj[key]?.GetValue<string>()
            ?? throw new InvalidOperationException($"Missing required property '{key}'.");
    }

    private static int RequireJsonInt(JsonObject obj, string key)
    {
        return obj[key]?.GetValue<int>()
            ?? throw new InvalidOperationException($"Missing required property '{key}'.");
    }

    private static decimal RequireJsonDecimal(JsonObject obj, string key)
    {
        return obj[key]?.GetValue<decimal>()
            ?? throw new InvalidOperationException($"Missing required property '{key}'.");
    }

    private static Dictionary<string, string?> ParseOptions(string[] args)
    {
        var options = new Dictionary<string, string?>(StringComparer.OrdinalIgnoreCase);
        for (var index = 0; index < args.Length; index++)
        {
            var token = args[index];
            if (!token.StartsWith("--", StringComparison.Ordinal))
            {
                throw new InvalidOperationException($"Unexpected token '{token}'. Options must start with '--'.");
            }

            var name = token[2..];
            if (index + 1 < args.Length && !args[index + 1].StartsWith("--", StringComparison.Ordinal))
            {
                options[name] = args[index + 1];
                index++;
            }
            else
            {
                options[name] = "true";
            }
        }

        return options;
    }
}
