using System.Text.Json.Nodes;

namespace CodexPowerPlatform.AuthDialog;

internal sealed class DialogOptions
{
    public string? OutputPath { get; init; }

    public string? ToolDllPath { get; init; }

    public string? InitialTargetUrl { get; init; }

    public string? InitialUsername { get; init; }

    public string? InitialTenantId { get; init; }

    public bool AutoValidate { get; init; }

    public static DialogOptions Parse(string[] args)
    {
        string? outputPath = null;
        string? toolDllPath = null;
        string? initialTargetUrl = null;
        string? initialUsername = null;
        string? initialTenantId = null;
        var autoValidate = false;

        for (var index = 0; index < args.Length; index++)
        {
            var token = args[index];
            if (!token.StartsWith("--", StringComparison.Ordinal))
            {
                continue;
            }

            string? value = null;
            if (index + 1 < args.Length && !args[index + 1].StartsWith("--", StringComparison.Ordinal))
            {
                value = args[index + 1];
                index++;
            }

            switch (token)
            {
                case "--output-path":
                    outputPath = value;
                    break;
                case "--tool-dll-path":
                    toolDllPath = value;
                    break;
                case "--initial-target-url":
                    initialTargetUrl = value;
                    break;
                case "--initial-username":
                    initialUsername = value;
                    break;
                case "--initial-tenant-id":
                    initialTenantId = value;
                    break;
                case "--auto-validate":
                    autoValidate = true;
                    break;
            }
        }

        return new DialogOptions
        {
            OutputPath = outputPath,
            ToolDllPath = toolDllPath,
            InitialTargetUrl = initialTargetUrl,
            InitialUsername = initialUsername,
            InitialTenantId = initialTenantId,
            AutoValidate = autoValidate,
        };
    }
}

internal sealed record TargetResolutionResult(
    string TargetInput,
    string EnvironmentUrl,
    string? SolutionUrl,
    string? EnvironmentId,
    string? SolutionId);

internal sealed class AuthDialogPayload
{
    public bool Success { get; init; }

    public bool Cancelled { get; init; }

    public string? Message { get; init; }

    public string? TargetUrlInput { get; init; }

    public string? EnvironmentUrl { get; init; }

    public string? SolutionUrl { get; init; }

    public string? EnvironmentId { get; init; }

    public string? Username { get; init; }

    public string? TenantId { get; init; }

    public string? Diagnostics { get; init; }

    public JsonObject? WhoAmI { get; init; }

    public SelectedSolutionPayload? SelectedSolution { get; init; }
}

internal sealed record AuthAttemptResult(
    bool Success,
    string Message,
    string Diagnostics,
    JsonObject? WhoAmI);

internal sealed class SelectedSolutionPayload
{
    public string SolutionId { get; init; } = string.Empty;

    public string UniqueName { get; init; } = string.Empty;

    public string FriendlyName { get; init; } = string.Empty;

    public string? Version { get; init; }

    public bool IsManaged { get; init; }

    public bool IsPatch { get; init; }

    public string? ParentSolutionId { get; init; }

    public string? ParentSolutionUniqueName { get; init; }
}

internal sealed class SolutionDialogOption
{
    public string SolutionId { get; init; } = string.Empty;

    public string UniqueName { get; init; } = string.Empty;

    public string FriendlyName { get; init; } = string.Empty;

    public string? Version { get; init; }

    public bool IsManaged { get; init; }

    public bool IsPatch { get; init; }

    public string? ParentSolutionId { get; init; }

    public string? ParentSolutionUniqueName { get; init; }

    public string DisplayLabel =>
        $"{FriendlyName} ({UniqueName})"
        + (string.IsNullOrWhiteSpace(Version) ? string.Empty : $"  v{Version}")
        + (IsPatch
            ? $"  Patch of {ParentSolutionUniqueName ?? ParentSolutionId ?? "<unknown>"}"
            : IsManaged
                ? "  Managed"
                : "  Unmanaged");

    public SelectedSolutionPayload ToPayload() =>
        new()
        {
            SolutionId = SolutionId,
            UniqueName = UniqueName,
            FriendlyName = FriendlyName,
            Version = Version,
            IsManaged = IsManaged,
            IsPatch = IsPatch,
            ParentSolutionId = ParentSolutionId,
            ParentSolutionUniqueName = ParentSolutionUniqueName,
        };
}

internal sealed record SolutionListAttemptResult(
    bool Success,
    string Message,
    string Diagnostics,
    IReadOnlyList<SolutionDialogOption> Solutions);
