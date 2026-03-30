using System.Diagnostics;
using System.Text.RegularExpressions;

namespace CodexPowerPlatform.AuthDialog;

internal static class TargetInputResolver
{
    private static readonly Regex EnvironmentIdPathRegex =
        new(@"/environments/(?<id>[0-9a-fA-F-]{36})", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex SolutionIdPathRegex =
        new(@"/solutions/(?<id>[0-9a-fA-F-]{36})", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex EnvironmentUrlRegex =
        new(@"https://\S+/?", RegexOptions.Compiled | RegexOptions.IgnoreCase);

    public static async Task<TargetResolutionResult> ResolveAsync(string input)
    {
        var trimmed = input.Trim();
        if (string.IsNullOrWhiteSpace(trimmed))
        {
            throw new InvalidOperationException("Enter a target Dataverse org URL or a Power Apps solution URL.");
        }

        if (Guid.TryParse(trimmed, out var environmentGuid))
        {
            var environmentId = environmentGuid.ToString();
            var environmentUrl = await ResolveEnvironmentUrlFromIdAsync(environmentId).ConfigureAwait(true);
            return new TargetResolutionResult(trimmed, environmentUrl, null, environmentId, null);
        }

        if (!Uri.TryCreate(trimmed, UriKind.Absolute, out var uri))
        {
            throw new InvalidOperationException("The target URL is not a valid absolute URL.");
        }

        if (IsDataverseOrgHost(uri.Host))
        {
            return new TargetResolutionResult(trimmed, $"{uri.Scheme}://{uri.Authority}/", null, null, null);
        }

        if (IsPowerAppsHost(uri.Host))
        {
            var match = EnvironmentIdPathRegex.Match(uri.AbsolutePath);
            if (!match.Success)
            {
                throw new InvalidOperationException(
                    "The Power Apps URL does not contain an environment ID. Paste a full environment or solution URL.");
            }

            var environmentId = match.Groups["id"].Value;
            var solutionIdMatch = SolutionIdPathRegex.Match(uri.AbsolutePath);
            var environmentUrl = await ResolveEnvironmentUrlFromIdAsync(environmentId).ConfigureAwait(true);
            return new TargetResolutionResult(
                trimmed,
                environmentUrl,
                trimmed,
                environmentId,
                solutionIdMatch.Success ? solutionIdMatch.Groups["id"].Value : null);
        }

        throw new InvalidOperationException(
            "The target URL must be a Dataverse org URL or a Power Apps environment or solution URL.");
    }

    private static bool IsDataverseOrgHost(string host) =>
        host.Contains(".crm", StringComparison.OrdinalIgnoreCase)
        && host.EndsWith(".dynamics.com", StringComparison.OrdinalIgnoreCase);

    private static bool IsPowerAppsHost(string host) =>
        host.Equals("make.powerapps.com", StringComparison.OrdinalIgnoreCase)
        || host.EndsWith(".powerapps.com", StringComparison.OrdinalIgnoreCase);

    private static async Task<string> ResolveEnvironmentUrlFromIdAsync(string environmentId)
    {
        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = "pac",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            },
        };
        process.StartInfo.ArgumentList.Add("env");
        process.StartInfo.ArgumentList.Add("list");

        process.Start();
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync().ConfigureAwait(true);

        var stdout = await stdoutTask.ConfigureAwait(true);
        var stderr = await stderrTask.ConfigureAwait(true);
        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"Failed to resolve the environment URL through PAC CLI. {stderr.Trim()}".Trim());
        }

        foreach (var line in stdout.Replace("\r\n", "\n", StringComparison.Ordinal).Split('\n'))
        {
            if (!line.Contains(environmentId, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var urlMatch = EnvironmentUrlRegex.Match(line);
            if (urlMatch.Success)
            {
                return urlMatch.Value.Trim();
            }
        }

        throw new InvalidOperationException(
            $"PAC CLI did not return an environment URL for environment ID '{environmentId}'.");
    }
}
