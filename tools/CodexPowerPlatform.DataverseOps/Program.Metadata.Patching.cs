using Microsoft.PowerPlatform.Dataverse.Client;
using Microsoft.Xrm.Sdk;
using Microsoft.Xrm.Sdk.Query;

internal static partial class Program
{
    private static object ExecutePatchFormXml(ServiceClient client, FormXmlPatchSpec spec)
    {
        ValidateRequired(spec.EntityLogicalName, "entityLogicalName");
        ValidateRequired(spec.FormName, "formName");

        var form = RetrieveSingle(
            client,
            "systemform",
            new ColumnSet("formxml", "name", "objecttypecode", "type"),
            new ConditionExpression("objecttypecode", ConditionOperator.Equal, spec.EntityLogicalName),
            new ConditionExpression("name", ConditionOperator.Equal, spec.FormName),
            new ConditionExpression("type", ConditionOperator.Equal, spec.FormType ?? 2));

        var formXml = form.GetAttributeValue<string>("formxml")
            ?? throw new InvalidOperationException($"Form '{spec.FormName}' does not contain formxml.");
        var updated = FormXmlPatchEngine.ApplyFormXmlPatch(formXml, spec.Operations);
        if (!updated.Changed)
        {
            return new
            {
                success = true,
                mode = "patch-form-xml",
                formId = form.Id,
                entityLogicalName = spec.EntityLogicalName,
                formName = spec.FormName,
                appliedOperations = updated.AppliedOperations,
                createdNodes = updated.CreatedNodes,
                message = "No form XML changes were needed.",
            };
        }

        var patch = new Entity("systemform", form.Id)
        {
            ["formxml"] = updated.Xml,
        };
        client.Update(patch);

        return new
        {
            success = true,
            mode = "patch-form-xml",
            formId = form.Id,
            entityLogicalName = spec.EntityLogicalName,
            formName = spec.FormName,
            appliedOperations = updated.AppliedOperations,
            createdNodes = updated.CreatedNodes,
        };
    }

    private static object ExecutePatchFormRibbon(ServiceClient client, FormRibbonPatchSpec spec)
    {
        ValidateRequired(spec.EntityLogicalName, "entityLogicalName");
        ValidateRequired(spec.FormName, "formName");

        var form = RetrieveSingle(
            client,
            "systemform",
            new ColumnSet("formxml", "name", "objecttypecode", "type"),
            new ConditionExpression("objecttypecode", ConditionOperator.Equal, spec.EntityLogicalName),
            new ConditionExpression("name", ConditionOperator.Equal, spec.FormName),
            new ConditionExpression("type", ConditionOperator.Equal, spec.FormType ?? 2));

        var formXml = form.GetAttributeValue<string>("formxml")
            ?? throw new InvalidOperationException($"Form '{spec.FormName}' does not contain formxml.");
        var updated = FormXmlPatchEngine.ApplyFormRibbonPatch(
            formXml,
            spec.Operations,
            spec.CreateRibbonDiffXmlIfMissing);
        if (!updated.Changed)
        {
            return new
            {
                success = true,
                mode = "patch-form-ribbon",
                formId = form.Id,
                entityLogicalName = spec.EntityLogicalName,
                formName = spec.FormName,
                appliedOperations = updated.AppliedOperations,
                createdNodes = updated.CreatedNodes,
                message = "No form ribbon changes were needed.",
            };
        }

        var patch = new Entity("systemform", form.Id)
        {
            ["formxml"] = updated.Xml,
        };
        client.Update(patch);

        return new
        {
            success = true,
            mode = "patch-form-ribbon",
            formId = form.Id,
            entityLogicalName = spec.EntityLogicalName,
            formName = spec.FormName,
            appliedOperations = updated.AppliedOperations,
            createdNodes = updated.CreatedNodes,
        };
    }
}
