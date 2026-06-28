using Xunit;

public sealed class FetchXmlPagingTests
{
    [Fact]
    public void ApplyPage_InjectsCountPageAndTotalCountAndStripsTop()
    {
        const string fetch = "<fetch top=\"5\"><entity name=\"account\"><attribute name=\"name\" /></entity></fetch>";

        var result = FetchXmlPaging.ApplyPage(fetch, 2, 100, null);

        Assert.Contains("count=\"100\"", result);
        Assert.Contains("page=\"2\"", result);
        Assert.Contains("returntotalrecordcount=\"true\"", result);
        Assert.DoesNotContain("top=", result);
    }

    [Fact]
    public void ApplyPage_EmbedsAttributeEscapedPagingCookieWhenProvided()
    {
        const string fetch = "<fetch><entity name=\"contact\" /></fetch>";

        var result = FetchXmlPaging.ApplyPage(fetch, 2, 50, "<cookie page=\"1\" />");

        Assert.Contains("paging-cookie=", result);
        Assert.Contains("&lt;cookie", result);
    }

    [Fact]
    public void ApplyPage_OmitsPagingCookieOnFirstPage()
    {
        const string fetch = "<fetch><entity name=\"contact\" /></fetch>";

        var result = FetchXmlPaging.ApplyPage(fetch, 1, 50, null);

        Assert.DoesNotContain("paging-cookie", result);
    }

    [Fact]
    public void ApplyPage_RejectsNonFetchRoot()
    {
        Assert.Throws<InvalidOperationException>(
            () => FetchXmlPaging.ApplyPage("<query><entity name=\"a\" /></query>", 1, 10, null));
    }

    [Fact]
    public void GetEntityName_ReturnsTheEntityName()
    {
        const string fetch = "<fetch><entity name=\"dhx_invoice\"><attribute name=\"dhx_name\" /></entity></fetch>";

        Assert.Equal("dhx_invoice", FetchXmlPaging.GetEntityName(fetch));
    }
}
