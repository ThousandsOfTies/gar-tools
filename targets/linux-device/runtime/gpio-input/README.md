# GPIO input configuration

`python/gar_gpio_debounce.py` applies an optional Product-selected GPIO v2
debounce period to python-periphery input handles. Copy this reusable module
beside the Python application in its deployment artifact. Call `configure_inputs`
after setting the inputs' edge and bias properties, before starting readers.
The default should be zero for compatibility; Products choose a physical period.
The helper preserves edge selection, bias, inversion and periphery's realtime
event clock. A nonzero request on a legacy backend fails explicitly.

The kernel uses hardware support or software filtering; the requested period
does not guarantee exact microsecond timing. Long filters can suppress valid
quadrature transitions. Qualify the period on each physical target.
