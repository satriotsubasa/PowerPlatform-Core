using Xunit;

public sealed class FormXmlPatchEngineTests
{
    [Fact]
    public void ApplyFormXmlPatch_ReplacesHeaderChildren()
    {
        const string formXml = """
            <form>
              <header>
                <rows>
                  <row id="old" />
                </rows>
              </header>
              <tabs />
            </form>
            """;

        var result = FormXmlPatchEngine.ApplyFormXmlPatch(
            formXml,
            [
                new XmlPatchOperationSpec
                {
                    Type = "replace-children",
                    TargetXPath = ".//header",
                    Xml = "<rows><row id=\"new\" /></rows>"
                }
            ]);

        Assert.True(result.Changed);
        Assert.Contains("id=\"new\"", result.Xml);
        Assert.DoesNotContain("id=\"old\"", result.Xml);
    }

    [Fact]
    public void ApplyFormRibbonPatch_CreatesRibbonDiffXmlWhenMissing()
    {
        const string formXml = """
            <form>
              <tabs />
            </form>
            """;

        var result = FormXmlPatchEngine.ApplyFormRibbonPatch(
            formXml,
            [
                new XmlPatchOperationSpec
                {
                    Type = "append-child",
                    TargetXPath = ".",
                    Xml = "<CustomActions><CustomAction Id=\"contoso.Action\" /></CustomActions>"
                }
            ],
            createRibbonDiffXmlIfMissing: true);

        Assert.True(result.Changed);
        Assert.Contains("<RibbonDiffXml>", result.Xml);
        Assert.Contains("contoso.Action", result.Xml);
        Assert.Contains("RibbonDiffXml", result.CreatedNodes);
    }

    [Fact]
    public void ApplyFormXmlPatch_ThrowsWhenTargetXPathDoesNotMatch()
    {
        const string formXml = """
            <form>
              <tabs />
            </form>
            """;

        var exception = Assert.Throws<InvalidOperationException>(() =>
            FormXmlPatchEngine.ApplyFormXmlPatch(
                formXml,
                [
                    new XmlPatchOperationSpec
                    {
                        Type = "remove-element",
                        TargetXPath = ".//header"
                    }
                ]));

        Assert.Contains("targetXPath", exception.Message);
    }
}
