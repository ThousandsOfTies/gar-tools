*** Variables ***
${UART}                         sysbus.cpu.uartSemihosting
${ELF}                          SET_BY_RUN_PY_AFTER_SHA256_VERIFICATION

*** Keywords ***
Create M5Status Tiny Machine
    Execute Command             using sysbus
    Execute Command             mach create "m5status-tiny"
    Execute Command             machine LoadPlatformDescription @platforms/cpus/xtensa-sample-controller.repl
    Execute Command             sysbus LoadELF @${ELF}
    Execute Command             cpu PC 0x50000000

*** Test Cases ***
M5Status Tiny Firmware Boots And Writes UART
    Create M5Status Tiny Machine
    Create Terminal Tester      ${UART}

    Start Emulation

    Wait For Line On Uart       Booting Zephyr OS
    Wait For Line On Uart       Hello World! qemu_xtensa
