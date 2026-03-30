using System.Xml.Linq;
using System.Xml.XPath;

internal sealed class XmlPatchOperationSpec
{
    public string Type { get; init; } = string.Empty;

    public string TargetXPath { get; init; } = string.Empty;

    public string? Xml { get; init; }

    public Dictionary<string, string?> Attributes { get; init; } = new(StringComparer.OrdinalIgnoreCase);
}

internal sealed record XmlPatchApplicationResult(
    bool Changed,
    string Xml,
    List<string> AppliedOperations,
    List<string> CreatedNodes);

internal static class FormXmlPatchEngine
{
    internal static XmlPatchApplicationResult ApplyFormXmlPatch(string formXml, IReadOnlyList<XmlPatchOperationSpec> operations)
    {
        var document = XDocument.Parse(formXml, LoadOptions.PreserveWhitespace);
        var root = document.Root ?? throw new InvalidOperationException("Form XML does not contain a root form node.");
        var appliedOperations = new List<string>();
        var createdNodes = new List<string>();
        var changed = ApplyOperations(root, operations, appliedOperations);

        return new XmlPatchApplicationResult(
            changed,
            document.ToString(SaveOptions.DisableFormatting),
            appliedOperations,
            createdNodes);
    }

    internal static XmlPatchApplicationResult ApplyFormRibbonPatch(
        string formXml,
        IReadOnlyList<XmlPatchOperationSpec> operations,
        bool createRibbonDiffXmlIfMissing)
    {
        var document = XDocument.Parse(formXml, LoadOptions.PreserveWhitespace);
        var root = document.Root ?? throw new InvalidOperationException("Form XML does not contain a root form node.");
        var appliedOperations = new List<string>();
        var createdNodes = new List<string>();

        var ribbonDiffXml = root.Element("RibbonDiffXml");
        var changed = false;
        if (ribbonDiffXml is null)
        {
            if (!createRibbonDiffXmlIfMissing)
            {
                throw new InvalidOperationException("Form XML does not contain RibbonDiffXml and createRibbonDiffXmlIfMissing is false.");
            }

            ribbonDiffXml = new XElement("RibbonDiffXml");
            root.Add(ribbonDiffXml);
            createdNodes.Add("RibbonDiffXml");
            changed = true;
        }

        changed |= ApplyOperations(ribbonDiffXml, operations, appliedOperations);
        return new XmlPatchApplicationResult(
            changed,
            document.ToString(SaveOptions.DisableFormatting),
            appliedOperations,
            createdNodes);
    }

