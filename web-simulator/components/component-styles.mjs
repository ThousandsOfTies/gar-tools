/** Load a component's private stylesheet once inside its own ShadowRoot. */
export function installComponentStyles(root) {
  if (!(root instanceof ShadowRoot)) throw new TypeError('Component styles require a ShadowRoot');
  const href = new URL('./pwm-components.css', import.meta.url).href;
  if ([...root.querySelectorAll('link[rel="stylesheet"]')].some(link => link.href === href)) return;
  const link = root.ownerDocument.createElement('link');
  link.rel = 'stylesheet';
  link.href = href;
  root.prepend(link);
}
