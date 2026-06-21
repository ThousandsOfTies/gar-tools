*** Variables ***
${UART}                         sysbus.cpu.uartSemihosting
${ELF}                          https://dl.antmicro.com/projects/renode/xtensa-sample-controller-zephyr-hello-world.elf-s_293544-4be60f8a3891e70c30e1e8a471df4ad12ab08144

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

