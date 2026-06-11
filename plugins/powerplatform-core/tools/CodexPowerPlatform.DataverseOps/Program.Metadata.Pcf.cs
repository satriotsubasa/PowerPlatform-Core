using System.Xml.Linq;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static object ExecuteBindPcfControl(ServiceClient client, PcfBindingSpec spec)
    {
        ValidateRequired(spec.EntityLogicalName, "entityLogicalName");
        ValidateRequired(spec.FormName, "formName");
        ValidateRequired(spec.PcfControlName, "pcfControlName");
        if (string.IsNullOrWhiteSpace(spec.ControlUniqueId)
            && string.IsNullOrWhiteSpace(spec.ControlId)
            && string.IsNullOrWhiteSpace(spec.ControlDataFieldName))
        {
            throw new InvalidOperationException(
                "Provide one of controlUniqueId, controlId, or controlDataFieldName to locate the form control.");
        }

        var form = RetrieveSingle(
            client,
            "systemform",
            new ColumnSet("formxml", "name", "objecttypecode", "type"),
            new ConditionExpression("objecttypecode", ConditionOperator.Equal, spec.EntityLogicalName),
            new ConditionExpression("name", ConditionOperator.Equal, spec.FormName),
            new ConditionExpression("type", ConditionOperator.Equal, spec.FormType ?? 2));

        var formXml = form.GetAttributeValue<string>("formxml")
            ?? throw new InvalidOperationException($"Form '{spec.FormName}' does not contain formxml.");
        var updated = UpdatePcfBindingXml(formXml, spec);
        if (!updated.Changed)
        {
            return new
            {
                success = true,
                mode = "bind-pcf-control",
                formId = form.Id,
                entityLogicalName = spec.EntityLogicalName,
                formName = spec.FormName,
                targetControlId = updated.TargetControlId,
                pcfControlName = spec.PcfControlName,
                appliedFormFactors = updated.AppliedFormFactors,
                message = "No PCF binding changes were needed.",
            };
        }

        var patch = new Entity("systemform", form.Id)
        {
            ["formxml"] = updated.FormXml,
        };
        client.Update(patch);

        return new
        {
            success = true,
            mode = "bind-pcf-control",
            formId = form.Id,
            entityLogicalName = spec.EntityLogicalName,
            formName = spec.FormName,
            targetControlId = updated.TargetControlId,
            pcfControlName = spec.PcfControlName,
            pcfControlVersion = spec.PcfControlVersion,
            customControlDefaultConfigId = spec.CustomControlDefaultConfigId,
            appliedFormFactors = updated.AppliedFormFactors,
            replacedExisting = spec.ReplaceExisting,
        };
    }

    private static PcfBindingXmlUpdateResult UpdatePcfBindingXml(string formXml, PcfBindingSpec spec)
    {
        var document = XDocument.Parse(formXml, LoadOptions.PreserveWhitespace);
        var form = document.Root ?? throw new InvalidOperationException("Form XML does not contain a root form node.");
        var targetControl = FindTargetFormControl(document, spec);
        var targetControlId = ResolveTargetControlId(targetControl, spec);

        var controlDescriptions = EnsureDirectChild(form, "controlDescriptions");
        var controlDescription = controlDescriptions
            .Elements("controlDescription")
            .FirstOrDefault(element => MatchesControlReference((string?)element.Attribute("forControl"), targetControlId));

        var changed = false;
        if (controlDescription is null)
        {
            controlDescription = new XElement("controlDescription", new XAttribute("forControl", FormatControlReference(targetControlId)));
            controlDescriptions.Add(controlDescription);
            changed = true;
        }
        else if (!string.Equals((string?)controlDescription.Attribute("forControl"), FormatControlReference(targetControlId), StringComparison.OrdinalIgnoreCase))
        {
            controlDescription.SetAttributeValue("forControl", FormatControlReference(targetControlId));
            changed = true;
        }

        if (spec.ReplaceExisting && controlDescription.Elements("customControl").Any())
        {
            controlDescription.Elements("customControl").Remove();
            changed = true;
        }

        if (!string.IsNullOrWhiteSpace(spec.CustomControlDefaultConfigId))
        {
            var defaultNode = BuildPcfCustomControlElement(
                name: null,
                formFactor: null,
                version: null,
                controlDefaultConfigId: spec.CustomControlDefaultConfigId,
                parameters: spec.DefaultConfigParameters);
            changed |= UpsertCustomControlNode(
                controlDescription,
                defaultNode,
                existingNode => string.Equals(
                    NormalizeOptionalString((string?)existingNode.Attribute("id")),
                    NormalizeOptionalString(spec.CustomControlDefaultConfigId),
                    StringComparison.OrdinalIgnoreCase));
        }

        var appliedFormFactors = ResolveFormFactors(spec);
        foreach (var formFactor in appliedFormFactors)
        {
            spec.ParametersByFormFactor.TryGetValue(formFactor.ToString(), out var numericSpecificParameters);
            spec.ParametersByFormFactor.TryGetValue(FormFactorAlias(formFactor), out var aliasSpecificParameters);
            var effectiveParameters = aliasSpecificParameters
                ?? numericSpecificParameters
                ?? spec.Parameters;

            var customControlNode = BuildPcfCustomControlElement(
                name: spec.PcfControlName,
                formFactor: formFactor,
                version: spec.PcfControlVersion,
                controlDefaultConfigId: null,
                parameters: effectiveParameters);

            changed |= UpsertCustomControlNode(
                controlDescription,
                customControlNode,
                existingNode =>
                {
                    var existingName = NormalizeOptionalString((string?)existingNode.Attribute("name"));
                    var existingFormFactor = NormalizeOptionalString((string?)existingNode.Attribute("formFactor"));
                    return string.Equals(existingName, NormalizeOptionalString(spec.PcfControlName), StringComparison.OrdinalIgnoreCase)
                           && string.Equals(existingFormFactor, formFactor.ToString(), StringComparison.OrdinalIgnoreCase);
                });
        }

        return new PcfBindingXmlUpdateResult(
            changed,
            document.ToString(SaveOptions.DisableFormatting),
            appliedFormFactors,
            targetControlId);
    }

    private static XElement FindTargetFormControl(XDocument document, PcfBindingSpec spec)
    {
        var controls = document.Descendants("control").ToList();
        var candidates = controls.Where(control => MatchesTargetFormControl(control, spec)).ToList();
        if (candidates.Count == 0)
        {
            throw new InvalidOperationException("Could not locate the requested control on the target form.");
        }

        if (candidates.Count > 1)
        {
            throw new InvalidOperationException(
                "More than one control matched the requested PCF binding selector. Provide a more specific control id.");
        }

        return candidates[0];
    }

    private static bool MatchesTargetFormControl(XElement control, PcfBindingSpec spec)
    {
        var controlId = NormalizeOptionalString((string?)control.Attribute("id"));
        var uniqueId = NormalizeOptionalString((string?)control.Attribute("uniqueid"));
        var dataFieldName = NormalizeOptionalString((string?)control.Attribute("datafieldname"));

        if (!string.IsNullOrWhiteSpace(spec.ControlUniqueId))
        {
            var expected = NormalizeControlReference(spec.ControlUniqueId);
            if (string.Equals(NormalizeControlReference(uniqueId), expected, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        if (!string.IsNullOrWhiteSpace(spec.ControlId))
        {
            var expected = NormalizeControlReference(spec.ControlId);
            if (string.Equals(NormalizeControlReference(controlId), expected, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        if (!string.IsNullOrWhiteSpace(spec.ControlDataFieldName))
        {
            var expected = NormalizeLogicalName(spec.ControlDataFieldName);
            if (string.Equals(NormalizeLogicalName(dataFieldName ?? string.Empty), expected, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }
        }

        return false;
    }

    private static string ResolveTargetControlId(XElement control, PcfBindingSpec spec)
    {
        var resolved = NormalizeOptionalString((string?)control.Attribute("id"))
            ?? NormalizeOptionalString((string?)control.Attribute("uniqueid"))
            ?? NormalizeOptionalString(spec.ControlId)
            ?? NormalizeOptionalString(spec.ControlUniqueId);

        if (string.IsNullOrWhiteSpace(resolved))
        {
            throw new InvalidOperationException(
                "The matched form control does not expose an id or uniqueid that can be used in controlDescriptions.");
        }

        return NormalizeControlReference(resolved);
    }

    private static bool MatchesControlReference(string? actual, string expected)
    {
        return string.Equals(NormalizeControlReference(actual), NormalizeControlReference(expected), StringComparison.OrdinalIgnoreCase);
    }

    private static string NormalizeControlReference(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        return value.Trim().Trim('{', '}').ToLowerInvariant();
    }

    private static string FormatControlReference(string value)
    {
        var normalized = NormalizeControlReference(value);
        return string.IsNullOrWhiteSpace(normalized) ? value : $"{{{normalized}}}";
    }

    private static List<int> ResolveFormFactors(PcfBindingSpec spec)
    {
        var factors = new List<int>();
        foreach (var value in spec.FormFactors)
        {
            if (!factors.Contains(value))
            {
                factors.Add(value);
            }
        }

        if (factors.Count == 0)
        {
            factors.AddRange([0, 1, 2]);
        }

        return factors;
    }

    private static string FormFactorAlias(int formFactor)
    {
        return formFactor switch
        {
            0 => "web",
            1 => "phone",
            2 => "tablet",
            _ => formFactor.ToString(),
        };
    }

    private static XElement BuildPcfCustomControlElement(
        string? name,
        int? formFactor,
        string? version,
        string? controlDefaultConfigId,
        IEnumerable<PcfParameterElementSpec> parameters)
    {
        var element = new XElement("customControl");
        if (!string.IsNullOrWhiteSpace(controlDefaultConfigId))
        {
            element.SetAttributeValue("id", controlDefaultConfigId);
        }

        if (!string.IsNullOrWhiteSpace(name))
        {
            element.SetAttributeValue("name", name);
        }

        if (formFactor.HasValue)
        {
            element.SetAttributeValue("formFactor", formFactor.Value.ToString());
        }

        if (!string.IsNullOrWhiteSpace(version))
        {
            element.SetAttributeValue("version", version);
        }

        var parametersElement = new XElement("parameters");
        foreach (var parameter in parameters)
        {
            parametersElement.Add(BuildPcfParameterElement(parameter));
        }

        element.Add(parametersElement);
        return element;
    }

    private static XElement BuildPcfParameterElement(PcfParameterElementSpec spec)
    {
        ValidateRequired(spec.Name, "parameters[].name");
        var element = new XElement(spec.Name.Trim());
        foreach (var attribute in spec.Attributes)
        {
            if (!string.IsNullOrWhiteSpace(attribute.Key) && attribute.Value is not null)
            {
                element.SetAttributeValue(attribute.Key.Trim(), attribute.Value);
            }
        }

        if (!string.IsNullOrWhiteSpace(spec.Text))
        {
            element.Value = spec.Text;
        }

        foreach (var child in spec.Children)
        {
            element.Add(BuildPcfParameterElement(child));
        }

        return element;
    }

    private static bool UpsertCustomControlNode(
        XElement controlDescription,
        XElement desiredNode,
        Func<XElement, bool> matcher)
    {
        var existing = controlDescription.Elements("customControl").FirstOrDefault(matcher);
        if (existing is null)
        {
            controlDescription.Add(desiredNode);
            return true;
        }

        if (XNode.DeepEquals(existing, desiredNode))
        {
            return false;
        }

        existing.ReplaceWith(desiredNode);
        return true;
    }

    private sealed class PcfBindingSpec
    {
        public string EntityLogicalName { get; init; } = string.Empty;

        public string FormName { get; init; } = string.Empty;

        public int? FormType { get; init; }

        public string? ControlUniqueId { get; init; }

        public string? ControlId { get; init; }

        public string? ControlDataFieldName { get; init; }

        public string PcfControlName { get; init; } = string.Empty;

        public string? PcfControlVersion { get; init; }

        public string? CustomControlDefaultConfigId { get; init; }

        public bool ReplaceExisting { get; init; } = true;

        public List<int> FormFactors { get; init; } = new();

        public List<PcfParameterElementSpec> Parameters { get; init; } = new();

        public Dictionary<string, List<PcfParameterElementSpec>> ParametersByFormFactor { get; init; } = new(StringComparer.OrdinalIgnoreCase);

        public List<PcfParameterElementSpec> DefaultConfigParameters { get; init; } = new();
    }

    private sealed class PcfParameterElementSpec
    {
        public string Name { get; init; } = string.Empty;

        public string? Text { get; init; }

        public Dictionary<string, string> Attributes { get; init; } = new(StringComparer.OrdinalIgnoreCase);

        public List<PcfParameterElementSpec> Children { get; init; } = new();
    }

    private sealed record PcfBindingXmlUpdateResult(
        bool Changed,
        string FormXml,
        List<int> AppliedFormFactors,
        string TargetControlId);
}
