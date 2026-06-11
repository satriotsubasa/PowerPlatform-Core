using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;

namespace CodexPowerPlatform.AuthDialog;

internal static class WhoAmIProcessRunner
{
    public static async Task<AuthAttemptResult> RunAsync(
        string toolDllPath,
        string environmentUrl,
        string username,
        string? tenantId,
        nint parentWindowHandle)
    {
        if (string.IsNullOrWhiteSpace(toolDllPath))
        {
            throw new InvalidOperationException("The Dataverse SDK tool path was not supplied to the dialog.");
        }

        if (!File.Exists(toolDllPath))
        {
            throw new FileNotFoundException("The Dataverse SDK tool DLL was not found.", toolDllPath);
        }

        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = "dotnet",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            },
        };

        process.StartInfo.ArgumentList.Add(toolDllPath);
        process.StartInfo.ArgumentList.Add("whoami");
        process.StartInfo.ArgumentList.Add("--environment-url");
        process.StartInfo.ArgumentList.Add(environmentUrl);
        process.StartInfo.ArgumentList.Add("--username");
        process.StartInfo.ArgumentList.Add(username);
        if (!string.IsNullOrWhiteSpace(tenantId))
        {
            process.StartInfo.ArgumentList.Add("--tenant-id");
            process.StartInfo.ArgumentList.Add(tenantId);
        }
        if (parentWindowHandle != 0)
        {
            process.StartInfo.ArgumentList.Add("--parent-window-handle");
            process.StartInfo.ArgumentList.Add(parentWindowHandle.ToString());
        }
        process.StartInfo.ArgumentList.Add("--auth-flow");
        process.StartInfo.ArgumentList.Add("interactive");
        process.StartInfo.ArgumentList.Add("--force-prompt");
        process.StartInfo.ArgumentList.Add("--verbose");

        process.Start();
        var stdoutTask = process.StandardOutput.ReadToEndAsync();
        var stderrTask = process.StandardError.ReadToEndAsync();
        await process.WaitForExitAsync().ConfigureAwait(true);

        var stdout = await stdoutTask.ConfigureAwait(true);
        var stderr = await stderrTask.ConfigureAwait(true);

        JsonObject? payload = null;
        var trimmed = stdout.Trim();
        if (!string.IsNullOrWhiteSpace(trimmed))
        {
            payload = JsonNode.Parse(trimmed) as JsonObject;
        }

        var success = payload?["success"]?.GetValue<bool>() == true && process.ExitCode == 0;
        var message = success
            ? $"Connected to {payload?["organizationFriendlyName"]?.GetValue<string>() ?? environmentUrl}."
            : payload?["error"]?.GetValue<string>() ?? "Interactive Dataverse sign-in did not succeed.";

        return new AuthAttemptResult(success, message, stderr.Trim(), payload);
    }
}
