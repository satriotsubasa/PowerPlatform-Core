using System.Text.Json;
using System.Xml.Linq;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Messages;
using Microsoft.Xrm.Sdk.Metadata;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static int RunSolutionAddComponents(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = Require(options, "spec");
        var spec = JsonSerializer.Deserialize<SolutionComponentPlacementSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for solution component placement spec.");

        ValidateRequired(spec.SolutionUniqueName, "solutionUniqueName");
        if (spec.Items.Count == 0)
        {
            throw new InvalidOperationException("Provide at least one solution component item.");
        }

        var solution = RetrieveSingle(
            client,
            "solution",
            new ColumnSet("friendlyname", "uniquename"),
            new ConditionExpression("uniquename", ConditionOperator.Equal, spec.SolutionUniqueName));

        var added = new List<object>();
        var skipped = new List<object>();
        foreach (var item in spec.Items)
        {
            var resolved = ResolveSolutionComponent(client, item);
            if (IsComponentAlreadyInSolution(client, solution.Id, resolved.ComponentId, resolved.ComponentType))
            {
                skipped.Add(new
                {
                    componentType = resolved.ComponentType,
                    componentTypeName = resolved.ComponentTypeName,
                    componentId = resolved.ComponentId,
                    resolved.Description,
                    reason = "Already present in the target solution.",
                });
                continue;
            }

            client.Execute(new AddSolutionComponentRequest
            {
                ComponentId = resolved.ComponentId,
                ComponentType = resolved.ComponentType,
                SolutionUniqueName = spec.SolutionUniqueName,
                AddRequiredComponents = item.AddRequiredComponents ?? spec.AddRequiredComponents ?? true,
                DoNotIncludeSubcomponents = !(item.IncludeSubcomponents ?? spec.IncludeSubcomponents ?? false),
            });

            added.Add(new
            {
                componentType = resolved.ComponentType,
                componentTypeName = resolved.ComponentTypeName,
                componentId = resolved.ComponentId,
                resolved.Description,
            });
        }

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "add-components",
            solutionUniqueName = spec.SolutionUniqueName,
            addedCount = added.Count,
            skippedCount = skipped.Count,
            added,
            skipped,
        }, JsonOptions));
        return 0;
    }

    private static ResolvedSolutionComponent ResolveSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var explicitType = item.ComponentTypeCode ?? ParseSolutionComponentType(item.ComponentType);
        if (item.ComponentId is { Length: > 0 })
        {
            return new ResolvedSolutionComponent(
                Guid.Parse(item.ComponentId),
                explicitType,
                DescribeSolutionComponent(item, explicitType),
                SolutionComponentTypeName(explicitType));
        }

        return explicitType switch
        {
            1 => ResolveEntitySolutionComponent(client, item),
            2 => ResolveAttributeSolutionComponent(client, item),
            10 => ResolveRelationshipSolutionComponent(client, item),
            20 => ResolveRoleSolutionComponent(client, item),
            21 => ResolveRolePrivilegeSolutionComponent(client, item),
            29 => ResolveWorkflowSolutionComponent(client, item),
            60 => ResolveSystemFormSolutionComponent(client, item),
            61 => ResolveWebResourceSolutionComponent(client, item),
            66 => ResolveCustomControlSolutionComponent(client, item),
            68 => ResolveCustomControlDefaultConfigSolutionComponent(client, item),
            26 => ResolveSavedQuerySolutionComponent(client, item),
            90 => ResolvePluginTypeSolutionComponent(client, item),
            91 => ResolvePluginAssemblySolutionComponent(client, item),
            92 => ResolveSdkMessageProcessingStepSolutionComponent(client, item),
            93 => ResolveSdkMessageProcessingStepImageSolutionComponent(client, item),
            _ => throw new InvalidOperationException(
                $"Unsupported solution component type '{item.ComponentType ?? explicitType.ToString()}'."),
        };
    }

    private static ResolvedSolutionComponent ResolveEntitySolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var logicalName = item.LogicalName ?? item.EntityLogicalName;
        ValidateRequired(logicalName, "items[].logicalName");

        var response = (RetrieveEntityResponse)client.Execute(new RetrieveEntityRequest
        {
            LogicalName = logicalName,
            EntityFilters = EntityFilters.Entity,
            RetrieveAsIfPublished = true,
        });
        var metadataId = response.EntityMetadata.MetadataId
            ?? throw new InvalidOperationException($"Could not resolve a metadata id for table '{logicalName}'.");
        return new ResolvedSolutionComponent(metadataId, 1, $"entity:{logicalName}", "entity");
    }

    private static ResolvedSolutionComponent ResolveAttributeSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        ValidateRequired(item.EntityLogicalName, "items[].entityLogicalName");
        var logicalName = item.LogicalName ?? item.SchemaName;
        ValidateRequired(logicalName, "items[].logicalName");

        var response = (RetrieveAttributeResponse)client.Execute(new RetrieveAttributeRequest
        {
            EntityLogicalName = item.EntityLogicalName,
            LogicalName = logicalName,
            RetrieveAsIfPublished = true,
        });
        var metadataId = response.AttributeMetadata.MetadataId
            ?? throw new InvalidOperationException(
                $"Could not resolve a metadata id for column '{logicalName}' on '{item.EntityLogicalName}'.");
        return new ResolvedSolutionComponent(metadataId, 2, $"attribute:{item.EntityLogicalName}.{logicalName}", "attribute");
    }

    private static ResolvedSolutionComponent ResolveRelationshipSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var schemaName = item.SchemaName ?? item.Name;
        ValidateRequired(schemaName, "items[].schemaName");

        var response = (RetrieveRelationshipResponse)client.Execute(new RetrieveRelationshipRequest
        {
            Name = schemaName,
            RetrieveAsIfPublished = true,
        });
        var metadataId = response.RelationshipMetadata.MetadataId
            ?? throw new InvalidOperationException($"Could not resolve a metadata id for relationship '{schemaName}'.");
        return new ResolvedSolutionComponent(metadataId, 10, $"relationship:{schemaName}", "relationship");
    }

    private static ResolvedSolutionComponent ResolveRoleSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.RoleName ?? item.Name ?? item.LogicalName;
        var role = ResolveSecurityRole(
            client,
            item.RoleId ?? item.ComponentId,
            name,
            item.BusinessUnitId,
            item.BusinessUnitName,
            null);
        return new ResolvedSolutionComponent(role.Id, 20, $"role:{role.GetAttributeValue<string>("name")}", "role");
    }

    private static ResolvedSolutionComponent ResolveRolePrivilegeSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        if (item.ComponentId is { Length: > 0 })
        {
            return new ResolvedSolutionComponent(Guid.Parse(item.ComponentId), 21, $"roleprivilege:{item.ComponentId}", "roleprivilege");
        }

        var role = ResolveSecurityRole(
            client,
            item.RoleId,
            item.RoleName ?? item.Name,
            item.BusinessUnitId,
            item.BusinessUnitName,
            null);
        var privileges = LoadRolePrivilegesByRoleId(client, new[] { role.Id }).GetValueOrDefault(role.Id, new List<SecurityRolePrivilegeRow>());
        if (!string.IsNullOrWhiteSpace(item.PrivilegeId))
        {
            var privilegeId = Guid.Parse(item.PrivilegeId);
            var exact = privileges.Where(privilege => privilege.PrivilegeId == privilegeId).ToList();
            if (exact.Count == 0)
            {
                throw new InvalidOperationException($"Could not resolve role privilege '{item.PrivilegeId}' for role '{role.GetAttributeValue<string>("name")}'.");
            }
            if (exact.Count > 1)
            {
                throw new InvalidOperationException($"More than one role privilege matched '{item.PrivilegeId}'. Use componentId explicitly.");
            }

            return new ResolvedSolutionComponent(exact[0].RolePrivilegeId, 21, $"roleprivilege:{exact[0].PrivilegeId}", "roleprivilege");
        }

        ValidateRequired(item.PrivilegeName, "items[].privilegeName");
        var matches = privileges
            .Where(privilege => string.Equals(privilege.PrivilegeName, item.PrivilegeName, StringComparison.OrdinalIgnoreCase))
            .ToList();
        if (matches.Count == 0)
        {
            throw new InvalidOperationException($"Could not resolve role privilege '{item.PrivilegeName}' for role '{role.GetAttributeValue<string>("name")}'.");
        }
        if (matches.Count > 1)
        {
            throw new InvalidOperationException($"More than one role privilege matched '{item.PrivilegeName}'. Use componentId explicitly.");
        }

        return new ResolvedSolutionComponent(matches[0].RolePrivilegeId, 21, $"roleprivilege:{matches[0].PrivilegeName}", "roleprivilege");
    }

    private static ResolvedSolutionComponent ResolveSystemFormSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        ValidateRequired(item.EntityLogicalName, "items[].entityLogicalName");
        var formName = item.Name ?? item.FormName;
        ValidateRequired(formName, "items[].name");

        var form = RetrieveSingle(
            client,
            "systemform",
            new ColumnSet("name", "objecttypecode", "type"),
            new ConditionExpression("objecttypecode", ConditionOperator.Equal, item.EntityLogicalName),
            new ConditionExpression("name", ConditionOperator.Equal, formName),
            new ConditionExpression("type", ConditionOperator.Equal, item.FormType ?? 2));
        return new ResolvedSolutionComponent(form.Id, 60, $"systemform:{item.EntityLogicalName}:{formName}", "systemform");
    }

    private static ResolvedSolutionComponent ResolveSavedQuerySolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        ValidateRequired(item.EntityLogicalName, "items[].entityLogicalName");
        var viewName = item.Name ?? item.ViewName;
        ValidateRequired(viewName, "items[].name");

        var view = RetrieveSingle(
            client,
            "savedquery",
            new ColumnSet("name", "returnedtypecode"),
            new ConditionExpression("returnedtypecode", ConditionOperator.Equal, item.EntityLogicalName),
            new ConditionExpression("name", ConditionOperator.Equal, viewName));
        return new ResolvedSolutionComponent(view.Id, 26, $"savedquery:{item.EntityLogicalName}:{viewName}", "savedquery");
    }

    private static ResolvedSolutionComponent ResolveWorkflowSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        if (item.ComponentId is { Length: > 0 })
        {
            return new ResolvedSolutionComponent(Guid.Parse(item.ComponentId), 29, $"workflow:{item.ComponentId}", "workflow");
        }

        var query = new QueryExpression("workflow")
        {
            ColumnSet = new ColumnSet("name", "uniquename", "workflowidunique"),
            TopCount = 2,
        };
        query.Criteria.AddCondition("category", ConditionOperator.Equal, 5);
        query.Criteria.AddCondition("type", ConditionOperator.Equal, 1);

        var selectorCount = 0;
        if (!string.IsNullOrWhiteSpace(item.WorkflowId))
        {
            query.Criteria.AddCondition("workflowid", ConditionOperator.Equal, Guid.Parse(item.WorkflowId));
            selectorCount++;
        }
        if (!string.IsNullOrWhiteSpace(item.WorkflowUniqueId))
        {
            query.Criteria.AddCondition("workflowidunique", ConditionOperator.Equal, Guid.Parse(item.WorkflowUniqueId));
            selectorCount++;
        }
        if (!string.IsNullOrWhiteSpace(item.UniqueName))
        {
            query.Criteria.AddCondition("uniquename", ConditionOperator.Equal, item.UniqueName);
            selectorCount++;
        }
        var name = item.Name ?? item.LogicalName;
        if (!string.IsNullOrWhiteSpace(name))
        {
            query.Criteria.AddCondition("name", ConditionOperator.Equal, name);
            selectorCount++;
        }

        if (selectorCount == 0)
        {
            throw new InvalidOperationException(
                "Workflow solution components require componentId, workflowId, workflowUniqueId, uniqueName, or name.");
        }

        var matches = client.RetrieveMultiple(query).Entities;
        if (matches.Count == 0)
        {
            throw new InvalidOperationException("Could not resolve a workflow component from the supplied selector.");
        }
        if (matches.Count > 1)
        {
            throw new InvalidOperationException(
                "More than one workflow matched the supplied selector. Use workflowId or uniqueName explicitly.");
        }

        var flow = matches[0];
        return new ResolvedSolutionComponent(flow.Id, 29, $"workflow:{flow.GetAttributeValue<string>("name")}", "workflow");
    }

    private static ResolvedSolutionComponent ResolveWebResourceSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.Name ?? item.LogicalName;
        ValidateRequired(name, "items[].name");

        var webResource = RetrieveSingle(
            client,
            "webresource",
            new ColumnSet("name"),
            new ConditionExpression("name", ConditionOperator.Equal, name));
        return new ResolvedSolutionComponent(webResource.Id, 61, $"webresource:{name}", "webresource");
    }

    private static ResolvedSolutionComponent ResolveCustomControlSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.Name ?? item.PcfControlName ?? item.LogicalName;
        ValidateRequired(name, "items[].name");

        var control = RetrieveSingle(
            client,
            "customcontrol",
            new ColumnSet("name"),
            new ConditionExpression("name", ConditionOperator.Equal, name));
        return new ResolvedSolutionComponent(control.Id, 66, $"customcontrol:{name}", "customcontrol");
    }

    private static ResolvedSolutionComponent ResolveCustomControlDefaultConfigSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        if (item.ComponentId is { Length: > 0 })
        {
            return new ResolvedSolutionComponent(Guid.Parse(item.ComponentId), 68, $"customcontroldefaultconfig:{item.ComponentId}", "customcontroldefaultconfig");
        }

        ValidateRequired(item.EntityLogicalName, "items[].entityLogicalName");
        var controlName = item.PcfControlName ?? item.Name;
        ValidateRequired(controlName, "items[].pcfControlName");
        var resolvedControlName = controlName!;

        var query = new QueryExpression("customcontroldefaultconfig")
        {
            ColumnSet = new ColumnSet("controldescriptionxml", "primaryentitytypecode"),
            TopCount = 50,
        };
        query.Criteria.AddCondition("primaryentitytypecode", ConditionOperator.Equal, item.EntityLogicalName);

        var matches = client.RetrieveMultiple(query).Entities
            .Where(entity => MatchesCustomControlDefaultConfig(entity, resolvedControlName))
            .ToList();
        if (matches.Count == 0)
        {
            throw new InvalidOperationException(
                $"Could not resolve a custom control default config for '{resolvedControlName}' on '{item.EntityLogicalName}'.");
        }

        if (matches.Count > 1)
        {
            throw new InvalidOperationException(
                $"More than one custom control default config matched '{resolvedControlName}' on '{item.EntityLogicalName}'. Use componentId explicitly.");
        }

        return new ResolvedSolutionComponent(
            matches[0].Id,
            68,
            $"customcontroldefaultconfig:{item.EntityLogicalName}:{resolvedControlName}",
            "customcontroldefaultconfig");
    }

    private static bool MatchesCustomControlDefaultConfig(Entity entity, string controlName)
    {
        var xml = entity.GetAttributeValue<string>("controldescriptionxml");
        if (string.IsNullOrWhiteSpace(xml))
        {
            return false;
        }

        var document = XDocument.Parse(xml, LoadOptions.PreserveWhitespace);
        return document.Descendants("customControl")
            .Any(node => string.Equals(
                NormalizeOptionalString((string?)node.Attribute("name")),
                NormalizeOptionalString(controlName),
                StringComparison.OrdinalIgnoreCase));
    }

    private static ResolvedSolutionComponent ResolvePluginTypeSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.Name ?? item.LogicalName;
        ValidateRequired(name, "items[].name");

        var pluginType = RetrieveSingle(
            client,
            "plugintype",
            new ColumnSet("name"),
            new ConditionExpression("name", ConditionOperator.Equal, name));
        return new ResolvedSolutionComponent(pluginType.Id, 90, $"plugintype:{name}", "plugintype");
    }

    private static ResolvedSolutionComponent ResolvePluginAssemblySolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.Name ?? item.LogicalName;
        ValidateRequired(name, "items[].name");

        var assembly = RetrieveSingle(
            client,
            "pluginassembly",
            new ColumnSet("name"),
            new ConditionExpression("name", ConditionOperator.Equal, name));
        return new ResolvedSolutionComponent(assembly.Id, 91, $"pluginassembly:{name}", "pluginassembly");
    }

    private static ResolvedSolutionComponent ResolveSdkMessageProcessingStepSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.Name ?? item.LogicalName;
        ValidateRequired(name, "items[].name");

        var step = RetrieveSingle(
            client,
            "sdkmessageprocessingstep",
            new ColumnSet("name"),
            new ConditionExpression("name", ConditionOperator.Equal, name));
        return new ResolvedSolutionComponent(step.Id, 92, $"sdkmessageprocessingstep:{name}", "sdkmessageprocessingstep");
    }

    private static ResolvedSolutionComponent ResolveSdkMessageProcessingStepImageSolutionComponent(ServiceClient client, SolutionComponentItemSpec item)
    {
        var name = item.Name ?? item.LogicalName;
        ValidateRequired(name, "items[].name");

        var image = RetrieveSingle(
            client,
            "sdkmessageprocessingstepimage",
            new ColumnSet("name"),
            new ConditionExpression("name", ConditionOperator.Equal, name));
        return new ResolvedSolutionComponent(image.Id, 93, $"sdkmessageprocessingstepimage:{name}", "sdkmessageprocessingstepimage");
    }

    private static bool IsComponentAlreadyInSolution(ServiceClient client, Guid solutionId, Guid componentId, int componentType)
    {
        var query = new QueryExpression("solutioncomponent")
        {
            ColumnSet = new ColumnSet("solutioncomponentid"),
            TopCount = 1,
        };
        query.Criteria.AddCondition("solutionid", ConditionOperator.Equal, solutionId);
        query.Criteria.AddCondition("objectid", ConditionOperator.Equal, componentId);
        query.Criteria.AddCondition("componenttype", ConditionOperator.Equal, componentType);
        return client.RetrieveMultiple(query).Entities.Count > 0;
    }

    private static int ParseSolutionComponentType(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new InvalidOperationException("Solution component items require componentType or componentTypeCode.");
        }

        if (int.TryParse(value, out var numeric))
        {
            return numeric;
        }

        return value.Trim().ToLowerInvariant() switch
        {
            "entity" or "table" => 1,
            "attribute" or "field" or "column" => 2,
            "relationship" or "entityrelationship" => 10,
            "role" or "securityrole" => 20,
            "roleprivilege" or "securityroleprivilege" => 21,
            "workflow" or "flow" or "cloudflow" => 29,
            "savedquery" or "view" => 26,
            "systemform" or "form" => 60,
            "webresource" => 61,
            "customcontrol" or "pcfcontrol" => 66,
            "customcontroldefaultconfig" or "pcfdefaultconfig" => 68,
            "plugintype" => 90,
            "pluginassembly" => 91,
            "sdkmessageprocessingstep" or "step" => 92,
            "sdkmessageprocessingstepimage" or "stepimage" => 93,
            _ => throw new InvalidOperationException($"Unsupported solution component type '{value}'."),
        };
    }

    private static string DescribeSolutionComponent(SolutionComponentItemSpec item, int componentType)
    {
        return componentType switch
        {
            1 => $"entity:{item.LogicalName ?? item.EntityLogicalName}",
            2 => $"attribute:{item.EntityLogicalName}.{item.LogicalName ?? item.SchemaName}",
            10 => $"relationship:{item.SchemaName ?? item.Name}",
            20 => $"role:{item.RoleName ?? item.Name}",
            21 => $"roleprivilege:{item.PrivilegeName ?? item.PrivilegeId}",
            29 => $"workflow:{item.UniqueName ?? item.Name ?? item.WorkflowId ?? item.WorkflowUniqueId}",
            26 => $"savedquery:{item.EntityLogicalName}:{item.Name ?? item.ViewName}",
            60 => $"systemform:{item.EntityLogicalName}:{item.Name ?? item.FormName}",
            61 => $"webresource:{item.Name ?? item.LogicalName}",
            66 => $"customcontrol:{item.Name ?? item.PcfControlName}",
            68 => $"customcontroldefaultconfig:{item.EntityLogicalName}:{item.Name ?? item.PcfControlName}",
            90 => $"plugintype:{item.Name}",
            91 => $"pluginassembly:{item.Name}",
            92 => $"sdkmessageprocessingstep:{item.Name}",
            93 => $"sdkmessageprocessingstepimage:{item.Name}",
            _ => $"component:{componentType}:{item.ComponentId}",
        };
    }

    private static string SolutionComponentTypeName(int componentType)
    {
        return componentType switch
        {
            1 => "entity",
            2 => "attribute",
            10 => "relationship",
            20 => "role",
            21 => "roleprivilege",
            29 => "workflow",
            26 => "savedquery",
            60 => "systemform",
            61 => "webresource",
            66 => "customcontrol",
            68 => "customcontroldefaultconfig",
            90 => "plugintype",
            91 => "pluginassembly",
            92 => "sdkmessageprocessingstep",
            93 => "sdkmessageprocessingstepimage",
            _ => componentType.ToString(),
        };
    }

    private sealed class SolutionComponentPlacementSpec
    {
        public string SolutionUniqueName { get; init; } = string.Empty;

        public bool? AddRequiredComponents { get; init; }

        public bool? IncludeSubcomponents { get; init; }

        public List<SolutionComponentItemSpec> Items { get; init; } = new();
    }

    private sealed class SolutionComponentItemSpec
    {
        public string? ComponentType { get; init; }

        public int? ComponentTypeCode { get; init; }

        public string? ComponentId { get; init; }

        public string? LogicalName { get; init; }

        public string? EntityLogicalName { get; init; }

        public string? SchemaName { get; init; }

        public string? Name { get; init; }

        public string? RoleName { get; init; }

        public string? UniqueName { get; init; }

        public string? FormName { get; init; }

        public string? ViewName { get; init; }

        public string? WorkflowId { get; init; }

        public string? WorkflowUniqueId { get; init; }

        public string? RoleId { get; init; }

        public string? BusinessUnitId { get; init; }

        public string? BusinessUnitName { get; init; }

        public string? PrivilegeId { get; init; }

        public string? PrivilegeName { get; init; }

        public int? FormType { get; init; }

        public string? PcfControlName { get; init; }

        public bool? AddRequiredComponents { get; init; }

        public bool? IncludeSubcomponents { get; init; }
    }

    private sealed record ResolvedSolutionComponent(
        Guid ComponentId,
        int ComponentType,
        string Description,
        string ComponentTypeName);
}
