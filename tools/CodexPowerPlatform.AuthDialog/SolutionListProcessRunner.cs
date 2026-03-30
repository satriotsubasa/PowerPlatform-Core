using System.Diagnostics;
using System.IO;
using System.Text.Json.Nodes;

namespace CodexPowerPlatform.AuthDialog;

internal static class SolutionListProcessRunner
{
    public static async Task<SolutionListAttemptResult> RunAsync(
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
        process.StartInfo.ArgumentList.Add("solution");
        process.StartInfo.ArgumentList.Add("--mode");
        process.StartInfo.ArgumentList.Add("list");
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
        if (!success)
        {
            var message = payload?["error"]?.GetValue<string>() ?? "Solution lookup did not succeed.";
            return new SolutionListAttemptResult(false, message, stderr.Trim(), Array.Empty<SolutionDialogOption>());
        }

        var solutions = payload?["solutions"]?.AsArray()
            .Select(node => node?.AsObject())
            .Where(node => node is not null)
            .Select(node => new SolutionDialogOption
            {
                SolutionId = ReadString(node!, "solutionId", "SolutionId") ?? string.Empty,
                UniqueName = ReadString(node!, "uniqueName", "UniqueName") ?? string.Empty,
                FriendlyName = ReadString(node!, "friendlyName", "FriendlyName") ?? string.Empty,
                Version = ReadString(node!, "version", "Version"),
                IsManaged = ReadBool(node!, "isManaged", "IsManaged"),
                IsPatch = ReadBool(node!, "isPatch", "IsPatch"),
                ParentSolutionId = ReadString(node!, "parentSolutionId", "ParentSolutionId"),
                ParentSolutionUniqueName = ReadString(node!, "parentSolutionUniqueName", "ParentSolutionUniqueName"),
            })
            .Where(option => !string.IsNullOrWhiteSpace(option.SolutionId))
            .ToList()
            ?? new List<SolutionDialogOption>();

        var messageText = solutions.Count == 0
            ? "Connected, but no selectable solutions were returned."
            : $"Connected and loaded {solutions.Count} selectable solution(s).";
        return new SolutionListAttemptResult(true, messageText, stderr.Trim(), solutions);
    }

    private static string? ReadString(JsonObject node, string camelCase, string pascalCase)
    {
        return node[camelCase]?.GetValue<string>() ?? node[pascalCase]?.GetValue<string>();
    }

    private static bool ReadBool(JsonObject node, string camelCase, string pascalCase)
    {
        return node[camelCase]?.GetValue<bool>() == true || node[pascalCase]?.GetValue<bool>() == true;
    }
}
