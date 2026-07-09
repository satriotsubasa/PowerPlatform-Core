using Xunit;

public sealed class EnvironmentVariableTypesTests
{
    [Theory]
    [InlineData(null, 100000000)]
    [InlineData("", 100000000)]
    [InlineData("string", 100000000)]
    [InlineData("String", 100000000)]
    [InlineData("text", 100000000)]
    [InlineData("number", 100000001)]
    [InlineData("integer", 100000001)]
    [InlineData("int", 100000001)]
    [InlineData("decimal", 100000001)]
    [InlineData("double", 100000001)]
    [InlineData("boolean", 100000002)]
    [InlineData("bool", 100000002)]
    [InlineData("yesno", 100000002)]
    [InlineData("twooptions", 100000002)]
    [InlineData("json", 100000003)]
    [InlineData("datasource", 100000004)]
    [InlineData("data-source", 100000004)]
    [InlineData("secret", 100000005)]
    public void Parse_MapsFriendlyNamesToOptionSetValues(string? input, int expected)
    {
        Assert.Equal(expected, EnvironmentVariableTypes.Parse(input));
    }

    [Fact]
    public void Parse_AcceptsRawNumericOptionSetValue()
    {
        Assert.Equal(100000003, EnvironmentVariableTypes.Parse("100000003"));
    }

    [Fact]
    public void Parse_RejectsUnknownTypeName()
    {
        Assert.Throws<InvalidOperationException>(() => EnvironmentVariableTypes.Parse("colour"));
    }
}
