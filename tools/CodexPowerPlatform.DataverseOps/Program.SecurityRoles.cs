using System.Text.Json;
using Microsoft.Crm.Sdk.Messages;
using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static readonly string[] SecurityRoleColumns =
    {
        "roleid",
        "name",
        "description",
        "appliesto",
        "summaryofcoretablepermissions",
        "businessunitid",
        "canbedeleted",
        "isinherited",
        "isautoassigned",
        "issytemgenerated",
        "ismanaged",
        "createdon",
        "modifiedon",
        "parentrootroleid",
        "roletemplateid",
    };

    private static int RunSecurityRole(Dictionary<string, string?> options)
    {
        using var client = Connect(options);
        var mode = options.TryGetValue("mode", out var rawMode) && !string.IsNullOrWhiteSpace(rawMode)
            ? rawMode!.Trim().ToLowerInvariant()
            : "list";

        return mode switch
        {
            "list" => RunSecurityRoleList(client, options),
            "inspect" => RunSecurityRoleInspect(client, options),
            "create" => RunSecurityRoleCreate(client, options),
            "update" => RunSecurityRoleUpdate(client, options),
            _ => throw new InvalidOperationException("Unsupported securityrole mode. Use --mode list, inspect, create, or update."),
        };
    }

    private static int RunSecurityRoleList(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<SecurityRoleListSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for security role list spec.");

        var businessUnitId = ResolveBusinessUnitId(client, spec.BusinessUnitId, spec.BusinessUnitName, allowDefaultRoot: false);
        var query = BuildSecurityRoleQuery(spec.SolutionUniqueName, businessUnitId, includeSystemGenerated: spec.IncludeSystemGenerated != false);
        var roles = RetrieveAll(client, query);
        var privilegesByRole = spec.IncludePrivileges == true
            ? LoadRolePrivilegesByRoleId(client, roles.Select(role => role.Id).ToArray())
            : new Dictionary<Guid, List<SecurityRolePrivilegeRow>>();

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "list",
            solutionUniqueName = spec.SolutionUniqueName,
            count = roles.Count,
            roles = roles.Select(role => BuildSecurityRolePayload(
                role,
                privilegesByRole.TryGetValue(role.Id, out var privileges) ? privileges : null)),
        }, JsonOptions));
        return 0;
    }

    private static int RunSecurityRoleInspect(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<SecurityRoleInspectSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for security role inspect spec.");

        var role = ResolveSecurityRole(
            client,
            spec.RoleId,
            spec.Name,
            spec.BusinessUnitId,
            spec.BusinessUnitName,
            spec.SolutionUniqueName);
        var privilegesByRole = spec.IncludePrivileges == false
            ? new Dictionary<Guid, List<SecurityRolePrivilegeRow>>()
            : LoadRolePrivilegesByRoleId(client, new[] { role.Id });

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "inspect",
            role = BuildSecurityRolePayload(
                role,
                privilegesByRole.TryGetValue(role.Id, out var privileges) ? privileges : null),
        }, JsonOptions));
        return 0;
    }

    private static int RunSecurityRoleCreate(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<SecurityRoleCreateSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for security role create spec.");

        ValidateRequired(spec.Name, "name");

        var sourceRole = ResolveOptionalSourceRole(
            client,
            spec.CopyFromRoleId,
            spec.CopyFromRoleName,
            spec.CopyFromBusinessUnitId,
            spec.CopyFromBusinessUnitName);
        var businessUnitId = ResolveCreateBusinessUnitId(client, spec.BusinessUnitId, spec.BusinessUnitName, sourceRole);

        var entity = new Entity("role")
        {
            ["name"] = spec.Name,
            ["businessunitid"] = new EntityReference("businessunit", businessUnitId),
        };

        ApplyRoleStringField(entity, "description", spec.Description ?? sourceRole?.GetAttributeValue<string>("description"));
        ApplyRoleStringField(entity, "appliesto", spec.AppliesTo ?? sourceRole?.GetAttributeValue<string>("appliesto"));
        ApplyRoleStringField(
            entity,
            "summaryofcoretablepermissions",
            spec.SummaryOfCoreTablePermissions ?? sourceRole?.GetAttributeValue<string>("summaryofcoretablepermissions"));

        var inheritanceMode = ResolveInheritanceMode(spec.InheritanceMode);
        if (inheritanceMode.HasValue)
        {
            entity["isinherited"] = new OptionSetValue(inheritanceMode.Value);
        }
        else if (sourceRole?.GetAttributeValue<OptionSetValue>("isinherited") is { } sourceInheritance)
        {
            entity["isinherited"] = new OptionSetValue(sourceInheritance.Value);
        }

        if (spec.IsAutoAssigned.HasValue)
        {
            entity["isautoassigned"] = new OptionSetValue(spec.IsAutoAssigned.Value ? 1 : 0);
        }
        else if (sourceRole?.GetAttributeValue<OptionSetValue>("isautoassigned") is { } sourceAutoAssigned)
        {
            entity["isautoassigned"] = new OptionSetValue(sourceAutoAssigned.Value);
        }

        var roleId = client.Create(entity);
        var role = ResolveSecurityRole(client, roleId.ToString("D"), null, null, null, null);
        var desiredPrivileges = BuildDesiredRolePrivileges(
            basePrivileges: sourceRole is null
                ? Array.Empty<SecurityRolePrivilegeRow>()
                : LoadRolePrivilegesByRoleId(client, new[] { sourceRole.Id }).GetValueOrDefault(sourceRole.Id, new List<SecurityRolePrivilegeRow>()),
            replacePrivileges: spec.Privileges,
            additionalPrivileges: spec.AdditionalPrivileges,
            removePrivileges: spec.RemovePrivileges,
            targetBusinessUnitId: businessUnitId,
            client: client);

        if (desiredPrivileges is not null)
        {
            ReplaceRolePrivileges(client, roleId, desiredPrivileges);
        }

        EnsureSecurityRoleInSolution(client, roleId, spec.SolutionUniqueName);
        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            EnsureSecurityRolePrivilegesInSolution(client, roleId, spec.SolutionUniqueName!);
        }

        var rolePrivileges = LoadRolePrivilegesByRoleId(client, new[] { roleId }).GetValueOrDefault(roleId, new List<SecurityRolePrivilegeRow>());
        var warnings = BuildSecurityRoleWarnings(spec.SolutionUniqueName, rolePrivileges.Count);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "create",
            solutionUniqueName = spec.SolutionUniqueName,
            copiedFromRoleId = sourceRole?.Id,
            warnings,
            role = BuildSecurityRolePayload(role, rolePrivileges),
        }, JsonOptions));
        return 0;
    }

    private static int RunSecurityRoleUpdate(ServiceClient client, Dictionary<string, string?> options)
    {
        var specText = ReadSpecText(options);
        var spec = JsonSerializer.Deserialize<SecurityRoleUpdateSpec>(specText, InputJsonOptions)
            ?? throw new InvalidOperationException("Expected a JSON object for security role update spec.");

        var role = ResolveSecurityRole(
            client,
            spec.RoleId,
            spec.Name,
            spec.BusinessUnitId,
            spec.BusinessUnitName,
            spec.SolutionUniqueName);
        EnsureEditableRole(role, spec.AllowSystemGeneratedRoleUpdate == true);

        var update = new Entity("role", role.Id);
        if (!string.IsNullOrWhiteSpace(spec.NewName))
        {
            update["name"] = spec.NewName;
        }
        if (spec.Description is not null)
        {
            update["description"] = spec.Description;
        }
        if (spec.AppliesTo is not null)
        {
            update["appliesto"] = spec.AppliesTo;
        }
        if (spec.SummaryOfCoreTablePermissions is not null)
        {
            update["summaryofcoretablepermissions"] = spec.SummaryOfCoreTablePermissions;
        }

        var inheritanceMode = ResolveInheritanceMode(spec.InheritanceMode);
        if (inheritanceMode.HasValue)
        {
            update["isinherited"] = new OptionSetValue(inheritanceMode.Value);
        }
        if (spec.IsAutoAssigned.HasValue)
        {
            update["isautoassigned"] = new OptionSetValue(spec.IsAutoAssigned.Value ? 1 : 0);
        }

        if (update.Attributes.Count > 0)
        {
            client.Update(update);
        }

        var businessUnitId = role.GetAttributeValue<EntityReference>("businessunitid")?.Id
            ?? throw new InvalidOperationException("The target security role does not expose a business unit.");
        var currentPrivileges = LoadRolePrivilegesByRoleId(client, new[] { role.Id }).GetValueOrDefault(role.Id, new List<SecurityRolePrivilegeRow>());
        var desiredPrivileges = BuildDesiredRolePrivileges(
            basePrivileges: currentPrivileges,
            replacePrivileges: spec.Privileges,
            additionalPrivileges: spec.AdditionalPrivileges,
            removePrivileges: spec.RemovePrivileges,
            targetBusinessUnitId: businessUnitId,
            client: client);

        if (desiredPrivileges is not null)
        {
            ReplaceRolePrivileges(client, role.Id, desiredPrivileges);
        }

        if (!string.IsNullOrWhiteSpace(spec.SolutionUniqueName))
        {
            EnsureSecurityRoleInSolution(client, role.Id, spec.SolutionUniqueName);
            EnsureSecurityRolePrivilegesInSolution(client, role.Id, spec.SolutionUniqueName!);
        }

        var refreshed = ResolveSecurityRole(client, role.Id.ToString("D"), null, null, null, spec.SolutionUniqueName);
        var refreshedPrivileges = LoadRolePrivilegesByRoleId(client, new[] { role.Id }).GetValueOrDefault(role.Id, new List<SecurityRolePrivilegeRow>());
        var warnings = BuildSecurityRoleWarnings(spec.SolutionUniqueName, refreshedPrivileges.Count);

        Console.WriteLine(JsonSerializer.Serialize(new
        {
            success = true,
            mode = "update",
            solutionUniqueName = spec.SolutionUniqueName,
            warnings,
            role = BuildSecurityRolePayload(refreshed, refreshedPrivileges),
        }, JsonOptions));
        return 0;
    }

    private static QueryExpression BuildSecurityRoleQuery(string? solutionUniqueName, Guid? businessUnitId, bool includeSystemGenerated)
    {
        var query = new QueryExpression("role")
        {
            ColumnSet = new ColumnSet(SecurityRoleColumns),
            PageInfo = new PagingInfo
            {
                Count = 5000,
                PageNumber = 1,
            },
        };

        if (businessUnitId.HasValue)
        {
            query.Criteria.AddCondition("businessunitid", ConditionOperator.Equal, businessUnitId.Value);
        }
        if (!includeSystemGenerated)
        {
            query.Criteria.AddCondition("issytemgenerated", ConditionOperator.Equal, false);
        }
        if (!string.IsNullOrWhiteSpace(solutionUniqueName))
        {
            AddSolutionComponentFilter(query, "roleid", solutionUniqueName!, 20);
        }

        return query;
    }

    private static void AddSolutionComponentFilter(QueryExpression query, string primaryIdAttribute, string solutionUniqueName, int componentType)
    {
        var componentLink = query.AddLink("solutioncomponent", primaryIdAttribute, "objectid");
        componentLink.LinkCriteria.AddCondition("componenttype", ConditionOperator.Equal, componentType);
        var solutionLink = componentLink.AddLink("solution", "solutionid", "solutionid");
        solutionLink.LinkCriteria.AddCondition("uniquename", ConditionOperator.Equal, solutionUniqueName);
    }

    private static Entity ResolveSecurityRole(
        ServiceClient client,
        string? roleId,
        string? name,
        string? businessUnitId,
        string? businessUnitName,
        string? solutionUniqueName)
    {
        var resolvedBusinessUnitId = ResolveBusinessUnitId(client, businessUnitId, businessUnitName, allowDefaultRoot: false);
        var query = BuildSecurityRoleQuery(solutionUniqueName, resolvedBusinessUnitId, includeSystemGenerated: true);
        query.TopCount = 2;

        var selectorCount = 0;
        if (!string.IsNullOrWhiteSpace(roleId))
        {
            query.Criteria.AddCondition("roleid", ConditionOperator.Equal, Guid.Parse(roleId));
            selectorCount++;
        }
        if (!string.IsNullOrWhiteSpace(name))
        {
            query.Criteria.AddCondition("name", ConditionOperator.Equal, name);
            selectorCount++;
        }

        if (selectorCount == 0)
        {
            throw new InvalidOperationException("Security role operations require roleId or name.");
        }

        var matches = client.RetrieveMultiple(query).Entities;
        if (matches.Count == 0)
        {
            throw new InvalidOperationException("No matching security role was found for the supplied selector.");
        }
        if (matches.Count > 1)
        {
            throw new InvalidOperationException("More than one security role matched the supplied selector. Include businessUnitId or businessUnitName.");
        }

        return matches[0];
    }

    private static Entity? ResolveOptionalSourceRole(
        ServiceClient client,
        string? roleId,
        string? name,
        string? businessUnitId,
        string? businessUnitName)
    {
        if (string.IsNullOrWhiteSpace(roleId) && string.IsNullOrWhiteSpace(name))
        {
            return null;
        }

        return ResolveSecurityRole(client, roleId, name, businessUnitId, businessUnitName, null);
    }

    private static Guid ResolveCreateBusinessUnitId(ServiceClient client, string? businessUnitId, string? businessUnitName, Entity? sourceRole)
    {
        if (!string.IsNullOrWhiteSpace(businessUnitId) || !string.IsNullOrWhiteSpace(businessUnitName))
        {
            return ResolveBusinessUnitId(client, businessUnitId, businessUnitName, allowDefaultRoot: false)
                ?? throw new InvalidOperationException("Could not resolve the requested business unit.");
        }

        if (sourceRole?.GetAttributeValue<EntityReference>("businessunitid") is { } sourceBusinessUnit)
        {
            return sourceBusinessUnit.Id;
        }

        return ResolveBusinessUnitId(client, null, null, allowDefaultRoot: true)
            ?? throw new InvalidOperationException("Could not resolve the default root business unit.");
    }

    private static Guid? ResolveBusinessUnitId(ServiceClient client, string? businessUnitId, string? businessUnitName, bool allowDefaultRoot)
    {
        if (!string.IsNullOrWhiteSpace(businessUnitId))
        {
            return Guid.Parse(businessUnitId);
        }
        if (!string.IsNullOrWhiteSpace(businessUnitName))
        {
            return RetrieveSingle(
                client,
                "businessunit",
                new ColumnSet("businessunitid", "name"),
                new ConditionExpression("name", ConditionOperator.Equal, businessUnitName)).Id;
        }
        if (allowDefaultRoot)
        {
            return RetrieveSingle(
                client,
                "businessunit",
                new ColumnSet("businessunitid", "name"),
                new ConditionExpression("parentbusinessunitid", ConditionOperator.Null)).Id;
        }

        return null;
    }

    private static Dictionary<Guid, List<SecurityRolePrivilegeRow>> LoadRolePrivilegesByRoleId(ServiceClient client, IReadOnlyCollection<Guid> roleIds)
    {
        var result = new Dictionary<Guid, List<SecurityRolePrivilegeRow>>();
        if (roleIds.Count == 0)
        {
            return result;
        }

        var query = new QueryExpression("roleprivileges")
        {
            ColumnSet = new ColumnSet("roleprivilegeid", "roleid", "privilegeid", "privilegedepthmask", "recordfilterid"),
            PageInfo = new PagingInfo
            {
                Count = 5000,
                PageNumber = 1,
            },
        };
        query.Criteria.AddCondition("roleid", ConditionOperator.In, roleIds.Cast<object>().ToArray());

        var privilegeLink = query.AddLink("privilege", "privilegeid", "privilegeid", JoinOperator.LeftOuter);
        privilegeLink.EntityAlias = "privilege";
        privilegeLink.Columns = new ColumnSet("name");

        var rows = RetrieveAll(client, query)
            .Select(entity => new SecurityRolePrivilegeRow(
                RolePrivilegeId: entity.Id,
                RoleId: entity.GetAttributeValue<Guid>("roleid"),
                PrivilegeId: entity.GetAttributeValue<Guid>("privilegeid"),
                PrivilegeName: ReadAliasedString(entity, "privilege.name"),
                DepthValue: entity.GetAttributeValue<int>("privilegedepthmask"),
                RecordFilterId: entity.GetAttributeValue<EntityReference>("recordfilterid")?.Id))
            .ToList();

        foreach (var row in rows)
        {
            if (!result.TryGetValue(row.RoleId, out var list))
            {
                list = new List<SecurityRolePrivilegeRow>();
                result[row.RoleId] = list;
            }

            list.Add(row);
        }

        return result;
    }

    private static string? ReadAliasedString(Entity entity, string alias)
    {
        return entity.Attributes.TryGetValue(alias, out var value) && value is AliasedValue aliased
            ? aliased.Value as string
            : null;
    }

    private static object BuildSecurityRolePayload(Entity role, IReadOnlyList<SecurityRolePrivilegeRow>? privileges)
    {
        var businessUnit = role.GetAttributeValue<EntityReference>("businessunitid");
        var parentRootRole = role.GetAttributeValue<EntityReference>("parentrootroleid");
        var roleTemplate = role.GetAttributeValue<EntityReference>("roletemplateid");

        return new
        {
            roleId = role.Id,
            name = role.GetAttributeValue<string>("name"),
            description = role.GetAttributeValue<string>("description"),
            appliesTo = role.GetAttributeValue<string>("appliesto"),
            summaryOfCoreTablePermissions = role.GetAttributeValue<string>("summaryofcoretablepermissions"),
            businessUnitId = businessUnit?.Id,
            businessUnitName = businessUnit?.Name,
            isSystemGenerated = ReadBoolAttribute(role, "issytemgenerated"),
            isManaged = ReadBoolAttribute(role, "ismanaged"),
            canBeDeleted = role.GetAttributeValue<BooleanManagedProperty>("canbedeleted")?.Value,
            isInherited = role.GetAttributeValue<OptionSetValue>("isinherited")?.Value,
            isInheritedLabel = InheritanceModeLabel(role.GetAttributeValue<OptionSetValue>("isinherited")?.Value),
            isAutoAssigned = role.GetAttributeValue<OptionSetValue>("isautoassigned")?.Value,
            isAutoAssignedLabel = YesNoLabel(role.GetAttributeValue<OptionSetValue>("isautoassigned")?.Value),
            parentRootRoleId = parentRootRole?.Id,
            parentRootRoleName = parentRootRole?.Name,
            roleTemplateId = roleTemplate?.Id,
            roleTemplateName = roleTemplate?.Name,
            createdOn = role.GetAttributeValue<DateTime?>("createdon"),
            modifiedOn = role.GetAttributeValue<DateTime?>("modifiedon"),
            privilegeCount = privileges?.Count,
            privileges = privileges?.Select(privilege => new
            {
                rolePrivilegeId = privilege.RolePrivilegeId,
                privilegeId = privilege.PrivilegeId,
                privilegeName = privilege.PrivilegeName,
                depth = PrivilegeDepthLabel(privilege.DepthValue),
                depthValue = privilege.DepthValue,
                recordFilterId = privilege.RecordFilterId,
            }),
        };
    }

    private static string? InheritanceModeLabel(int? value)
    {
        return value switch
        {
            0 => "team-only",
            1 => "direct-user-and-team",
            _ => value?.ToString(),
        };
    }

    private static string? YesNoLabel(int? value)
    {
        return value switch
        {
            0 => "no",
            1 => "yes",
            _ => value?.ToString(),
        };
    }

    private static string PrivilegeDepthLabel(int depthValue)
    {
        return depthValue switch
        {
            0 => "basic",
            1 => "local",
            2 => "deep",
            3 => "global",
            4 => "record-filter",
            _ => depthValue.ToString(),
        };
    }

    private static List<DesiredSecurityRolePrivilege>? BuildDesiredRolePrivileges(
        IReadOnlyList<SecurityRolePrivilegeRow> basePrivileges,
        List<SecurityRolePrivilegeSpec>? replacePrivileges,
        List<SecurityRolePrivilegeSpec>? additionalPrivileges,
        List<SecurityRolePrivilegeSelectorSpec>? removePrivileges,
        Guid targetBusinessUnitId,
        ServiceClient client)
    {
        var hasPrivilegeChangeRequest = replacePrivileges is not null
            || additionalPrivileges is not null
            || removePrivileges is not null;
        if (!hasPrivilegeChangeRequest && basePrivileges.Count == 0)
        {
            return null;
        }

        var desired = replacePrivileges is not null
            ? ResolveDesiredSecurityRolePrivileges(client, replacePrivileges, targetBusinessUnitId)
            : basePrivileges.ToDictionary(
                privilege => BuildPrivilegeKey(privilege.PrivilegeId, privilege.RecordFilterId),
                privilege => new DesiredSecurityRolePrivilege(
                    privilege.PrivilegeId,
                    privilege.PrivilegeName,
                    privilege.DepthValue,
                    targetBusinessUnitId,
                    privilege.RecordFilterId));

        if (additionalPrivileges is not null)
        {
            foreach (var privilege in ResolveDesiredSecurityRolePrivileges(client, additionalPrivileges, targetBusinessUnitId).Values)
            {
                desired[BuildPrivilegeKey(privilege.PrivilegeId, privilege.RecordFilterId)] = privilege;
            }
        }

        if (removePrivileges is not null)
        {
            var removeSelectors = ResolveSecurityRolePrivilegeSelectors(client, removePrivileges);
            foreach (var removeSelector in removeSelectors)
            {
                if (removeSelector.RecordFilterId.HasValue)
                {
                    desired.Remove(BuildPrivilegeKey(removeSelector.PrivilegeId, removeSelector.RecordFilterId));
                    continue;
                }

                foreach (var key in desired.Keys.Where(key => key.StartsWith(removeSelector.PrivilegeId.ToString("N"), StringComparison.OrdinalIgnoreCase)).ToList())
                {
                    desired.Remove(key);
                }
            }
        }

        return desired.Values
            .OrderBy(privilege => privilege.PrivilegeName ?? privilege.PrivilegeId.ToString("D"), StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    private static Dictionary<string, DesiredSecurityRolePrivilege> ResolveDesiredSecurityRolePrivileges(
        ServiceClient client,
        IEnumerable<SecurityRolePrivilegeSpec> specs,
        Guid targetBusinessUnitId)
    {
        var desired = new Dictionary<string, DesiredSecurityRolePrivilege>(StringComparer.OrdinalIgnoreCase);
        var index = 0;
        foreach (var spec in specs)
        {
            index++;
            var privilege = ResolveSecurityRolePrivilege(client, spec, $"privileges[{index - 1}]");
            desired[BuildPrivilegeKey(privilege.PrivilegeId, privilege.RecordFilterId)] = privilege with
            {
                BusinessUnitId = targetBusinessUnitId,
            };
        }

        return desired;
    }

    private static List<ResolvedSecurityRolePrivilegeSelector> ResolveSecurityRolePrivilegeSelectors(
        ServiceClient client,
        IEnumerable<SecurityRolePrivilegeSelectorSpec> specs)
    {
        var selectors = new List<ResolvedSecurityRolePrivilegeSelector>();
        var index = 0;
        foreach (var spec in specs)
        {
            index++;
            selectors.Add(ResolveSecurityRolePrivilegeSelector(client, spec, $"removePrivileges[{index - 1}]"));
        }

        return selectors;
    }

    private static DesiredSecurityRolePrivilege ResolveSecurityRolePrivilege(
        ServiceClient client,
        SecurityRolePrivilegeSpec spec,
        string propertyPrefix)
    {
        var selector = ResolveSecurityRolePrivilegeSelector(
            client,
            new SecurityRolePrivilegeSelectorSpec
            {
                PrivilegeId = spec.PrivilegeId,
                PrivilegeName = spec.PrivilegeName,
                RecordFilterId = spec.RecordFilterId,
            },
            propertyPrefix);
        var depthValue = ResolvePrivilegeDepth(spec.Depth, propertyPrefix);

        return new DesiredSecurityRolePrivilege(
            selector.PrivilegeId,
            selector.PrivilegeName,
            depthValue,
            Guid.Empty,
            selector.RecordFilterId);
    }

    private static ResolvedSecurityRolePrivilegeSelector ResolveSecurityRolePrivilegeSelector(
        ServiceClient client,
        SecurityRolePrivilegeSelectorSpec spec,
        string propertyPrefix)
    {
        if (!string.IsNullOrWhiteSpace(spec.PrivilegeId))
        {
            return new ResolvedSecurityRolePrivilegeSelector(
                Guid.Parse(spec.PrivilegeId),
                spec.PrivilegeName,
                string.IsNullOrWhiteSpace(spec.RecordFilterId) ? null : Guid.Parse(spec.RecordFilterId));
        }

        ValidateRequired(spec.PrivilegeName, $"{propertyPrefix}.privilegeName");
        var privilege = RetrieveSingle(
            client,
            "privilege",
            new ColumnSet("privilegeid", "name"),
            new ConditionExpression("name", ConditionOperator.Equal, spec.PrivilegeName));
        return new ResolvedSecurityRolePrivilegeSelector(
            privilege.Id,
            privilege.GetAttributeValue<string>("name"),
            string.IsNullOrWhiteSpace(spec.RecordFilterId) ? null : Guid.Parse(spec.RecordFilterId));
    }

    private static int ResolvePrivilegeDepth(string? rawValue, string propertyPrefix)
    {
        ValidateRequired(rawValue, $"{propertyPrefix}.depth");
        return rawValue!.Trim().ToLowerInvariant() switch
        {
            "basic" or "user" => 0,
            "local" or "business-unit" or "businessunit" => 1,
            "deep" or "parent-child" or "parent-child-business-units" => 2,
            "global" or "organization" or "org" => 3,
            "record-filter" or "recordfilter" => 4,
            _ when int.TryParse(rawValue, out var parsed) && parsed >= 0 && parsed <= 4 => parsed,
            _ => throw new InvalidOperationException(
                $"Unsupported privilege depth '{rawValue}' for {propertyPrefix}. Use basic, local, deep, global, or record-filter."),
        };
    }

    private static string BuildPrivilegeKey(Guid privilegeId, Guid? recordFilterId)
    {
        return $"{privilegeId:N}|{recordFilterId?.ToString("N") ?? "none"}";
    }

    private static void ReplaceRolePrivileges(ServiceClient client, Guid roleId, IReadOnlyCollection<DesiredSecurityRolePrivilege> privileges)
    {
        var request = new ReplacePrivilegesRoleRequest
        {
            RoleId = roleId,
            Privileges = privileges.Select(BuildRolePrivilege).ToArray(),
        };
        client.Execute(request);
    }

    private static RolePrivilege BuildRolePrivilege(DesiredSecurityRolePrivilege privilege)
    {
        if (privilege.RecordFilterId.HasValue && !string.IsNullOrWhiteSpace(privilege.PrivilegeName))
        {
            return new RolePrivilege(
                privilege.DepthValue,
                privilege.PrivilegeId,
                privilege.BusinessUnitId,
                privilege.PrivilegeName,
                privilege.RecordFilterId.Value);
        }
        if (!string.IsNullOrWhiteSpace(privilege.PrivilegeName))
        {
            return new RolePrivilege(
                privilege.DepthValue,
                privilege.PrivilegeId,
                privilege.BusinessUnitId,
                privilege.PrivilegeName);
        }

        return new RolePrivilege(privilege.DepthValue, privilege.PrivilegeId);
    }

    private static void EnsureEditableRole(Entity role, bool allowSystemGeneratedRoleUpdate)
    {
        if (allowSystemGeneratedRoleUpdate)
        {
            return;
        }

        if (ReadBoolAttribute(role, "issytemgenerated") == true)
        {
            throw new InvalidOperationException(
                "System-generated or predefined security roles are not updated by default. Copy the role or set allowSystemGeneratedRoleUpdate to true.");
        }
    }

    private static void EnsureSecurityRoleInSolution(ServiceClient client, Guid roleId, string? solutionUniqueName)
    {
        if (string.IsNullOrWhiteSpace(solutionUniqueName))
        {
            return;
        }

        var solution = RetrieveSingle(
            client,
            "solution",
            new ColumnSet("uniquename", "friendlyname"),
            new ConditionExpression("uniquename", ConditionOperator.Equal, solutionUniqueName));

        if (IsComponentAlreadyInSolution(client, solution.Id, roleId, 20))
        {
            return;
        }

        client.Execute(new AddSolutionComponentRequest
        {
            ComponentId = roleId,
            ComponentType = 20,
            SolutionUniqueName = solutionUniqueName,
            AddRequiredComponents = true,
            DoNotIncludeSubcomponents = false,
        });
    }

    private static void EnsureSecurityRolePrivilegesInSolution(ServiceClient client, Guid roleId, string solutionUniqueName)
    {
        var solution = RetrieveSingle(
            client,
            "solution",
            new ColumnSet("uniquename", "friendlyname"),
            new ConditionExpression("uniquename", ConditionOperator.Equal, solutionUniqueName));

        var privileges = LoadRolePrivilegesByRoleId(client, new[] { roleId }).GetValueOrDefault(roleId, new List<SecurityRolePrivilegeRow>());
        foreach (var privilege in privileges)
        {
            if (IsComponentAlreadyInSolution(client, solution.Id, privilege.RolePrivilegeId, 21))
            {
                continue;
            }

            client.Execute(new AddSolutionComponentRequest
            {
                ComponentId = privilege.RolePrivilegeId,
                ComponentType = 21,
                SolutionUniqueName = solutionUniqueName,
                AddRequiredComponents = false,
                DoNotIncludeSubcomponents = true,
            });
        }
    }

    private static void ApplyRoleStringField(Entity entity, string logicalName, string? value)
    {
        if (value is not null)
        {
            entity[logicalName] = value;
        }
    }

    private static int? ResolveInheritanceMode(string? rawValue)
    {
        if (string.IsNullOrWhiteSpace(rawValue))
        {
            return null;
        }

        return rawValue.Trim().ToLowerInvariant() switch
        {
            "team-only" or "teamonly" => 0,
            "direct-user-and-team" or "directuserandteam" or "basic-and-team" => 1,
            _ when int.TryParse(rawValue, out var parsed) && parsed is 0 or 1 => parsed,
            _ => throw new InvalidOperationException(
                $"Unsupported inheritanceMode '{rawValue}'. Use team-only or direct-user-and-team."),
        };
    }

    private static List<string> BuildSecurityRoleWarnings(string? solutionUniqueName, int privilegeCount)
    {
        var warnings = new List<string>();
        if (string.IsNullOrWhiteSpace(solutionUniqueName))
        {
            warnings.Add("The security role change was applied live without attaching the role to a named unmanaged solution.");
        }
        if (privilegeCount == 0)
        {
            warnings.Add("The security role currently has no privileges. It will not be usable until privileges are added.");
        }

        return warnings;
    }

    private sealed class SecurityRoleListSpec
    {
        public string? SolutionUniqueName { get; init; }

        public string? BusinessUnitId { get; init; }

        public string? BusinessUnitName { get; init; }

        public bool? IncludePrivileges { get; init; }

        public bool? IncludeSystemGenerated { get; init; }
    }

    private sealed class SecurityRoleInspectSpec
    {
        public string? RoleId { get; init; }

        public string? Name { get; init; }

        public string? BusinessUnitId { get; init; }

        public string? BusinessUnitName { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? IncludePrivileges { get; init; }
    }

    private sealed class SecurityRoleCreateSpec
    {
        public string Name { get; init; } = string.Empty;

        public string? BusinessUnitId { get; init; }

        public string? BusinessUnitName { get; init; }

        public string? Description { get; init; }

        public string? AppliesTo { get; init; }

        public string? SummaryOfCoreTablePermissions { get; init; }

        public string? InheritanceMode { get; init; }

        public bool? IsAutoAssigned { get; init; }

        public string? CopyFromRoleId { get; init; }

        public string? CopyFromRoleName { get; init; }

        public string? CopyFromBusinessUnitId { get; init; }

        public string? CopyFromBusinessUnitName { get; init; }

        public string? SolutionUniqueName { get; init; }

        public List<SecurityRolePrivilegeSpec>? Privileges { get; init; }

        public List<SecurityRolePrivilegeSpec>? AdditionalPrivileges { get; init; }

        public List<SecurityRolePrivilegeSelectorSpec>? RemovePrivileges { get; init; }
    }

    private sealed class SecurityRoleUpdateSpec
    {
        public string? RoleId { get; init; }

        public string? Name { get; init; }

        public string? BusinessUnitId { get; init; }

        public string? BusinessUnitName { get; init; }

        public string? NewName { get; init; }

        public string? Description { get; init; }

        public string? AppliesTo { get; init; }

        public string? SummaryOfCoreTablePermissions { get; init; }

        public string? InheritanceMode { get; init; }

        public bool? IsAutoAssigned { get; init; }

        public string? SolutionUniqueName { get; init; }

        public bool? AllowSystemGeneratedRoleUpdate { get; init; }

        public List<SecurityRolePrivilegeSpec>? Privileges { get; init; }

        public List<SecurityRolePrivilegeSpec>? AdditionalPrivileges { get; init; }

        public List<SecurityRolePrivilegeSelectorSpec>? RemovePrivileges { get; init; }
    }

    private sealed class SecurityRolePrivilegeSpec
    {
        public string? PrivilegeId { get; init; }

        public string? PrivilegeName { get; init; }

        public string? Depth { get; init; }

        public string? RecordFilterId { get; init; }
    }

    private sealed class SecurityRolePrivilegeSelectorSpec
    {
        public string? PrivilegeId { get; init; }

        public string? PrivilegeName { get; init; }

        public string? RecordFilterId { get; init; }
    }

    private sealed record SecurityRolePrivilegeRow(
        Guid RolePrivilegeId,
        Guid RoleId,
        Guid PrivilegeId,
        string? PrivilegeName,
        int DepthValue,
        Guid? RecordFilterId);

    private sealed record DesiredSecurityRolePrivilege(
        Guid PrivilegeId,
        string? PrivilegeName,
        int DepthValue,
        Guid BusinessUnitId,
        Guid? RecordFilterId);

    private sealed record ResolvedSecurityRolePrivilegeSelector(
        Guid PrivilegeId,
        string? PrivilegeName,
        Guid? RecordFilterId);
}