    private static bool ApplyOperations(
        XElement scopeRoot,
        IReadOnlyList<XmlPatchOperationSpec> operations,
        List<string> appliedOperations)
    {
        if (operations.Count == 0)
        {
            throw new InvalidOperationException("Provide at least one XML patch operation.");
        }

        var changed = false;
        foreach (var operation in operations)
        {
            ValidateRequired(operation.Type, "operations[].type");
            ValidateRequired(operation.TargetXPath, "operations[].targetXPath");

            var normalizedType = NormalizeOperationType(operation.Type);
            var targets = SelectTargets(scopeRoot, operation.TargetXPath);

            switch (normalizedType)
            {
                case "remove-element":
                    foreach (var target in targets)
                    {
                        target.Remove();
                    }

                    changed = true;
                    appliedOperations.Add($"remove-element:{targets.Count}");
                    break;

                case "replace-element":
                    {
                        var fragments = ParseXmlFragmentElements(operation.Xml, normalizedType);
                        foreach (var target in targets)
                        {
                            target.ReplaceWith(CloneElements(fragments));
                        }

                        changed = true;
                        appliedOperations.Add($"replace-element:{targets.Count}");
                        break;
                    }

                case "replace-children":
                    {
                        var fragments = ParseXmlFragmentElements(operation.Xml, normalizedType);
                        foreach (var target in targets)
                        {
                            target.RemoveNodes();
                            target.Add(CloneElements(fragments));
                        }

                        changed = true;
                        appliedOperations.Add($"replace-children:{targets.Count}");
                        break;
                    }

                case "append-child":
                    {
                        var fragments = ParseXmlFragmentElements(operation.Xml, normalizedType);
                        foreach (var target in targets)
                        {
                            target.Add(CloneElements(fragments));
                        }

                        changed = true;
                        appliedOperations.Add($"append-child:{targets.Count}");
                        break;
                    }

                case "prepend-child":
                    {
                        var fragments = ParseXmlFragmentElements(operation.Xml, normalizedType);
                        foreach (var target in targets)
                        {
                            target.AddFirst(CloneElements(fragments));
                        }

                        changed = true;
                        appliedOperations.Add($"prepend-child:{targets.Count}");
                        break;
                    }

                case "insert-before":
                    {
                        var fragments = ParseXmlFragmentElements(operation.Xml, normalizedType);
                        foreach (var target in targets)
                        {
                            target.AddBeforeSelf(CloneElements(fragments));
                        }

                        changed = true;
                        appliedOperations.Add($"insert-before:{targets.Count}");
                        break;
                    }

                case "insert-after":
                    {
                        var fragments = ParseXmlFragmentElements(operation.Xml, normalizedType);
                        foreach (var target in targets)
                        {
                            target.AddAfterSelf(CloneElements(fragments));
                        }

                        changed = true;
                        appliedOperations.Add($"insert-after:{targets.Count}");
                        break;
                    }

                case "set-attributes":
                    {
                        if (operation.Attributes.Count == 0)
                        {
                            throw new InvalidOperationException("set-attributes requires a non-empty attributes object.");
                        }

                        var operationChanged = false;
                        foreach (var target in targets)
                        {
                            foreach (var pair in operation.Attributes)
                            {
                                if (string.IsNullOrWhiteSpace(pair.Key))
                                {
                                    throw new InvalidOperationException("Attribute names in set-attributes must be non-empty.");
                                }

                                var existing = target.Attribute(pair.Key);
                                if (pair.Value is null)
                                {
                                    if (existing is not null)
                                    {
                                        existing.Remove();
                                        operationChanged = true;
                                    }

                                    continue;
                                }

                                if (!string.Equals(existing?.Value, pair.Value, StringComparison.Ordinal))
                                {
                                    target.SetAttributeValue(pair.Key, pair.Value);
                                    operationChanged = true;
                                }
                            }
                        }

                        changed |= operationChanged;
                        appliedOperations.Add($"set-attributes:{targets.Count}");
                        break;
                    }

                default:
                    throw new InvalidOperationException(
                        $"Unsupported XML patch operation '{operation.Type}'. Use replace-element, replace-children, remove-element, append-child, prepend-child, insert-before, insert-after, or set-attributes.");
            }
        }

        return changed;
    }

    private static List<XElement> SelectTargets(XElement scopeRoot, string targetXPath)
    {
        if (targetXPath == ".")
        {
            return [scopeRoot];
        }

        var targets = scopeRoot.XPathSelectElements(targetXPath).ToList();
        if (targets.Count == 0)
        {
            throw new InvalidOperationException($"The XML patch targetXPath '{targetXPath}' did not match any elements.");
        }

        return targets;
    }

    private static List<XElement> ParseXmlFragmentElements(string? xml, string operationType)
    {
        if (string.IsNullOrWhiteSpace(xml))
        {
            throw new InvalidOperationException($"{operationType} requires a non-empty xml fragment.");
        }

        var wrapper = XElement.Parse($"<root>{xml}</root>", LoadOptions.PreserveWhitespace);
        if (!wrapper.Nodes().Any())
        {
            throw new InvalidOperationException($"{operationType} requires at least one XML element fragment.");
        }

        if (wrapper.Nodes().Any(node => node is not XElement))
        {
            throw new InvalidOperationException($"{operationType} only supports XML element fragments.");
        }

        return wrapper.Elements().Select(element => new XElement(element)).ToList();
    }

    private static List<XElement> CloneElements(List<XElement> elements)
    {
        return elements.Select(element => new XElement(element)).ToList();
    }

    private static string NormalizeOperationType(string rawValue)
    {
        return rawValue.Trim().ToLowerInvariant().Replace("_", "-");
    }

    private static void ValidateRequired(string? value, string label)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException($"Missing required property '{label}'.");
        }
    }
}
