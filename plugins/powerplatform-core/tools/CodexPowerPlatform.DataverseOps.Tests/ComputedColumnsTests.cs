using Xunit;

public sealed class ComputedColumnsTests
{
    [Fact]
    public void RejectHeadlessCreation_NoOpWhenNeitherSet()
    {
        // A normal (non-computed) column request must pass through untouched.
        ComputedColumns.RejectHeadlessCreation(null, null);
        ComputedColumns.RejectHeadlessCreation("", "   ");
    }

    [Theory]
    [InlineData("formula", null)]
    [InlineData("calculated", null)]
    [InlineData("rollup", null)]
    [InlineData(null, "<Activity/>")]
    public void RejectHeadlessCreation_ThrowsActionableRedirectWhenComputed(string? sourceType, string? formulaDefinition)
    {
        var ex = Assert.Throws<InvalidOperationException>(
            () => ComputedColumns.RejectHeadlessCreation(sourceType, formulaDefinition));
        Assert.Contains("maker portal", ex.Message);
        Assert.Contains("solution import", ex.Message);
    }
}
