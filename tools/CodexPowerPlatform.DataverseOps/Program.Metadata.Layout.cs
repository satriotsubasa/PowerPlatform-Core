using System.Xml.Linq;

internal static partial class Program
{
    private static FormXmlUpdateResult UpdateMainFormLayoutXml(string formXml, FormUpdateSpec spec)
    {
        var document = XDocument.Parse(formXml, LoadOptions.PreserveWhitespace);
        var createdTabs = new List<string>();
        var createdSections = new List<string>();
        var targetTab = EnsureTabForUpdate(document, spec, createdTabs);
        var targetSection = EnsureSectionForUpdate(document, targetTab, spec, createdSections);
        var rows = targetSection.Element("rows") ?? new XElement("rows");
        if (rows.Parent is null)
        {
            targetSection.Add(rows);
        }

        if (spec.SectionColumns.HasValue)
        {
            targetSection.SetAttributeValue("columns", spec.SectionColumns.Value.ToString());
        }

        var targetSectionFields = targetSection
            .Descendants("control")
            .Select(control => NormalizeOptionalString((string?)control.Attribute("datafieldname")))
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => name!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
        var existingFields = document
            .Descendants("control")
            .Select(control => NormalizeOptionalString((string?)control.Attribute("datafieldname")))
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => name!)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var added = new List<string>();
        var moved = new List<string>();
        var skipped = new List<string>();
        foreach (var rawField in spec.FieldLogicalNames)
        {
            var field = NormalizeLogicalName(rawField);
            if (targetSectionFields.Contains(field))
            {
                skipped.Add(field);
                continue;
            }

            var movedField = false;
            if (spec.MoveExistingFields && existingFields.Contains(field))
            {
                movedField = RemoveFieldFromForm(document, targetSection, field);
            }
            else if (existingFields.Contains(field))
            {
                skipped.Add(field);
                continue;
            }

            InsertFormRow(rows, CreateFormRow(field), prepend: spec.PrependFields);
            targetSectionFields.Add(field);
            existingFields.Add(field);
            added.Add(field);
            if (movedField)
            {
                moved.Add(field);
            }
        }

