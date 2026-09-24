# Web simulator work

This rule applies to every GAR App and Product simulator, regardless of target.
Inventory existing shared components before writing a panel. When available,
read `web-simulator/README.md` for component APIs and examples.

- Put reusable device appearance, local interaction, and its public API in
  `web-simulator/components/`. Keep internal DOM and styling in Shadow DOM.
  Expose physical/configuration facts as attributes or properties, input as
  composed events, and host-page appearance through CSS/custom properties.
- Keep Product-specific device mapping, bridge message interpretation, commands,
  scenarios, and endpoints in the Product's panel adapter (for example,
  `panel/studio.js`). A shared transport is acceptable only when its protocol is
  reusable and its connection is configurable.
- Use Product `panel/index.html` to compose tags. Do not duplicate a component's
  internal markup or reach into its Shadow DOM from Product CSS or JavaScript.
- Before calling a new part reusable, demonstrate it outside the originating
  Product with two differently configured instances and independent state.
  Test its public events/properties and the Product's adapter wiring separately.
- If a control is genuinely Product-specific, leave it in the Product and name
  the dependency explicitly; do not move it into the shared library merely to
  shorten the Product page.
