using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;

namespace CodexPowerPlatform.AuthDialog;

public partial class MainWindow : Window
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private readonly DialogOptions _options;
    private AuthDialogPayload? _cachedPayload;
    private AuthDialogPayload? _currentPayload;
    private TargetResolutionResult? _currentResolution;
    private AuthAttemptResult? _currentAuthResult;
    private bool _completed;
    private bool _isValidating;

    public MainWindow()
    {
        InitializeComponent();
        _options = DialogOptions.Parse(Environment.GetCommandLineArgs().Skip(1).ToArray());
        Loaded += MainWindow_Loaded;
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        _cachedPayload = LoadCachedPayload();

        TargetUrlTextBox.Text = _options.InitialTargetUrl ?? _cachedPayload?.TargetUrlInput ?? string.Empty;
        UsernameTextBox.Text = _options.InitialUsername ?? _cachedPayload?.Username ?? string.Empty;
        TenantIdTextBox.Text = _options.InitialTenantId ?? _cachedPayload?.TenantId ?? string.Empty;
        ResolvedEnvironmentUrlTextBox.Text = _cachedPayload?.EnvironmentUrl ?? string.Empty;
        DiagnosticsTextBox.Text = _cachedPayload?.Diagnostics ?? "No validation has been run in this dialog yet.";
        SolutionSelectionPanel.Visibility = Visibility.Collapsed;
        SolutionSelectionStatusTextBlock.Text = "Validate the connection to load solutions.";

        SetStatus(
            badgeText: "Ready",
            badgeBackground: (Brush)FindResource("InfoBrush"),
            badgeForeground: (Brush)FindResource("InfoTextBrush"),
            title: "Start by validating the connection.",
            body: "The dialog will resolve the target environment, force an interactive Dataverse sign-in, load selectable solutions, and only then release the live context.");

        if (_options.AutoValidate)
        {
            await ValidateAsync().ConfigureAwait(true);
        }
    }

    private async void ValidateButton_Click(object sender, RoutedEventArgs e)
    {
        await ValidateAsync().ConfigureAwait(true);
    }

    private async Task ValidateAsync()
    {
        if (_isValidating)
        {
            return;
        }

        var targetUrl = TargetUrlTextBox.Text.Trim();
        var username = UsernameTextBox.Text.Trim();
        var tenantId = TenantIdTextBox.Text.Trim();

        if (string.IsNullOrWhiteSpace(username))
        {
            SetFailure("Enter a username before starting the interactive sign-in.");
            return;
        }

        ResetSolutionSelection();
        SetBusy(true);
        try
        {
            var parentWindowHandle = new WindowInteropHelper(this).Handle;

            SetStatus(
                badgeText: "Resolving",
                badgeBackground: (Brush)FindResource("InfoBrush"),
                badgeForeground: (Brush)FindResource("InfoTextBrush"),
                title: "Resolving the target environment.",
                body: "The dialog is resolving the Dataverse org URL, forcing an interactive sign-in, and then loading selectable solutions.");

            var resolution = await TargetInputResolver.ResolveAsync(targetUrl).ConfigureAwait(true);
            ResolvedEnvironmentUrlTextBox.Text = resolution.EnvironmentUrl;

            var authResult = await WhoAmIProcessRunner
                .RunAsync(_options.ToolDllPath ?? string.Empty, resolution.EnvironmentUrl, username, tenantId, parentWindowHandle)
                .ConfigureAwait(true);
            if (!authResult.Success)
            {
                DiagnosticsTextBox.Text = BuildDiagnosticsText(resolution, authResult, null);
                _currentPayload = new AuthDialogPayload
                {
                    Success = false,
                    Cancelled = false,
                    Message = authResult.Message,
                    TargetUrlInput = resolution.TargetInput,
                    EnvironmentUrl = resolution.EnvironmentUrl,
                    SolutionUrl = resolution.SolutionUrl,
                    EnvironmentId = resolution.EnvironmentId,
                    Username = username,
                    TenantId = string.IsNullOrWhiteSpace(tenantId) ? null : tenantId,
                    Diagnostics = DiagnosticsTextBox.Text,
                    WhoAmI = authResult.WhoAmI,
                };
                UseContextButton.IsEnabled = false;
                SetFailure(authResult.Message);
                return;
            }

            var solutionResult = await SolutionListProcessRunner
                .RunAsync(_options.ToolDllPath ?? string.Empty, resolution.EnvironmentUrl, username, tenantId, parentWindowHandle)
                .ConfigureAwait(true);
            DiagnosticsTextBox.Text = BuildDiagnosticsText(resolution, authResult, null, solutionResult);
            if (!solutionResult.Success)
            {
                _currentPayload = new AuthDialogPayload
                {
                    Success = false,
                    Cancelled = false,
                    Message = solutionResult.Message,
                    TargetUrlInput = resolution.TargetInput,
                    EnvironmentUrl = resolution.EnvironmentUrl,
                    SolutionUrl = resolution.SolutionUrl,
                    EnvironmentId = resolution.EnvironmentId,
                    Username = username,
                    TenantId = string.IsNullOrWhiteSpace(tenantId) ? null : tenantId,
                    Diagnostics = DiagnosticsTextBox.Text,
                    WhoAmI = authResult.WhoAmI,
                };
                UseContextButton.IsEnabled = false;
                SetFailure(solutionResult.Message);
                return;
            }

            if (solutionResult.Solutions.Count == 0)
            {
                _currentPayload = new AuthDialogPayload
                {
                    Success = false,
                    Cancelled = false,
                    Message = "Connected to Dataverse, but no selectable solutions were returned.",
                    TargetUrlInput = resolution.TargetInput,
                    EnvironmentUrl = resolution.EnvironmentUrl,
                    SolutionUrl = resolution.SolutionUrl,
                    EnvironmentId = resolution.EnvironmentId,
                    Username = username,
                    TenantId = string.IsNullOrWhiteSpace(tenantId) ? null : tenantId,
                    Diagnostics = DiagnosticsTextBox.Text,
                    WhoAmI = authResult.WhoAmI,
                };
                UseContextButton.IsEnabled = false;
                SetFailure(_currentPayload.Message ?? "No selectable solutions were returned.");
                return;
            }

            _currentResolution = resolution;
            _currentAuthResult = authResult;
            PopulateSolutions(
                solutionResult.Solutions,
                resolution,
                string.Equals(_cachedPayload?.EnvironmentUrl, resolution.EnvironmentUrl, StringComparison.OrdinalIgnoreCase)
                    ? _cachedPayload?.SelectedSolution
                    : null);
            UpdateSelectedSolutionState();

            SetStatus(
                badgeText: "Connected",
                badgeBackground: (Brush)FindResource("SuccessBrush"),
                badgeForeground: (Brush)FindResource("SuccessTextBrush"),
                title: "Interactive sign-in succeeded. Choose the working solution.",
                body: "Authentication is complete. Select the exact solution before handing the live context back to Codex so versioning and patch handling stay explicit.");
        }
        catch (Exception ex)
        {
            DiagnosticsTextBox.Text = ex.ToString();
            UseContextButton.IsEnabled = false;
            _currentPayload = new AuthDialogPayload
            {
                Success = false,
                Cancelled = false,
                Message = ex.Message,
                TargetUrlInput = string.IsNullOrWhiteSpace(targetUrl) ? null : targetUrl,
                EnvironmentUrl = string.IsNullOrWhiteSpace(ResolvedEnvironmentUrlTextBox.Text) ? null : ResolvedEnvironmentUrlTextBox.Text,
                Username = string.IsNullOrWhiteSpace(username) ? null : username,
                TenantId = string.IsNullOrWhiteSpace(tenantId) ? null : tenantId,
                Diagnostics = DiagnosticsTextBox.Text,
                SelectedSolution = CurrentSelectedSolution()?.ToPayload(),
            };
            SetFailure(ex.Message);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void SolutionComboBox_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        UpdateSelectedSolutionState();
    }

    private void UseContextButton_Click(object sender, RoutedEventArgs e)
    {
        if (_currentPayload is null || !_currentPayload.Success)
        {
            SetFailure("Validate a successful connection before using the context.");
            return;
        }

        if (_currentPayload.SelectedSolution is null)
        {
            SetFailure("Select a working solution before using the context.");
            return;
        }

        PersistPayload(_currentPayload);
        _completed = true;
        DialogResult = true;
        Close();
    }

    private void CancelButton_Click(object sender, RoutedEventArgs e)
    {
        PersistPayload(new AuthDialogPayload
        {
            Success = false,
            Cancelled = true,
            Message = "Authentication dialog was cancelled.",
            TargetUrlInput = string.IsNullOrWhiteSpace(TargetUrlTextBox.Text) ? null : TargetUrlTextBox.Text.Trim(),
            EnvironmentUrl = string.IsNullOrWhiteSpace(ResolvedEnvironmentUrlTextBox.Text) ? null : ResolvedEnvironmentUrlTextBox.Text.Trim(),
            Username = string.IsNullOrWhiteSpace(UsernameTextBox.Text) ? null : UsernameTextBox.Text.Trim(),
            TenantId = string.IsNullOrWhiteSpace(TenantIdTextBox.Text) ? null : TenantIdTextBox.Text.Trim(),
            Diagnostics = DiagnosticsTextBox.Text,
            SelectedSolution = CurrentSelectedSolution()?.ToPayload(),
        });
        _completed = true;
        DialogResult = false;
        Close();
    }

    private void Window_Closing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        if (_completed)
        {
            return;
        }

        PersistPayload(new AuthDialogPayload
        {
            Success = false,
            Cancelled = true,
            Message = "Authentication dialog was closed before completion.",
            TargetUrlInput = string.IsNullOrWhiteSpace(TargetUrlTextBox.Text) ? null : TargetUrlTextBox.Text.Trim(),
            EnvironmentUrl = string.IsNullOrWhiteSpace(ResolvedEnvironmentUrlTextBox.Text) ? null : ResolvedEnvironmentUrlTextBox.Text.Trim(),
            Username = string.IsNullOrWhiteSpace(UsernameTextBox.Text) ? null : UsernameTextBox.Text.Trim(),
            TenantId = string.IsNullOrWhiteSpace(TenantIdTextBox.Text) ? null : TenantIdTextBox.Text.Trim(),
            Diagnostics = DiagnosticsTextBox.Text,
            SelectedSolution = CurrentSelectedSolution()?.ToPayload(),
        });
    }

    private void ResetSolutionSelection()
    {
        SolutionSelectionPanel.Visibility = Visibility.Collapsed;
        SolutionComboBox.ItemsSource = null;
        SolutionComboBox.SelectedItem = null;
        SolutionSelectionStatusTextBlock.Text = "Validate the connection to load solutions.";
        _currentResolution = null;
        _currentAuthResult = null;
        _currentPayload = null;
    }

    private void PopulateSolutions(
        IReadOnlyList<SolutionDialogOption> solutions,
        TargetResolutionResult resolution,
        SelectedSolutionPayload? cachedSelection)
    {
        SolutionSelectionPanel.Visibility = Visibility.Visible;
        SolutionComboBox.ItemsSource = solutions;

        var preferred = ResolvePreferredSolution(solutions, resolution, cachedSelection);
        if (preferred is not null)
        {
            SolutionComboBox.SelectedItem = preferred;
        }
        else if (solutions.Count == 1)
        {
            SolutionComboBox.SelectedIndex = 0;
        }
        else
        {
            SolutionComboBox.SelectedIndex = -1;
        }
    }

    private static SolutionDialogOption? ResolvePreferredSolution(
        IReadOnlyList<SolutionDialogOption> solutions,
        TargetResolutionResult resolution,
        SelectedSolutionPayload? cachedSelection)
    {
        if (!string.IsNullOrWhiteSpace(resolution.SolutionId))
        {
            var fromTargetUrl = solutions.FirstOrDefault(solution =>
                string.Equals(solution.SolutionId, resolution.SolutionId, StringComparison.OrdinalIgnoreCase));
            if (fromTargetUrl is not null)
            {
                return fromTargetUrl;
            }
        }

        if (!string.IsNullOrWhiteSpace(cachedSelection?.SolutionId))
        {
            var fromCacheId = solutions.FirstOrDefault(solution =>
                string.Equals(solution.SolutionId, cachedSelection.SolutionId, StringComparison.OrdinalIgnoreCase));
            if (fromCacheId is not null)
            {
                return fromCacheId;
            }
        }

        if (!string.IsNullOrWhiteSpace(cachedSelection?.UniqueName))
        {
            return solutions.FirstOrDefault(solution =>
                string.Equals(solution.UniqueName, cachedSelection.UniqueName, StringComparison.OrdinalIgnoreCase));
        }

        return null;
    }

    private void UpdateSelectedSolutionState()
    {
        var selection = CurrentSelectedSolution();
        if (_currentResolution is null || _currentAuthResult is null)
        {
            UseContextButton.IsEnabled = false;
            return;
        }

        if (selection is null)
        {
            SolutionSelectionStatusTextBlock.Text =
                "Select the solution Codex should work on. No Dataverse mutations should start before this is explicit.";
            DiagnosticsTextBox.Text = BuildDiagnosticsText(_currentResolution, _currentAuthResult, null);
            _currentPayload = BuildSuccessPayload(_currentResolution, _currentAuthResult, null);
            UseContextButton.IsEnabled = false;
            return;
        }

        SolutionSelectionStatusTextBlock.Text = BuildSolutionSelectionSummary(selection);
        DiagnosticsTextBox.Text = BuildDiagnosticsText(_currentResolution, _currentAuthResult, selection);
        _currentPayload = BuildSuccessPayload(_currentResolution, _currentAuthResult, selection);
        UseContextButton.IsEnabled = !_isValidating;
    }

    private AuthDialogPayload BuildSuccessPayload(
        TargetResolutionResult resolution,
        AuthAttemptResult authResult,
        SolutionDialogOption? selection)
    {
        var message = selection is null
            ? authResult.Message
            : $"Connected to {selection.FriendlyName} ({selection.UniqueName}) in {resolution.EnvironmentUrl}";

        return new AuthDialogPayload
        {
            Success = true,
            Cancelled = false,
            Message = message,
            TargetUrlInput = resolution.TargetInput,
            EnvironmentUrl = resolution.EnvironmentUrl,
            SolutionUrl = resolution.SolutionUrl,
            EnvironmentId = resolution.EnvironmentId,
            Username = UsernameTextBox.Text.Trim(),
            TenantId = string.IsNullOrWhiteSpace(TenantIdTextBox.Text) ? null : TenantIdTextBox.Text.Trim(),
            Diagnostics = DiagnosticsTextBox.Text,
            WhoAmI = authResult.WhoAmI,
            SelectedSolution = selection?.ToPayload(),
        };
    }

    private SolutionDialogOption? CurrentSelectedSolution() => SolutionComboBox.SelectedItem as SolutionDialogOption;

    private void SetBusy(bool isBusy)
    {
        _isValidating = isBusy;
        BusyProgressBar.Visibility = isBusy ? Visibility.Visible : Visibility.Collapsed;
        ValidateButton.IsEnabled = !isBusy;
        UseContextButton.IsEnabled = !isBusy && _currentPayload?.Success == true && _currentPayload.SelectedSolution is not null;
        TargetUrlTextBox.IsEnabled = !isBusy;
        UsernameTextBox.IsEnabled = !isBusy;
        TenantIdTextBox.IsEnabled = !isBusy;
        SolutionComboBox.IsEnabled = !isBusy && SolutionComboBox.Items.Count > 0;
    }

    private void SetFailure(string message)
    {
        SetStatus(
            badgeText: "Failed",
            badgeBackground: (Brush)FindResource("ErrorBrush"),
            badgeForeground: (Brush)FindResource("ErrorTextBrush"),
            title: "Connection or solution preparation failed.",
            body: message);
    }

    private void SetStatus(string badgeText, Brush badgeBackground, Brush badgeForeground, string title, string body)
    {
        StatusBadge.Background = badgeBackground;
        StatusBadgeText.Foreground = badgeForeground;
        StatusBadgeText.Text = badgeText;
        StatusTitleTextBlock.Text = title;
        StatusBodyTextBlock.Text = body;
    }

    private static string BuildDiagnosticsText(
        TargetResolutionResult resolution,
        AuthAttemptResult authResult,
        SolutionDialogOption? selectedSolution,
        SolutionListAttemptResult? solutionResult = null)
    {
        var lines = new List<string>
        {
            $"Target input: {resolution.TargetInput}",
            $"Resolved org URL: {resolution.EnvironmentUrl}",
        };
        if (!string.IsNullOrWhiteSpace(resolution.EnvironmentId))
        {
            lines.Add($"Environment ID: {resolution.EnvironmentId}");
        }
        if (!string.IsNullOrWhiteSpace(resolution.SolutionUrl))
        {
            lines.Add($"Solution URL: {resolution.SolutionUrl}");
        }
        if (!string.IsNullOrWhiteSpace(resolution.SolutionId))
        {
            lines.Add($"Solution ID from target URL: {resolution.SolutionId}");
        }
        if (selectedSolution is not null)
        {
            lines.Add($"Selected solution: {selectedSolution.FriendlyName} ({selectedSolution.UniqueName})");
            if (!string.IsNullOrWhiteSpace(selectedSolution.Version))
            {
                lines.Add($"Selected solution version: {selectedSolution.Version}");
            }
            lines.Add($"Selected solution type: {(selectedSolution.IsPatch ? "Patch" : selectedSolution.IsManaged ? "Managed" : "Unmanaged")}");
            if (selectedSolution.IsPatch && !string.IsNullOrWhiteSpace(selectedSolution.ParentSolutionUniqueName))
            {
                lines.Add($"Patch parent solution: {selectedSolution.ParentSolutionUniqueName}");
            }
        }
        lines.Add(string.Empty);
        lines.Add("WhoAmI payload:");
        lines.Add(authResult.WhoAmI?.ToJsonString(JsonOptions) ?? "<none>");
        if (solutionResult is not null)
        {
            lines.Add(string.Empty);
            lines.Add($"Selectable solutions returned: {solutionResult.Solutions.Count}");
            lines.Add($"Solution lookup message: {solutionResult.Message}");
        }
        lines.Add(string.Empty);
        lines.Add("Diagnostics:");
        lines.Add(string.IsNullOrWhiteSpace(authResult.Diagnostics) ? "<none>" : authResult.Diagnostics);
        if (solutionResult is not null && !string.IsNullOrWhiteSpace(solutionResult.Diagnostics))
        {
            lines.Add(string.Empty);
            lines.Add("Solution diagnostics:");
            lines.Add(solutionResult.Diagnostics);
        }
        return string.Join(Environment.NewLine, lines);
    }

    private static string BuildSolutionSelectionSummary(SolutionDialogOption option)
    {
        var parts = new List<string>
        {
            $"Selected solution: {option.FriendlyName} ({option.UniqueName}).",
        };
        if (!string.IsNullOrWhiteSpace(option.Version))
        {
            parts.Add($"Current version: {option.Version}.");
        }

        if (option.IsPatch)
        {
            parts.Add($"This is a patch solution for {option.ParentSolutionUniqueName ?? option.ParentSolutionId ?? "<unknown parent>"}. Decide explicitly later whether Codex should keep working in the patch or merge it back to the main solution.");
        }
        else if (option.IsManaged)
        {
            parts.Add("This solution is managed.");
        }
        else
        {
            parts.Add("This is an unmanaged solution and will be treated as the current working solution unless you later instruct Codex to create a patch.");
        }

        return string.Join(" ", parts);
    }

    private static AuthDialogPayload? LoadCachedPayload()
    {
        var cachePath = CachePath();
        if (!File.Exists(cachePath))
        {
            return null;
        }

        try
        {
            return JsonSerializer.Deserialize<AuthDialogPayload>(File.ReadAllText(cachePath));
        }
        catch
        {
            return null;
        }
    }

    private void PersistPayload(AuthDialogPayload payload)
    {
        var json = JsonSerializer.Serialize(payload, JsonOptions);
        if (!string.IsNullOrWhiteSpace(_options.OutputPath))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_options.OutputPath) ?? ".");
            File.WriteAllText(_options.OutputPath, json);
        }

        if (payload.Success)
        {
            var cachePath = CachePath();
            Directory.CreateDirectory(Path.GetDirectoryName(cachePath) ?? ".");
            File.WriteAllText(cachePath, json);
        }
    }

    private static string CachePath()
    {
        return Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "CodexPowerPlatform",
            "auth-context.json");
    }
}
