using System.Text.Json;
using System.Xml.Linq;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Metadata;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static readonly JsonSerializerOptions InputJsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private static int RunMetadata(string subcommand, Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var specText = Require(options, "spec");

        var result = subcommand switch
        {
            "create-table" => ExecuteCreateTable(client, DeserializeSpec<TableCreateSpec>(specText, "table")),
            "create-field" => ExecuteCreateField(client, DeserializeSpec<AttributeCreateSpec>(specText, "field")),
            "create-lookup" => ExecuteCreateLookup(client, DeserializeSpec<LookupCreateSpec>(specText, "lookup")),
            "set-table-icon" => ExecuteSetTableIcon(client, DeserializeSpec<TableIconSpec>(specText, "table icon")),
            "update-main-form" => ExecuteUpdateMainForm(client, DeserializeSpec<FormUpdateSpec>(specText, "main form")),
            "patch-form-xml" => ExecutePatchFormXml(client, DeserializeSpec<FormXmlPatchSpec>(specText, "form XML patch")),
            "patch-form-ribbon" => ExecutePatchFormRibbon(client, DeserializeSpec<FormRibbonPatchSpec>(specText, "form ribbon patch")),
            "update-form-events" => ExecuteUpdateFormEvents(client, DeserializeSpec<FormEventUpdateSpec>(specText, "form events")),
            "update-view" => ExecuteUpdateView(client, DeserializeSpec<ViewUpdateSpec>(specText, "view")),
            "bind-pcf-control" => ExecuteBindPcfControl(client, DeserializeSpec<PcfBindingSpec>(specText, "PCF binding")),
            _ => throw new InvalidOperationException(
                $"Unsupported metadata subcommand '{subcommand}'. Use create-table, create-field, create-lookup, set-table-icon, update-main-form, patch-form-xml, patch-form-ribbon, update-form-events, update-view, or bind-pcf-control."),
        };

        Console.WriteLine(JsonSerializer.Serialize(result, JsonOptions));
        return 0;
    }

    private static T DeserializeSpec<T>(string text, string label)
    {
        var spec = JsonSerializer.Deserialize<T>(text, InputJsonOptions);
        return spec ?? throw new InvalidOperationException($"Expected a JSON object for metadata {label} spec.");
    }

    private static object ExecuteCreateTable(ServiceClient client, TableCreateSpec spec)
    {
        ValidateRequired(spec.SchemaName, "schemaName");
        ValidateRequired(spec.DisplayName, "displayName");
        ValidateRequired(spec.PluralDisplayName, "pluralDisplayName");
        ValidateRequired(spec.PrimaryName.SchemaName, "primaryName.schemaName");
        ValidateRequired(spec.PrimaryName.DisplayName, "primaryName.displayName");

        var logicalName = NormalizeLogicalName(spec.LogicalName ?? spec.SchemaName);
        var primaryLogicalName = NormalizeLogicalName(spec.PrimaryName.LogicalName ?? spec.PrimaryName.SchemaName);
        var entity = new EntityMetadata
        {
            SchemaName = spec.SchemaName,
            LogicalName = logicalName,
            DisplayName = Localized(spec.DisplayName),
            DisplayCollectionName = Localized(spec.PluralDisplayName),
            Description = LocalizedOrNull(spec.Description),
            OwnershipType = ParseOwnershipType(spec.OwnershipType),
        };
        if (spec.EnableAudit.HasValue)
        {
            entity.IsAuditEnabled = new BooleanManagedProperty(spec.EnableAudit.Value);
        }

        var primaryName = new StringAttributeMetadata
        {
            SchemaName = spec.PrimaryName.SchemaName,
            LogicalName = primaryLogicalName,
            DisplayName = Localized(spec.PrimaryName.DisplayName),
            Description = LocalizedOrNull(spec.PrimaryName.Description),
            RequiredLevel = new AttributeRequiredLevelManagedProperty(ParseRequiredLevel(spec.PrimaryName.RequiredLevel)),
            MaxLength = spec.PrimaryName.MaxLength ?? 100,
            Format = StringFormat.Text,
        };

        var response = (CreateEntityResponse)client.Execute(new CreateEntityRequest
        {
            Entity = entity,
            PrimaryAttribute = primaryName,
            HasActivities = spec.HasActivities,
            HasNotes = spec.HasNotes,
            HasFeedback = spec.HasFeedback,
            SolutionUniqueName = spec.SolutionUniqueName,
        });

        return new
        {
            success = true,
            mode = "create-table",
            logicalName,
            schemaName = spec.SchemaName,
            displayName = spec.DisplayName,
            pluralDisplayName = spec.PluralDisplayName,
            ownershipType = entity.OwnershipType?.ToString(),
            entityId = response.EntityId,
            primaryAttributeId = response.AttributeId,
            solutionUniqueName = spec.SolutionUniqueName,
        };
    }

    private static object ExecuteCreateField(ServiceClient client, AttributeCreateSpec spec)
    {
        ValidateRequired(spec.TableLogicalName, "tableLogicalName");
        ValidateRequired(spec.Type, "type");
        ValidateRequired(spec.SchemaName, "schemaName");
        ValidateRequired(spec.DisplayName, "displayName");

        var attribute = BuildAttributeMetadata(spec);
        var logicalName = NormalizeLogicalName(spec.LogicalName ?? spec.SchemaName);

        var response = (CreateAttributeResponse)client.Execute(new CreateAttributeRequest
        {
            EntityName = spec.TableLogicalName,
            Attribute = attribute,
            SolutionUniqueName = spec.SolutionUniqueName,
        });

        return new
        {
            success = true,
            mode = "create-field",
            tableLogicalName = spec.TableLogicalName,
            logicalName,
            schemaName = spec.SchemaName,
            displayName = spec.DisplayName,
            fieldType = spec.Type,
            attributeId = response.AttributeId,
            solutionUniqueName = spec.SolutionUniqueName,
        };
    }

    private static object ExecuteCreateLookup(ServiceClient client, LookupCreateSpec spec)
    {
        ValidateRequired(spec.ReferencingEntity, "referencingEntity");
        ValidateRequired(spec.ReferencedEntity, "referencedEntity");
        ValidateRequired(spec.RelationshipSchemaName, "relationshipSchemaName");
        ValidateRequired(spec.LookupSchemaName, "lookupSchemaName");
        ValidateRequired(spec.DisplayName, "displayName");

        var lookupLogicalName = NormalizeLogicalName(spec.LookupLogicalName ?? spec.LookupSchemaName);
        var referencedAttribute = ResolveReferencedAttribute(client, spec.ReferencedEntity, spec.ReferencedAttribute);

        var response = (CreateOneToManyResponse)client.Execute(new CreateOneToManyRequest
        {
            Lookup = new LookupAttributeMetadata
            {
                SchemaName = spec.LookupSchemaName,
                LogicalName = lookupLogicalName,
                DisplayName = Localized(spec.DisplayName),
                Description = LocalizedOrNull(spec.Description),
                RequiredLevel = new AttributeRequiredLevelManagedProperty(ParseRequiredLevel(spec.RequiredLevel)),
            },
            OneToManyRelationship = new OneToManyRelationshipMetadata
            {
                SchemaName = spec.RelationshipSchemaName,
                ReferencingEntity = spec.ReferencingEntity,
                ReferencedEntity = spec.ReferencedEntity,
                ReferencedAttribute = referencedAttribute,
                AssociatedMenuConfiguration = new AssociatedMenuConfiguration
                {
                    Behavior = ParseAssociatedMenuBehavior(spec.AssociatedMenuBehavior),
                    Group = ParseAssociatedMenuGroup(spec.AssociatedMenuGroup),
                    Label = Localized(spec.AssociatedMenuLabel ?? spec.DisplayName),
                    Order = spec.AssociatedMenuOrder ?? 10000,
                },
                CascadeConfiguration = BuildCascadeConfiguration(spec.Cascade),
            },
            SolutionUniqueName = spec.SolutionUniqueName,
        });

        return new
        {
            success = true,
            mode = "create-lookup",
            referencingEntity = spec.ReferencingEntity,
            referencedEntity = spec.ReferencedEntity,
            referencedAttribute,
            lookupLogicalName,
            lookupSchemaName = spec.LookupSchemaName,
            relationshipSchemaName = spec.RelationshipSchemaName,
            attributeId = response.AttributeId,
            relationshipId = response.RelationshipId,
            solutionUniqueName = spec.SolutionUniqueName,
        };
    }

    private static object ExecuteSetTableIcon(ServiceClient client, TableIconSpec spec)
    {
        ValidateRequired(spec.TableLogicalName, "tableLogicalName");
        if (string.IsNullOrWhiteSpace(spec.IconVectorName)
            && string.IsNullOrWhiteSpace(spec.IconSmallName)
            && string.IsNullOrWhiteSpace(spec.IconLargeName))
        {
            throw new InvalidOperationException(
                "At least one of iconVectorName, iconSmallName, or iconLargeName is required.");
        }

        var metadata = new EntityMetadata
        {
            LogicalName = spec.TableLogicalName,
            IconVectorName = EmptyToNull(spec.IconVectorName),
            IconSmallName = EmptyToNull(spec.IconSmallName),
            IconLargeName = EmptyToNull(spec.IconLargeName),
        };

        client.Execute(new UpdateEntityRequest
        {
            Entity = metadata,
            SolutionUniqueName = spec.SolutionUniqueName,
            MergeLabels = false,
        });

        return new
        {
            success = true,
            mode = "set-table-icon",
            tableLogicalName = spec.TableLogicalName,
            iconVectorName = metadata.IconVectorName,
            iconSmallName = metadata.IconSmallName,
            iconLargeName = metadata.IconLargeName,
            solutionUniqueName = spec.SolutionUniqueName,
        };
    }

    private static object ExecuteUpdateMainForm(ServiceClient client, FormUpdateSpec spec)
    {
        ValidateRequired(spec.EntityLogicalName, "entityLogicalName");
        ValidateRequired(spec.FormName, "formName");
        if (spec.FieldLogicalNames.Count == 0 && !spec.CreateTabIfMissing && !spec.CreateSectionIfMissing)
        {
            throw new InvalidOperationException(
                "Provide at least one fieldLogicalNames entry, or enable createTabIfMissing or createSectionIfMissing.");
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
        var updated = AddFieldsToFormXml(formXml, spec);
        if (!updated.Changed)
        {
            return new
            {
                success = true,
                mode = "update-main-form",
                formId = form.Id,
                entityLogicalName = spec.EntityLogicalName,
                formName = spec.FormName,
                addedFields = Array.Empty<string>(),
                movedFields = Array.Empty<string>(),
                skippedFields = updated.SkippedFields,
                createdTabs = Array.Empty<string>(),
                createdSections = Array.Empty<string>(),
                message = "No form layout changes were needed.",
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
            mode = "update-main-form",
            formId = form.Id,
            entityLogicalName = spec.EntityLogicalName,
            formName = spec.FormName,
            addedFields = updated.AddedFields,
            movedFields = updated.MovedFields,
            skippedFields = updated.SkippedFields,
            createdTabs = updated.CreatedTabs,
            createdSections = updated.CreatedSections,
        };
    }

    private static object ExecuteUpdateView(ServiceClient client, ViewUpdateSpec spec)
    {
        ValidateRequired(spec.EntityLogicalName, "entityLogicalName");
        ValidateRequired(spec.ViewName, "viewName");
        if (spec.Columns.Count == 0 && spec.Sort.Count == 0 && spec.Filters.Count == 0 && spec.Links.Count == 0
            && string.IsNullOrWhiteSpace(spec.JumpColumn))
        {
            throw new InvalidOperationException(
                "Provide at least one column, sort, filter, link, or jumpColumn change for view updates.");
        }

        var view = RetrieveSingle(
            client,
            "savedquery",
            new ColumnSet("fetchxml", "layoutxml", "name", "returnedtypecode"),
            new ConditionExpression("returnedtypecode", ConditionOperator.Equal, spec.EntityLogicalName),
            new ConditionExpression("name", ConditionOperator.Equal, spec.ViewName));

        var fetchXml = view.GetAttributeValue<string>("fetchxml")
            ?? throw new InvalidOperationException($"View '{spec.ViewName}' does not contain fetchxml.");
        var layoutXml = view.GetAttributeValue<string>("layoutxml")
            ?? throw new InvalidOperationException($"View '{spec.ViewName}' does not contain layoutxml.");

        var fetchUpdate = UpdateFetchXml(fetchXml, spec);
        var layoutUpdate = UpdateLayoutXml(layoutXml, spec);
        if (!fetchUpdate.Changed && !layoutUpdate.Changed)
        {
            return new
            {
                success = true,
                mode = "update-view",
                viewId = view.Id,
                entityLogicalName = spec.EntityLogicalName,
                viewName = spec.ViewName,
                addedColumns = Array.Empty<string>(),
                updatedColumns = Array.Empty<string>(),
                skippedColumns = layoutUpdate.SkippedColumns,
                addedLinks = Array.Empty<string>(),
                appliedFilterCount = 0,
                sortChanged = false,
                message = "No view changes were needed.",
            };
        }

        var patch = new Entity("savedquery", view.Id)
        {
            ["fetchxml"] = fetchUpdate.Xml,
            ["layoutxml"] = layoutUpdate.Xml,
        };
        client.Update(patch);

        return new
        {
            success = true,
            mode = "update-view",
            viewId = view.Id,
            entityLogicalName = spec.EntityLogicalName,
            viewName = spec.ViewName,
            addedColumns = DistinctOrdered(fetchUpdate.AddedColumns.Concat(layoutUpdate.AddedColumns)),
            updatedColumns = DistinctOrdered(fetchUpdate.UpdatedColumns.Concat(layoutUpdate.UpdatedColumns)),
            skippedColumns = DistinctOrdered(fetchUpdate.SkippedColumns.Concat(layoutUpdate.SkippedColumns)),
            addedLinks = fetchUpdate.AddedLinks,
            appliedFilterCount = fetchUpdate.AppliedFilterCount,
            sortChanged = fetchUpdate.SortChanged,
        };
    }

    private static object ExecuteUpdateFormEvents(ServiceClient client, FormEventUpdateSpec spec)
    {
        ValidateRequired(spec.EntityLogicalName, "entityLogicalName");
        ValidateRequired(spec.FormName, "formName");
        if (spec.Libraries.Count == 0 && spec.OnLoad.Count == 0 && spec.OnSave.Count == 0 && spec.OnChange.Count == 0)
        {
            throw new InvalidOperationException(
                "Form event update requires at least one library, onLoad handler, onSave handler, or onChange handler.");
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
        var updated = UpdateFormEventsXml(formXml, spec);
        if (!updated.Changed)
        {
            return new
            {
                success = true,
                mode = "update-form-events",
                formId = form.Id,
                entityLogicalName = spec.EntityLogicalName,
                formName = spec.FormName,
                addedLibraries = Array.Empty<string>(),
                addedHandlers = Array.Empty<string>(),
                updatedHandlers = Array.Empty<string>(),
                skippedHandlers = updated.SkippedHandlers,
                message = "No form event changes were needed.",
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
            mode = "update-form-events",
            formId = form.Id,
            entityLogicalName = spec.EntityLogicalName,
            formName = spec.FormName,
            addedLibraries = updated.AddedLibraries,
            addedHandlers = updated.AddedHandlers,
            updatedHandlers = updated.UpdatedHandlers,
            skippedHandlers = updated.SkippedHandlers,
        };
    }

    private static AttributeMetadata BuildAttributeMetadata(AttributeCreateSpec spec)
    {
        var logicalName = NormalizeLogicalName(spec.LogicalName ?? spec.SchemaName);
        var requiredLevel = new AttributeRequiredLevelManagedProperty(ParseRequiredLevel(spec.RequiredLevel));
        AttributeMetadata attribute = spec.Type.Trim().ToLowerInvariant() switch
        {
            "string" => new StringAttributeMetadata
            {
                MaxLength = spec.MaxLength ?? 100,
                Format = ParseStringFormat(spec.StringFormat),
            },
            "memo" => new MemoAttributeMetadata
            {
                MaxLength = spec.MaxLength ?? 4000,
                Format = StringFormat.TextArea,
            },
            "integer" => new IntegerAttributeMetadata
            {
                MinValue = spec.MinValueInt,
                MaxValue = spec.MaxValueInt,
                Format = ParseIntegerFormat(spec.IntegerFormat),
            },
            "decimal" => new DecimalAttributeMetadata
            {
                MinValue = spec.MinValueDecimal,
                MaxValue = spec.MaxValueDecimal,
                Precision = spec.Precision ?? 2,
            },
            "money" => new MoneyAttributeMetadata
            {
                MinValue = spec.MinValueDecimal.HasValue ? (double?)spec.MinValueDecimal.Value : null,
                MaxValue = spec.MaxValueDecimal.HasValue ? (double?)spec.MaxValueDecimal.Value : null,
                Precision = spec.Precision ?? 2,
            },
            "boolean" => BuildBooleanAttribute(spec),
            "datetime" => new DateTimeAttributeMetadata
            {
                Format = ParseDateTimeFormat(spec.DateTimeFormat),
                DateTimeBehavior = ParseDateTimeBehavior(spec.DateTimeBehavior),
            },
            "choice" => BuildPicklistAttribute(spec),
            _ => throw new InvalidOperationException(
                $"Unsupported field type '{spec.Type}'. Supported types: string, memo, integer, decimal, money, boolean, datetime, choice."),
        };

        attribute.SchemaName = spec.SchemaName;
        attribute.LogicalName = logicalName;
        attribute.DisplayName = Localized(spec.DisplayName);
        attribute.Description = LocalizedOrNull(spec.Description);
        attribute.RequiredLevel = requiredLevel;
        if (spec.EnableAudit.HasValue)
        {
            attribute.IsAuditEnabled = new BooleanManagedProperty(spec.EnableAudit.Value);
        }
        if (spec.IsSecured.HasValue)
        {
            attribute.IsSecured = spec.IsSecured.Value;
        }

        return attribute;
    }

    private static BooleanAttributeMetadata BuildBooleanAttribute(AttributeCreateSpec spec)
    {
        var optionSet = new BooleanOptionSetMetadata(
            new OptionMetadata(Localized(spec.TrueLabel ?? "Yes"), 1),
            new OptionMetadata(Localized(spec.FalseLabel ?? "No"), 0));

        return new BooleanAttributeMetadata(optionSet)
        {
            DefaultValue = spec.DefaultBooleanValue,
        };
    }

    private static PicklistAttributeMetadata BuildPicklistAttribute(AttributeCreateSpec spec)
    {
        if (spec.Options.Count == 0)
        {
            throw new InvalidOperationException("Choice fields require a non-empty 'options' collection.");
        }

        var optionSet = new OptionSetMetadata
        {
            IsGlobal = false,
            OptionSetType = OptionSetType.Picklist,
        };

        var nextValue = spec.OptionValueSeed ?? 100000000;
        foreach (var option in spec.Options)
        {
            ValidateRequired(option.Label, "options[].label");
            var value = option.Value ?? nextValue++;
            optionSet.Options.Add(new OptionMetadata(Localized(option.Label), value));
        }

        return new PicklistAttributeMetadata
        {
            OptionSet = optionSet,
        };
    }

    private static string ResolveReferencedAttribute(ServiceClient client, string referencedEntity, string? explicitAttribute)
    {
        if (!string.IsNullOrWhiteSpace(explicitAttribute))
        {
            return explicitAttribute;
        }

        var response = (RetrieveEntityResponse)client.Execute(new RetrieveEntityRequest
        {
            LogicalName = referencedEntity,
            EntityFilters = EntityFilters.Entity,
            RetrieveAsIfPublished = true,
        });

        return response.EntityMetadata.PrimaryIdAttribute
            ?? throw new InvalidOperationException(
                $"Could not resolve the primary ID attribute for referenced entity '{referencedEntity}'.");
    }

    private static Entity RetrieveSingle(
        ServiceClient client,
        string entityName,
        ColumnSet columns,
        params ConditionExpression[] conditions)
    {
        var query = new QueryExpression(entityName)
        {
            ColumnSet = columns,
            TopCount = 2,
        };
        foreach (var condition in conditions)
        {
            query.Criteria.AddCondition(condition);
        }

        var results = client.RetrieveMultiple(query).Entities;
        if (results.Count == 0)
        {
            throw new InvalidOperationException($"No {entityName} record matched the requested filters.");
        }

        if (results.Count > 1)
        {
            throw new InvalidOperationException($"More than one {entityName} record matched the requested filters.");
        }

        return results[0];
    }

    private static FormXmlUpdateResult AddFieldsToFormXml(string formXml, FormUpdateSpec spec)
    {
        return UpdateMainFormLayoutXml(formXml, spec);
    }

    private static FormEventXmlUpdateResult UpdateFormEventsXml(string formXml, FormEventUpdateSpec spec)
    {
        var document = XDocument.Parse(formXml, LoadOptions.PreserveWhitespace);
        var form = document.Root ?? throw new InvalidOperationException("Form XML does not contain a root form node.");
        var librariesElement = EnsureDirectChild(form, "formLibraries");
        var eventsElement = EnsureDirectChild(form, "events");

        var addedLibraries = new List<string>();
        var requestedLibraries = BuildRequestedLibraries(spec);
        foreach (var library in requestedLibraries)
        {
            EnsureFormLibrary(librariesElement, library, addedLibraries);
        }

        var addedHandlers = new List<string>();
        var updatedHandlers = new List<string>();
        var skippedHandlers = new List<string>();

        var changed = addedLibraries.Count > 0;
        changed |= UpsertFormEventHandlers(
            eventsElement,
            eventName: "onload",
            attributeName: null,
            handlers: spec.OnLoad,
            behaviorInBulkEditForm: spec.OnLoadBehaviorInBulkEditForm,
            addedHandlers,
            updatedHandlers,
            skippedHandlers);
        changed |= UpsertFormEventHandlers(
            eventsElement,
            eventName: "onsave",
            attributeName: null,
            handlers: spec.OnSave,
            behaviorInBulkEditForm: null,
            addedHandlers,
            updatedHandlers,
            skippedHandlers);

        foreach (var onChange in spec.OnChange)
        {
            ValidateRequired(onChange.Attribute, "onChange[].attribute");
            if (onChange.Handlers.Count == 0)
            {
                throw new InvalidOperationException($"onChange entry for '{onChange.Attribute}' must contain at least one handler.");
            }

            changed |= UpsertFormEventHandlers(
                eventsElement,
                eventName: "onchange",
                attributeName: NormalizeLogicalName(onChange.Attribute),
                handlers: onChange.Handlers,
                behaviorInBulkEditForm: null,
                addedHandlers,
                updatedHandlers,
                skippedHandlers);
        }

        return new FormEventXmlUpdateResult(
            changed,
            document.ToString(SaveOptions.DisableFormatting),
            addedLibraries,
            addedHandlers,
            updatedHandlers,
            skippedHandlers);
    }

    private static XElement FindTab(XDocument document, FormUpdateSpec spec)
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

        throw new InvalidOperationException("Could not locate the requested form tab.");
    }

    private static XElement FindSection(XElement tab, FormUpdateSpec spec)
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

        throw new InvalidOperationException("Could not locate the requested form section.");
    }

    private static XElement EnsureDirectChild(XElement parent, string elementName)
    {
        var child = parent.Element(elementName);
        if (child is not null)
        {
            return child;
        }

        child = new XElement(elementName);
        parent.Add(child);
        return child;
    }

    private static List<FormLibrarySpec> BuildRequestedLibraries(FormEventUpdateSpec spec)
    {
        var libraries = new Dictionary<string, FormLibrarySpec>(StringComparer.OrdinalIgnoreCase);

        foreach (var library in spec.Libraries)
        {
            ValidateRequired(library.Name, "libraries[].name");
            libraries[library.Name] = library;
        }

        foreach (var handler in EnumerateFormHandlers(spec))
        {
            ValidateRequired(handler.LibraryName, "handler.libraryName");
            ValidateRequired(handler.FunctionName, "handler.functionName");
            if (!libraries.ContainsKey(handler.LibraryName))
            {
                libraries[handler.LibraryName] = new FormLibrarySpec
                {
                    Name = handler.LibraryName,
                };
            }
        }

        return libraries.Values.ToList();
    }

    private static IEnumerable<FormHandlerSpec> EnumerateFormHandlers(FormEventUpdateSpec spec)
    {
        foreach (var handler in spec.OnLoad)
        {
            yield return handler;
        }

        foreach (var handler in spec.OnSave)
        {
            yield return handler;
        }

        foreach (var onChange in spec.OnChange)
        {
            foreach (var handler in onChange.Handlers)
            {
                yield return handler;
            }
        }
    }

    private static XElement EnsureFormLibrary(XElement librariesElement, FormLibrarySpec spec, List<string> addedLibraries)
    {
        var existing = librariesElement
            .Elements("Library")
            .FirstOrDefault(candidate => string.Equals(
                (string?)candidate.Attribute("name"),
                spec.Name,
                StringComparison.OrdinalIgnoreCase));
        if (existing is not null)
        {
            return existing;
        }

        var library = new XElement(
            "Library",
            new XAttribute("name", spec.Name),
            new XAttribute("libraryUniqueId", spec.LibraryUniqueId ?? Guid.NewGuid().ToString("D")));
        librariesElement.Add(library);
        addedLibraries.Add(spec.Name);
        return library;
    }

    private static bool UpsertFormEventHandlers(
        XElement eventsElement,
        string eventName,
        string? attributeName,
        List<FormHandlerSpec> handlers,
        string? behaviorInBulkEditForm,
        List<string> addedHandlers,
        List<string> updatedHandlers,
        List<string> skippedHandlers)
    {
        if (handlers.Count == 0 && string.IsNullOrWhiteSpace(behaviorInBulkEditForm))
        {
            return false;
        }

        var changed = false;
        var eventElement = FindFormEvent(eventsElement, eventName, attributeName);
        if (eventElement is null)
        {
            eventElement = new XElement(
                "event",
                new XAttribute("name", eventName),
                new XAttribute("application", "true"),
                new XAttribute("active", "true"));
            if (!string.IsNullOrWhiteSpace(attributeName))
            {
                eventElement.SetAttributeValue("attribute", attributeName);
            }

            eventsElement.Add(eventElement);
            changed = true;
        }

        if (!string.IsNullOrWhiteSpace(behaviorInBulkEditForm)
            && !string.Equals(
                (string?)eventElement.Attribute("BehaviorInBulkEditForm"),
                behaviorInBulkEditForm,
                StringComparison.OrdinalIgnoreCase))
        {
            eventElement.SetAttributeValue("BehaviorInBulkEditForm", behaviorInBulkEditForm);
            changed = true;
        }

        var handlersElement = eventElement.Element("Handlers");
        if (handlersElement is null)
        {
            handlersElement = new XElement("Handlers");
            eventElement.Add(handlersElement);
            changed = true;
        }

        foreach (var handler in handlers)
        {
            ValidateRequired(handler.LibraryName, "handler.libraryName");
            ValidateRequired(handler.FunctionName, "handler.functionName");

            var identifier = BuildHandlerIdentifier(eventName, attributeName, handler);
            var existing = handlersElement
                .Elements("Handler")
                .FirstOrDefault(candidate =>
                    string.Equals((string?)candidate.Attribute("libraryName"), handler.LibraryName, StringComparison.OrdinalIgnoreCase)
                    && string.Equals((string?)candidate.Attribute("functionName"), handler.FunctionName, StringComparison.OrdinalIgnoreCase));

            if (existing is null)
            {
                handlersElement.Add(CreateFormHandlerElement(handler));
                addedHandlers.Add(identifier);
                changed = true;
                continue;
            }

            if (UpdateFormHandlerElement(existing, handler))
            {
                updatedHandlers.Add(identifier);
                changed = true;
            }
            else
            {
                skippedHandlers.Add(identifier);
            }
        }

        return changed;
    }

    private static XElement? FindFormEvent(XElement eventsElement, string eventName, string? attributeName)
    {
        return eventsElement
            .Elements("event")
            .FirstOrDefault(candidate =>
                string.Equals((string?)candidate.Attribute("name"), eventName, StringComparison.OrdinalIgnoreCase)
                && string.Equals(
                    NormalizeAttributeValue((string?)candidate.Attribute("attribute")),
                    NormalizeAttributeValue(attributeName),
                    StringComparison.OrdinalIgnoreCase));
    }

    private static XElement CreateFormHandlerElement(FormHandlerSpec handler)
    {
        var element = new XElement(
            "Handler",
            new XAttribute("functionName", handler.FunctionName),
            new XAttribute("libraryName", handler.LibraryName),
            new XAttribute("handlerUniqueId", handler.HandlerUniqueId ?? Guid.NewGuid().ToString("D")),
            new XAttribute("enabled", (handler.Enabled ?? true).ToString().ToLowerInvariant()),
            new XAttribute("passExecutionContext", (handler.PassExecutionContext ?? true).ToString().ToLowerInvariant()));

        if (handler.Parameters is not null)
        {
            element.SetAttributeValue("parameters", handler.Parameters);
        }

        if (handler.Dependencies is not null)
        {
            SetHandlerDependencies(element, handler.Dependencies);
        }

        return element;
    }

    private static bool UpdateFormHandlerElement(XElement element, FormHandlerSpec handler)
    {
        var changed = false;

        changed |= SetAttributeIfDifferent(element, "libraryName", handler.LibraryName);
        changed |= SetAttributeIfDifferent(element, "functionName", handler.FunctionName);

        if (!string.IsNullOrWhiteSpace(handler.HandlerUniqueId))
        {
            changed |= SetAttributeIfDifferent(element, "handlerUniqueId", handler.HandlerUniqueId);
        }

        if (handler.Enabled.HasValue)
        {
            changed |= SetAttributeIfDifferent(element, "enabled", handler.Enabled.Value.ToString().ToLowerInvariant());
        }

        if (handler.PassExecutionContext.HasValue)
        {
            changed |= SetAttributeIfDifferent(
                element,
                "passExecutionContext",
                handler.PassExecutionContext.Value.ToString().ToLowerInvariant());
        }

        if (handler.Parameters is not null)
        {
            changed |= SetAttributeIfDifferent(element, "parameters", handler.Parameters, removeWhenEmpty: true);
        }

        if (handler.Dependencies is not null)
        {
            changed |= SetHandlerDependencies(element, handler.Dependencies);
        }

        return changed;
    }

    private static bool SetHandlerDependencies(XElement handlerElement, IReadOnlyCollection<string> dependencies)
    {
        var existing = handlerElement.Element("dependencies");
        var normalized = dependencies
            .Where(dependency => !string.IsNullOrWhiteSpace(dependency))
            .Select(dependency => dependency.Trim())
            .ToList();

        if (normalized.Count == 0)
        {
            if (existing is null)
            {
                return false;
            }

            existing.Remove();
            return true;
        }

        var replacement = new XElement(
            "dependencies",
            normalized.Select(dependency => new XElement("dependency", new XAttribute("id", dependency))));
        if (existing is not null && XNode.DeepEquals(existing, replacement))
        {
            return false;
        }

        existing?.Remove();
        handlerElement.Add(replacement);
        return true;
    }

    private static bool SetAttributeIfDifferent(XElement element, string attributeName, string? value, bool removeWhenEmpty = false)
    {
        var current = (string?)element.Attribute(attributeName);
        if (string.IsNullOrWhiteSpace(value) && removeWhenEmpty)
        {
            if (current is null)
            {
                return false;
            }

            element.Attribute(attributeName)?.Remove();
            return true;
        }

        if (string.Equals(current, value, StringComparison.Ordinal))
        {
            return false;
        }

        element.SetAttributeValue(attributeName, value);
        return true;
    }

    private static string BuildHandlerIdentifier(string eventName, string? attributeName, FormHandlerSpec handler)
    {
        var target = string.IsNullOrWhiteSpace(attributeName) ? eventName : $"{eventName}:{attributeName}";
        return $"{target} => {handler.LibraryName}::{handler.FunctionName}";
    }

    private static string? NormalizeAttributeValue(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim().ToLowerInvariant();
    }

    private static XElement CreateFormRow(string fieldLogicalName)
    {
        return new XElement(
            "row",
            new XElement(
                "cell",
                new XAttribute("id", Guid.NewGuid().ToString("D")),
                new XAttribute("showlabel", "true"),
                new XAttribute("locklevel", "0"),
                new XElement(
                    "labels",
                    new XElement(
                        "label",
                        new XAttribute("description", fieldLogicalName),
                        new XAttribute("languagecode", "1033"))),
                new XElement(
                    "control",
                    new XAttribute("id", fieldLogicalName),
                    new XAttribute("classid", "{4273EDBD-AC1D-40d3-9FB2-095C621B552D}"),
                    new XAttribute("datafieldname", fieldLogicalName),
                    new XAttribute("disabled", "false"))));
    }

    private static ViewXmlUpdateResult UpdateFetchXml(string fetchXml, ViewUpdateSpec spec)
    {
        return UpdateViewFetchXml(fetchXml, spec);
    }

    private static ViewXmlUpdateResult UpdateLayoutXml(string layoutXml, ViewUpdateSpec spec)
    {
        return UpdateViewLayoutXml(layoutXml, spec);
    }

    private static bool MatchesAttribute(XElement element, string attributeName, string? expected)
    {
        return !string.IsNullOrWhiteSpace(expected)
               && string.Equals((string?)element.Attribute(attributeName), expected, StringComparison.OrdinalIgnoreCase);
    }

    private static bool MatchesLabel(XElement element, string? expected)
    {
        return !string.IsNullOrWhiteSpace(expected)
               && element
                   .Descendants("label")
                   .Any(label => string.Equals(
                       (string?)label.Attribute("description"),
                       expected,
                       StringComparison.OrdinalIgnoreCase));
    }

    private static OwnershipTypes ParseOwnershipType(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "user" or "userowned" => OwnershipTypes.UserOwned,
            "organization" or "organizationowned" => OwnershipTypes.OrganizationOwned,
            "team" or "teamowned" => OwnershipTypes.TeamOwned,
            _ => throw new InvalidOperationException(
                $"Unsupported ownership type '{rawValue}'. Use userowned or organizationowned."),
        };
    }

    private static AttributeRequiredLevel ParseRequiredLevel(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "none" or "optional" => AttributeRequiredLevel.None,
            "recommended" => AttributeRequiredLevel.Recommended,
            "applicationrequired" or "required" => AttributeRequiredLevel.ApplicationRequired,
            "systemrequired" => AttributeRequiredLevel.SystemRequired,
            _ => throw new InvalidOperationException(
                $"Unsupported required level '{rawValue}'. Use none, recommended, applicationrequired, or systemrequired."),
        };
    }

    private static StringFormat ParseStringFormat(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "text" => StringFormat.Text,
            "textarea" => StringFormat.TextArea,
            "email" => StringFormat.Email,
            "phone" => StringFormat.Phone,
            "url" => StringFormat.Url,
            "json" => StringFormat.Json,
            "richtext" => StringFormat.RichText,
            _ => throw new InvalidOperationException(
                $"Unsupported string format '{rawValue}'. Use text, textarea, email, phone, url, json, or richtext."),
        };
    }

    private static IntegerFormat ParseIntegerFormat(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "none" => IntegerFormat.None,
            "duration" => IntegerFormat.Duration,
            "language" => IntegerFormat.Language,
            "locale" => IntegerFormat.Locale,
            "timezone" => IntegerFormat.TimeZone,
            _ => throw new InvalidOperationException(
                $"Unsupported integer format '{rawValue}'. Use none, duration, language, locale, or timezone."),
        };
    }

    private static DateTimeFormat ParseDateTimeFormat(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "dateonly" => DateTimeFormat.DateOnly,
            "dateandtime" => DateTimeFormat.DateAndTime,
            _ => throw new InvalidOperationException(
                $"Unsupported datetime format '{rawValue}'. Use dateonly or dateandtime."),
        };
    }

    private static DateTimeBehavior ParseDateTimeBehavior(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "userlocal" => DateTimeBehavior.UserLocal,
            "dateonly" => DateTimeBehavior.DateOnly,
            "timezoneindependent" => DateTimeBehavior.TimeZoneIndependent,
            _ => throw new InvalidOperationException(
                $"Unsupported datetime behavior '{rawValue}'. Use userlocal, dateonly, or timezoneindependent."),
        };
    }

    private static AssociatedMenuBehavior ParseAssociatedMenuBehavior(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "usecollectionname" => AssociatedMenuBehavior.UseCollectionName,
            "uselabel" => AssociatedMenuBehavior.UseLabel,
            "donotdisplay" => AssociatedMenuBehavior.DoNotDisplay,
            _ => throw new InvalidOperationException(
                $"Unsupported associated menu behavior '{rawValue}'. Use usecollectionname, uselabel, or donotdisplay."),
        };
    }

    private static AssociatedMenuGroup ParseAssociatedMenuGroup(string? rawValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" or "details" => AssociatedMenuGroup.Details,
            "sales" => AssociatedMenuGroup.Sales,
            "service" => AssociatedMenuGroup.Service,
            "marketing" => AssociatedMenuGroup.Marketing,
            _ => throw new InvalidOperationException(
                $"Unsupported associated menu group '{rawValue}'. Use details, sales, service, or marketing."),
        };
    }

    private static CascadeConfiguration BuildCascadeConfiguration(LookupCascadeSpec? spec)
    {
        spec ??= new LookupCascadeSpec();
        return new CascadeConfiguration
        {
            Assign = ParseCascadeType(spec.Assign, CascadeType.NoCascade),
            Delete = ParseCascadeType(spec.Delete, CascadeType.RemoveLink),
            Merge = ParseCascadeType(spec.Merge, CascadeType.NoCascade),
            Reparent = ParseCascadeType(spec.Reparent, CascadeType.NoCascade),
            Share = ParseCascadeType(spec.Share, CascadeType.NoCascade),
            Unshare = ParseCascadeType(spec.Unshare, CascadeType.NoCascade),
        };
    }

    private static CascadeType ParseCascadeType(string? rawValue, CascadeType defaultValue)
    {
        return rawValue?.Trim().ToLowerInvariant() switch
        {
            null or "" => defaultValue,
            "active" => CascadeType.Active,
            "cascade" => CascadeType.Cascade,
            "nocascade" => CascadeType.NoCascade,
            "removelink" => CascadeType.RemoveLink,
            "restrict" => CascadeType.Restrict,
            "userowned" => CascadeType.UserOwned,
            _ => throw new InvalidOperationException(
                $"Unsupported cascade type '{rawValue}'. Use active, cascade, nocascade, removelink, restrict, or userowned."),
        };
    }

    private static Label Localized(string value)
    {
        return new Label(value, 1033);
    }

    private static Label? LocalizedOrNull(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : new Label(value, 1033);
    }

    private static string NormalizeLogicalName(string rawValue)
    {
        return rawValue.Trim().ToLowerInvariant();
    }

    private static void ValidateRequired(string? value, string propertyName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException($"Metadata property '{propertyName}' is required.");
        }
    }

    private static string? EmptyToNull(string? value)
    {
        return string.IsNullOrWhiteSpace(value) ? null : value.Trim();
    }

    private sealed class TableCreateSpec
    {
        public string SchemaName { get; init; } = string.Empty;

        public string? LogicalName { get; init; }

        public string DisplayName { get; init; } = string.Empty;

        public string PluralDisplayName { get; init; } = string.Empty;

        public string? Description { get; init; }

        public string? SolutionUniqueName { get; init; }

        public string? OwnershipType { get; init; }

        public bool HasActivities { get; init; }

        public bool HasNotes { get; init; } = true;

        public bool HasFeedback { get; init; }

        public bool? EnableAudit { get; init; }

        public PrimaryNameSpec PrimaryName { get; init; } = new();
    }

    private sealed class PrimaryNameSpec
    {
        public string SchemaName { get; init; } = string.Empty;

        public string? LogicalName { get; init; }

        public string DisplayName { get; init; } = string.Empty;

        public string? Description { get; init; }

        public string? RequiredLevel { get; init; }

        public int? MaxLength { get; init; }
    }

    private sealed class AttributeCreateSpec
    {
        public string TableLogicalName { get; init; } = string.Empty;

        public string Type { get; init; } = string.Empty;

        public string SchemaName { get; init; } = string.Empty;

        public string? LogicalName { get; init; }

        public string DisplayName { get; init; } = string.Empty;

        public string? Description { get; init; }

        public string? RequiredLevel { get; init; }

        public bool? EnableAudit { get; init; }

        public bool? IsSecured { get; init; }

        public string? SolutionUniqueName { get; init; }

        public int? MaxLength { get; init; }

        public string? StringFormat { get; init; }

        public string? IntegerFormat { get; init; }

        public int? MinValueInt { get; init; }

        public int? MaxValueInt { get; init; }

        public decimal? MinValueDecimal { get; init; }

        public decimal? MaxValueDecimal { get; init; }

        public int? Precision { get; init; }

        public string? DateTimeFormat { get; init; }

        public string? DateTimeBehavior { get; init; }

        public string? TrueLabel { get; init; }

        public string? FalseLabel { get; init; }

        public bool? DefaultBooleanValue { get; init; }

        public List<ChoiceOptionSpec> Options { get; init; } = new();

        public int? OptionValueSeed { get; init; }
    }

    private sealed class ChoiceOptionSpec
    {
        public string Label { get; init; } = string.Empty;

        public int? Value { get; init; }
    }

    private sealed class LookupCreateSpec
    {
        public string ReferencingEntity { get; init; } = string.Empty;

        public string ReferencedEntity { get; init; } = string.Empty;

        public string? ReferencedAttribute { get; init; }

        public string RelationshipSchemaName { get; init; } = string.Empty;

        public string LookupSchemaName { get; init; } = string.Empty;

        public string? LookupLogicalName { get; init; }

        public string DisplayName { get; init; } = string.Empty;

        public string? Description { get; init; }

        public string? RequiredLevel { get; init; }

        public string? SolutionUniqueName { get; init; }

        public string? AssociatedMenuBehavior { get; init; }

        public string? AssociatedMenuGroup { get; init; }

        public string? AssociatedMenuLabel { get; init; }

        public int? AssociatedMenuOrder { get; init; }

        public LookupCascadeSpec? Cascade { get; init; }
    }

    private sealed class LookupCascadeSpec
    {
        public string? Assign { get; init; }

        public string? Delete { get; init; }

        public string? Merge { get; init; }

        public string? Reparent { get; init; }

        public string? Share { get; init; }

        public string? Unshare { get; init; }
    }

    private sealed class TableIconSpec
    {
        public string TableLogicalName { get; init; } = string.Empty;

        public string? IconVectorName { get; init; }

        public string? IconSmallName { get; init; }

        public string? IconLargeName { get; init; }

        public string? SolutionUniqueName { get; init; }
    }

    private sealed class FormUpdateSpec
    {
        public string EntityLogicalName { get; init; } = string.Empty;

        public string FormName { get; init; } = string.Empty;

        public int? FormType { get; init; }

        public string? TabName { get; init; }

        public string? TabLabel { get; init; }

        public string? SectionName { get; init; }

        public string? SectionLabel { get; init; }

        public bool CreateTabIfMissing { get; init; }

        public bool CreateSectionIfMissing { get; init; }

        public bool MoveExistingFields { get; init; }

        public bool PrependFields { get; init; }

        public int? SectionColumns { get; init; }

        public List<string> FieldLogicalNames { get; init; } = new();
    }

    private sealed class FormXmlPatchSpec
    {
        public string EntityLogicalName { get; init; } = string.Empty;

        public string FormName { get; init; } = string.Empty;

        public int? FormType { get; init; }

        public List<XmlPatchOperationSpec> Operations { get; init; } = new();
    }

    private sealed class FormRibbonPatchSpec
    {
        public string EntityLogicalName { get; init; } = string.Empty;

        public string FormName { get; init; } = string.Empty;

        public int? FormType { get; init; }

        public bool CreateRibbonDiffXmlIfMissing { get; init; } = true;

        public List<XmlPatchOperationSpec> Operations { get; init; } = new();
    }

    private sealed class FormEventUpdateSpec
    {
        public string EntityLogicalName { get; init; } = string.Empty;

        public string FormName { get; init; } = string.Empty;

        public int? FormType { get; init; }

        public string? OnLoadBehaviorInBulkEditForm { get; init; }

        public List<FormLibrarySpec> Libraries { get; init; } = new();

        public List<FormHandlerSpec> OnLoad { get; init; } = new();

        public List<FormHandlerSpec> OnSave { get; init; } = new();

        public List<FormOnChangeSpec> OnChange { get; init; } = new();
    }

    private sealed class FormLibrarySpec
    {
        public string Name { get; init; } = string.Empty;

        public string? LibraryUniqueId { get; init; }
    }

    private sealed class FormHandlerSpec
    {
        public string LibraryName { get; init; } = string.Empty;

        public string FunctionName { get; init; } = string.Empty;

        public string? HandlerUniqueId { get; init; }

        public bool? Enabled { get; init; }

        public bool? PassExecutionContext { get; init; }

        public string? Parameters { get; init; }

        public List<string>? Dependencies { get; init; }
    }

    private sealed class FormOnChangeSpec
    {
        public string Attribute { get; init; } = string.Empty;

        public List<FormHandlerSpec> Handlers { get; init; } = new();
    }

    private sealed class ViewUpdateSpec
    {
        public string EntityLogicalName { get; init; } = string.Empty;

        public string ViewName { get; init; } = string.Empty;

        public string? JumpColumn { get; init; }

        public bool ReplaceColumns { get; init; }

        public bool ReplaceSort { get; init; } = true;

        public bool ReplaceFilters { get; init; }

        public List<ViewColumnSpec> Columns { get; init; } = new();

        public List<ViewSortSpec> Sort { get; init; } = new();

        public List<ViewFilterSpec> Filters { get; init; } = new();

        public List<ViewLinkEntitySpec> Links { get; init; } = new();
    }

    private sealed class ViewColumnSpec
    {
        public string Name { get; init; } = string.Empty;

        public int? Width { get; init; }

        public string? EntityAlias { get; init; }

        public string? LayoutName { get; init; }
    }

    private sealed class ViewSortSpec
    {
        public string Attribute { get; init; } = string.Empty;

        public bool Descending { get; init; }

        public string? EntityAlias { get; init; }
    }

    private sealed class ViewFilterSpec
    {
        public string? Type { get; init; }

        public List<ViewConditionSpec> Conditions { get; init; } = new();

        public List<ViewFilterSpec> Filters { get; init; } = new();
    }

    private sealed class ViewConditionSpec
    {
        public string Attribute { get; init; } = string.Empty;

        public string? Operator { get; init; }

        public string? Value { get; init; }

        public List<string> Values { get; init; } = new();
    }

    private sealed class ViewLinkEntitySpec
    {
        public string Name { get; init; } = string.Empty;

        public string From { get; init; } = string.Empty;

        public string To { get; init; } = string.Empty;

        public string? Alias { get; init; }

        public string? LinkType { get; init; }

        public bool ReplaceFilters { get; init; }

        public List<ViewFilterSpec> Filters { get; init; } = new();
    }

    private sealed record FormXmlUpdateResult(
        bool Changed,
        string FormXml,
        List<string> AddedFields,
        List<string> MovedFields,
        List<string> SkippedFields,
        List<string> CreatedTabs,
        List<string> CreatedSections);

    private sealed record FormEventXmlUpdateResult(
        bool Changed,
        string FormXml,
        List<string> AddedLibraries,
        List<string> AddedHandlers,
        List<string> UpdatedHandlers,
        List<string> SkippedHandlers);

    private sealed record ViewXmlUpdateResult(
        bool Changed,
        string Xml,
        List<string> AddedColumns,
        List<string> UpdatedColumns,
        List<string> SkippedColumns,
        List<string> AddedLinks,
        int AppliedFilterCount,
        bool SortChanged);
}
