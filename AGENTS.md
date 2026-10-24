# Web simulator work

This rule applies to every GAR App and Product simulator, regardless of target.
Before designing or changing a panel, read
[Web simulator design principles](web-simulator/DESIGN_PRINCIPLES.md) for the
user's intent, anti-patterns, and completion criteria, then
[the component guide](web-simulator/README.md) for APIs and examples.
Inventory existing shared components before writing a panel.

- Preserve the user's "生の部品感": devices should remain recognisable as parts
  with their own physical/configuration facts and basic interactions. A viewer
  should be able to imagine another use for them without knowing the Product.
  Visual reuse is a requirement alongside code reuse. Do not replace a rotary
  encoder with a volume-only widget, or hide servos entirely inside a pet
  animation. Product visualisations may accompany the visible parts.
- Keep the display boundary visible while rendering the App's actual screen
  inside it. Product styling, labels, and layout must preserve each shared
  part's recognisable identity and basic interactions.
- Preserve part identity while adapting input to mouse and keyboard. A rotary
  knob should show its turning marker and retain simple step buttons and key
  input; do not require tracing a circular drag. Wheel input must not capture
  normal page scrolling when the knob is unfocused.

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
  Verify that its appearance and controls still explain the part when Product
  names and use-specific labels are removed; review the actual Product panel
  for the same visible part identity.
  Test its public events/properties and the Product's adapter wiring separately.
- If a control is genuinely Product-specific, leave it in the Product and name
  the dependency explicitly; do not move it into the shared library merely to
  shorten the Product page.
