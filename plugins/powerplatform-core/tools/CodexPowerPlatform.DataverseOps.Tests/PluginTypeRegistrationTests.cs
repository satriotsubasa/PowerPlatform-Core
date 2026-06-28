using Microsoft.Xrm.Sdk;
using Xunit;

public sealed class PluginTypeRegistrationTests
{
    [Fact]
    public void BuildPluginTypeEntity_SetsTypeNameAndAssemblyReference()
    {
        var assemblyId = Guid.NewGuid();

        var entity = PluginTypeRegistration.BuildPluginTypeEntity(assemblyId, "  My.Plugins.AccountCreate  ");

        Assert.Equal("plugintype", entity.LogicalName);
        Assert.Equal("My.Plugins.AccountCreate", entity.GetAttributeValue<string>("typename"));
        Assert.Equal("My.Plugins.AccountCreate", entity.GetAttributeValue<string>("name"));
        Assert.Equal("My.Plugins.AccountCreate", entity.GetAttributeValue<string>("friendlyname"));

        var reference = entity.GetAttributeValue<EntityReference>("pluginassemblyid");
        Assert.Equal("pluginassembly", reference.LogicalName);
        Assert.Equal(assemblyId, reference.Id);
    }

    [Fact]
    public void BuildPluginTypeEntity_RejectsEmptyTypeName()
    {
        Assert.Throws<InvalidOperationException>(
            () => PluginTypeRegistration.BuildPluginTypeEntity(Guid.NewGuid(), "   "));
    }
}