        return new FormXmlUpdateResult(
            added.Count > 0 || moved.Count > 0 || createdTabs.Count > 0 || createdSections.Count > 0,
            document.ToString(SaveOptions.DisableFormatting),
            added,
            moved,
            skipped,
            createdTabs,
            createdSections);
    }

    private static XElement EnsureTabForUpdate(XDocument document, FormUpdateSpec spec, List<string> createdTabs)
    {
        var existing = FindExistingTab(document, spec);
        if (existing is not null)
        {
            return existing;
        }

        if (!spec.CreateTabIfMissing)
        {
            throw new InvalidOperationException("Could not locate the requested form tab.");
        }

        var tabName = spec.TabName
            ?? CreateInternalName(spec.TabLabel, "tab");
        var tabLabel = spec.TabLabel ?? spec.TabName ?? "New Tab";
        var tabs = document.Descendants("tabs").FirstOrDefault()
            ?? EnsureDirectChild(document.Root ?? throw new InvalidOperationException("Form XML does not contain a root form node."), "tabs");
        var tab = new XElement(
            "tab",
            new XAttribute("name", tabName),
            new XAttribute("id", Guid.NewGuid().ToString("D")),
            new XAttribute("verticallayout", "true"),
            new XAttribute("expanded", "true"),
            new XAttribute("showlabel", "true"),
            new XAttribute("locklevel", "0"),
            new XElement(
                "labels",
                new XElement(
                    "label",
                    new XAttribute("description", tabLabel),
                    new XAttribute("languagecode", "1033"))),
            new XElement(
                "columns",
                new XElement(
                    "column",
                    new XAttribute("width", "100%"),
                    new XElement("sections"))));
        tabs.Add(tab);
        createdTabs.Add(tabName);
        return tab;
    }

    private static XElement EnsureSectionForUpdate(
        XDocument document,
        XElement tab,
        FormUpdateSpec spec,
        List<string> createdSections)
    {
        var existing = FindExistingSection(tab, spec);
        if (existing is not null)
        {
            return existing;
        }

        if (!spec.CreateSectionIfMissing)
        {
            throw new InvalidOperationException("Could not locate the requested form section.");
        }

        var sectionName = spec.SectionName ?? CreateInternalName(spec.SectionLabel, "section");
        var sectionLabel = spec.SectionLabel ?? spec.SectionName ?? "New Section";
        var sectionsElement = tab.Descendants("sections").FirstOrDefault()
            ?? EnsureDirectChild(
                tab.Descendants("column").FirstOrDefault()
                    ?? throw new InvalidOperationException("Form tab does not contain a column for sections."),
                "sections");
        var section = new XElement(
            "section",
            new XAttribute("name", sectionName),
            new XAttribute("id", Guid.NewGuid().ToString("D")),
            new XAttribute("showlabel", "true"),
            new XAttribute("showbar", "false"),
            new XAttribute("locklevel", "0"),
            new XAttribute("columns", (spec.SectionColumns ?? 1).ToString()),
            new XAttribute("labelwidth", "115"),
            new XAttribute("celllabelalignment", "Left"),
            new XAttribute("celllabelposition", "Left"),
            new XAttribute("layout", "varwidth"),
            new XElement(
                "labels",
                new XElement(
                    "label",
                    new XAttribute("description", sectionLabel),
                    new XAttribute("languagecode", "1033"))),
            new XElement("rows"));
        sectionsElement.Add(section);
        createdSections.Add(sectionName);
        return section;
    }

    private static XElement? FindExistingTab(XDocument document, FormUpdateSpec spec)
    {
        var tabs = document.Descendants("tab").ToList();
        var tab = tabs.FirstOrDefault(candidate =>
            MatchesAttribute(candidate, "name", spec.TabName)
            || MatchesLabel(candidate, spec.TabLabel));
        if (tab is not null)
        {
            return tab;
        }

        if (string.IsNullOrWhiteSpace(spec.TabName) && string.IsNullOrWhiteSpace(spec.TabLabel) && tabs.Count > 0)
        {
            return tabs[0];
        }

        return null;
    }

    private static XElement? FindExistingSection(XElement tab, FormUpdateSpec spec)
    {
        var sections = tab.Descendants("section").ToList();
        var section = sections.FirstOrDefault(candidate =>
            MatchesAttribute(candidate, "name", spec.SectionName)
            || MatchesLabel(candidate, spec.SectionLabel));
        if (section is not null)
        {
            return section;
        }

        if (string.IsNullOrWhiteSpace(spec.SectionName) && string.IsNullOrWhiteSpace(spec.SectionLabel) && sections.Count > 0)
        {
            return sections[0];
        }

        return null;
    }

    private static void InsertFormRow(XElement rows, XElement row, bool prepend)
    {
        if (prepend)
        {
            rows.AddFirst(row);
            return;
        }

        rows.Add(row);
    }

    private static bool RemoveFieldFromForm(XDocument document, XElement targetSection, string fieldLogicalName)
    {
        var controls = document
            .Descendants("control")
            .Where(control => string.Equals(
                NormalizeOptionalString((string?)control.Attribute("datafieldname")),
                fieldLogicalName,
                StringComparison.OrdinalIgnoreCase))
            .ToList();

        var changed = false;
        foreach (var control in controls)
        {
            if (control.Ancestors("section").Any(section => ReferenceEquals(section, targetSection)))
            {
                continue;
            }

            var cell = control.Ancestors("cell").FirstOrDefault();
            var row = control.Ancestors("row").FirstOrDefault();
            if (cell is not null)
            {
                cell.Remove();
                changed = true;
                row = row ?? cell.Parent;
            }

            if (row is not null && !row.Elements("cell").Any())
            {
                row.Remove();
            }
        }

        return changed;
    }

    private static ViewXmlUpdateResult UpdateViewFetchXml(string fetchXml, ViewUpdateSpec spec)
    {
        var document = XDocument.Parse(fetchXml, LoadOptions.PreserveWhitespace);
        var entity = document.Root?.Element("entity")
            ?? throw new InvalidOperationException("FetchXml does not contain a root entity node.");

        var changed = false;
        var addedColumns = new List<string>();
        var skippedColumns = new List<string>();
        var addedLinks = new List<string>();
        var appliedFilterCount = 0;
        var sortChanged = false;

        var linksByAlias = new Dictionary<string, XElement>(StringComparer.OrdinalIgnoreCase);
        foreach (var link in spec.Links)
        {
            var ensured = EnsureViewLinkEntity(entity, link, addedLinks, ref changed);
            if (!string.IsNullOrWhiteSpace(link.Alias))
            {
                linksByAlias[link.Alias!] = ensured;
            }

            if (link.Filters.Count > 0)
            {
                if (link.ReplaceFilters)
                {
                    ensured.Elements("filter").Remove();
                    changed = true;
                }

                foreach (var filter in link.Filters)
                {
                    ensured.Add(BuildFilterElement(filter));
                    appliedFilterCount += CountFilterConditions(filter);
                    changed = true;
                }
            }
        }

        if (spec.ReplaceColumns)
        {
            var removedAny = entity.Elements("attribute").Any();
            entity.Elements("attribute").Remove();
            foreach (var link in entity.Descendants("link-entity"))
            {
                removedAny |= link.Elements("attribute").Any();
                link.Elements("attribute").Remove();
            }
            changed |= removedAny;
        }

        foreach (var column in spec.Columns)
        {
            ValidateRequired(column.Name, "columns[].name");
            var targetEntity = ResolveViewColumnTarget(entity, linksByAlias, column);
            var existing = targetEntity.Elements("attribute").FirstOrDefault(attribute =>
                string.Equals((string?)attribute.Attribute("name"), column.Name, StringComparison.OrdinalIgnoreCase));
            var identifier = BuildViewColumnIdentifier(column);
            if (existing is not null)
            {
                skippedColumns.Add(identifier);
                continue;
            }

            targetEntity.AddFirst(new XElement("attribute", new XAttribute("name", column.Name)));
            addedColumns.Add(identifier);
            changed = true;
        }

        if (spec.Filters.Count > 0)
        {
            if (spec.ReplaceFilters)
            {
                entity.Elements("filter").Remove();
                changed = true;
            }

            foreach (var filter in spec.Filters)
            {
                entity.Add(BuildFilterElement(filter));
                appliedFilterCount += CountFilterConditions(filter);
                changed = true;
            }
        }

        if (spec.Sort.Count > 0)
        {
            if (spec.ReplaceSort)
            {
                entity.Descendants("order").Remove();
                changed = true;
            }

            foreach (var sort in spec.Sort)
            {
                var targetEntity = ResolveViewSortTarget(entity, linksByAlias, sort);
                var order = new XElement("order", new XAttribute("attribute", sort.Attribute));
                if (sort.Descending)
                {
                    order.SetAttributeValue("descending", "true");
                }
                targetEntity.Add(order);
                sortChanged = true;
                changed = true;
            }
        }

        return new ViewXmlUpdateResult(
            changed,
            document.ToString(SaveOptions.DisableFormatting),
            addedColumns,
            new List<string>(),
            skippedColumns,
            addedLinks,
            appliedFilterCount,
            sortChanged);
    }

    private static ViewXmlUpdateResult UpdateViewLayoutXml(string layoutXml, ViewUpdateSpec spec)
    {
        var document = XDocument.Parse(layoutXml, LoadOptions.PreserveWhitespace);
        var root = document.Root ?? throw new InvalidOperationException("LayoutXml does not contain a root node.");
        var row = root.Element("row")
            ?? throw new InvalidOperationException("LayoutXml does not contain a row node.");

        var changed = false;
        if (!string.IsNullOrWhiteSpace(spec.JumpColumn))
        {
            var jumpName = ResolveLayoutColumnName(spec.JumpColumn);
            if (!string.Equals((string?)root.Attribute("jump"), jumpName, StringComparison.OrdinalIgnoreCase))
            {
                root.SetAttributeValue("jump", jumpName);
                changed = true;
            }
        }

        if (spec.ReplaceColumns)
        {
            var hadCells = row.Elements("cell").Any();
            row.Elements("cell").Remove();
            changed |= hadCells;
        }

        var added = new List<string>();
        var updated = new List<string>();
        var skipped = new List<string>();
        var existingByName = row.Elements("cell")
            .Where(cell => !string.IsNullOrWhiteSpace((string?)cell.Attribute("name")))
            .ToDictionary(cell => ((string)cell.Attribute("name")!).Trim(), StringComparer.OrdinalIgnoreCase);

        foreach (var column in spec.Columns)
        {
            ValidateRequired(column.Name, "columns[].name");
            var cellName = ResolveLayoutColumnName(column);
            if (existingByName.TryGetValue(cellName, out var existing))
            {
                if (column.Width.HasValue
                    && !string.Equals((string?)existing.Attribute("width"), column.Width.Value.ToString(), StringComparison.Ordinal))
                {
                    existing.SetAttributeValue("width", column.Width.Value.ToString());
                    updated.Add(cellName);
                    changed = true;
                }
                else
                {
                    skipped.Add(cellName);
                }
                continue;
            }

            row.Add(new XElement(
                "cell",
                new XAttribute("name", cellName),
                new XAttribute("width", (column.Width ?? 150).ToString())));
            existingByName[cellName] = row.Elements("cell").Last();
            added.Add(cellName);
            changed = true;
        }

        return new ViewXmlUpdateResult(
            changed,
            document.ToString(SaveOptions.DisableFormatting),
            added,
            updated,
            skipped,
            new List<string>(),
            0,
            false);
    }

    private static XElement EnsureViewLinkEntity(
        XElement rootEntity,
        ViewLinkEntitySpec spec,
        List<string> addedLinks,
        ref bool changed)
    {
        ValidateRequired(spec.Name, "links[].name");
        ValidateRequired(spec.From, "links[].from");
        ValidateRequired(spec.To, "links[].to");

        var existing = rootEntity.Elements("link-entity").FirstOrDefault(link =>
            (!string.IsNullOrWhiteSpace(spec.Alias)
                && string.Equals((string?)link.Attribute("alias"), spec.Alias, StringComparison.OrdinalIgnoreCase))
            || (string.Equals((string?)link.Attribute("name"), spec.Name, StringComparison.OrdinalIgnoreCase)
                && string.Equals((string?)link.Attribute("from"), spec.From, StringComparison.OrdinalIgnoreCase)
                && string.Equals((string?)link.Attribute("to"), spec.To, StringComparison.OrdinalIgnoreCase)));
        if (existing is not null)
        {
            if (!string.IsNullOrWhiteSpace(spec.LinkType)
                && !string.Equals((string?)existing.Attribute("link-type"), spec.LinkType, StringComparison.OrdinalIgnoreCase))
            {
                existing.SetAttributeValue("link-type", spec.LinkType);
                changed = true;
            }
            if (!string.IsNullOrWhiteSpace(spec.Alias)
                && !string.Equals((string?)existing.Attribute("alias"), spec.Alias, StringComparison.OrdinalIgnoreCase))
            {
                existing.SetAttributeValue("alias", spec.Alias);
                changed = true;
            }
            return existing;
        }

        var created = new XElement(
            "link-entity",
            new XAttribute("name", spec.Name),
            new XAttribute("from", spec.From),
            new XAttribute("to", spec.To));
        if (!string.IsNullOrWhiteSpace(spec.Alias))
        {
            created.SetAttributeValue("alias", spec.Alias);
        }
        if (!string.IsNullOrWhiteSpace(spec.LinkType))
        {
            created.SetAttributeValue("link-type", spec.LinkType);
        }

        rootEntity.Add(created);
        addedLinks.Add(spec.Alias ?? spec.Name);
        changed = true;
        return created;
    }

    private static XElement ResolveViewColumnTarget(
        XElement rootEntity,
        Dictionary<string, XElement> linksByAlias,
        ViewColumnSpec column)
    {
        if (string.IsNullOrWhiteSpace(column.EntityAlias))
        {
            return rootEntity;
        }

        if (linksByAlias.TryGetValue(column.EntityAlias, out var link))
        {
            return link;
        }

        throw new InvalidOperationException(
            $"Column '{column.Name}' targets alias '{column.EntityAlias}', but no matching link was defined.");
    }

    private static XElement ResolveViewSortTarget(
        XElement rootEntity,
        Dictionary<string, XElement> linksByAlias,
        ViewSortSpec sort)
    {
        if (string.IsNullOrWhiteSpace(sort.EntityAlias))
        {
            return rootEntity;
        }

        if (linksByAlias.TryGetValue(sort.EntityAlias, out var link))
        {
            return link;
        }

        throw new InvalidOperationException(
            $"Sort on '{sort.Attribute}' targets alias '{sort.EntityAlias}', but no matching link was defined.");
    }

    private static XElement BuildFilterElement(ViewFilterSpec filter)
    {
        var type = string.IsNullOrWhiteSpace(filter.Type) ? "and" : filter.Type.Trim().ToLowerInvariant();
        if (type is not ("and" or "or"))
        {
            throw new InvalidOperationException($"Unsupported filter type '{filter.Type}'. Use and or or.");
        }

        var element = new XElement("filter", new XAttribute("type", type));
        foreach (var condition in filter.Conditions)
        {
            ValidateRequired(condition.Attribute, "filter.condition.attribute");
            var conditionElement = new XElement(
                "condition",
                new XAttribute("attribute", condition.Attribute),
                new XAttribute("operator", NormalizeFilterOperator(condition.Operator)));

            if (condition.Values.Count > 0)
            {
                foreach (var value in condition.Values)
                {
                    conditionElement.Add(new XElement("value", value));
                }
            }
            else if (condition.Value is not null)
            {
                conditionElement.SetAttributeValue("value", condition.Value);
            }

            element.Add(conditionElement);
        }

        foreach (var child in filter.Filters)
        {
            element.Add(BuildFilterElement(child));
        }

        return element;
    }

    private static int CountFilterConditions(ViewFilterSpec filter)
    {
        return filter.Conditions.Count + filter.Filters.Sum(CountFilterConditions);
    }

    private static string NormalizeFilterOperator(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? "eq" : value.Trim().ToLowerInvariant();
    }

    private static string BuildViewColumnIdentifier(ViewColumnSpec column)
    {
        return string.IsNullOrWhiteSpace(column.EntityAlias)
            ? column.Name
            : $"{column.EntityAlias}.{column.Name}";
    }

    private static string ResolveLayoutColumnName(ViewColumnSpec column)
    {
        if (!string.IsNullOrWhiteSpace(column.LayoutName))
        {
            return column.LayoutName.Trim();
        }

        return ResolveLayoutColumnName(BuildViewColumnIdentifier(column));
    }

    private static string ResolveLayoutColumnName(string name)
    {
        return name.Trim();
    }

    private static string CreateInternalName(string? label, string prefix)
    {
        if (!string.IsNullOrWhiteSpace(label))
        {
            var normalized = new string(label
                .Trim()
                .ToLowerInvariant()
                .Select(ch => char.IsLetterOrDigit(ch) ? ch : '_')
                .ToArray())
                .Trim('_');
            if (!string.IsNullOrWhiteSpace(normalized))
            {
                return $"{prefix}_{normalized}";
            }
        }

        return $"{prefix}_{Guid.NewGuid():N}";
    }

    private static List<string> DistinctOrdered(IEnumerable<string> values)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var result = new List<string>();
        foreach (var value in values)
        {
            if (string.IsNullOrWhiteSpace(value) || !seen.Add(value))
            {
                continue;
            }

            result.Add(value);
        }

        return result;
    }
}
