# Luckfox RK3506 Hardware Template

This directory is a deliberately empty assignment template. `gar hw init`
copies these CSV headers to a product workspace, where product requirements
are bound to the board resources in `../capabilities.json`.

Do not add an application's display, input, media, or wiring rows here. Those
facts belong respectively to the product requirement and machine-local
binding, because neither is an invariant of the RK3506 board.
