# Client Customization

Use this reference for model-driven form scripts, client APIs, and lightweight web resources.

## Core Rules

- Use `executionContext.getFormContext()` and `formContext` when adding new code. If the repo already uses `Xrm.Page`, preserve local consistency unless the user asked for a modernization pass.
- Use explicit namespaces for JS or TS modules.
- Keep handler functions small and named for their registration target.
- Prefer `Xrm.WebApi` for Dataverse calls from form code.
- Use notifications and clear error messages for user-facing failures.
- If the repo has no explicit namespace convention, preserve the existing file or module pattern instead of inventing a new house-style namespace.

## Event Handler Pattern

Use clear entry points for:

- `OnLoad`
- `OnSave`
- `OnChange` for specific columns

Register only named exported functions with the expected signature. Document which form and field bindings must exist when reporting the final change.

When the task includes headless form library registration or handler binding, prefer the reusable helper at `scripts/update_form_events.py` instead of assuming the maker UI is required.
When the task includes headless upload or update of the underlying JavaScript, HTML, CSS, XML, or image web resource file, prefer `scripts/sync_webresource.py`.
When the task includes form XML or RibbonDiffXml, prefer `scripts/patch_form_xml.py`, `scripts/patch_form_ribbon.py`, `scripts/update_main_form.py`, or a direct metadata update. If those paths cannot express the change, stop and explain the gap before considering a solution package import.

## Suggested Script Shape

```javascript
var Crm = Crm || {};
Crm.Account = (function () {
  async function onLoad(executionContext) {
    var formContext = executionContext.getFormContext();
    void formContext;
  }

  function onChangeName(executionContext) {
    var formContext = executionContext.getFormContext();
    void formContext;
  }

  return {
    onLoad: onLoad,
    onChangeName: onChangeName
  };
})();
```

If the repo uses TypeScript, follow the existing build pipeline and emit the expected JavaScript web resource artifact rather than introducing a second pattern.
If the repo uses classic namespace-based JavaScript rather than modules, preserve that existing pattern and handler names instead of forcing a new module style midstream.

## Xrm.WebApi Usage

Prefer:

- `retrieveRecord`
- `retrieveMultipleRecords`
- `createRecord`
- `updateRecord`
- `execute`

Select only the fields you need. Use logical names, not display names.

For client-side filtering or lookups:

- keep network calls minimal
- guard against null attribute values
- handle unsaved form state explicitly

## Form UX Rules

- Do not block form load unnecessarily.
- Avoid long synchronous work.
- Use form notifications or control notifications for actionable errors.
- Clear notifications after successful recovery.
- Do not hard-code environment URLs or tenant-specific values into web resources.

## HTML And CSS Web Resources

Use HTML web resources only for focused UI that fits inside the model-driven experience. If the request needs a reusable, data-rich, or interactive control, open [pcf-controls.md](pcf-controls.md) instead.

When using HTML or CSS web resources:

- keep them lightweight
- avoid unsupported page DOM coupling
- communicate with the parent form through supported APIs only

## Validation

Before finishing:

- confirm handler names match the form registration
- confirm referenced field logical names exist
- confirm namespace and file naming align with the publisher prefix or repo convention
- confirm build output exists if TypeScript is used
