# gar-tools

Gapless Agent Runtime のシミュレーション環境で使うツール群です。

主な内容:

- `targets/linux-device/`: Linux `/dev` 互換 runtime（EC2 Graviton などで利用）
  - `targets/linux-device/runtime/`: I2C/GPIO/SPI CUSE stubs、web-bridge、テストアプリ
- `targets/esp32/`: ESP32/M5Stack firmware artifact を QEMU/Renode/BT SPP へ接続する足場
  - `targets/esp32/renode/m5status-tiny/`: Renode で動く最小 Xtensa firmware smoke test
- `targets/luckfox-rv1106/`: Luckfox Pico Plus/Pro/Max (RV1106) 向けの target 雛形
  - `targets/luckfox-rv1106/app-template/`: C/C++ アプリ骨組みと cross build 用 Makefile/CMake
  - `targets/luckfox-rv1106/toolchain/`: Buildroot SDK toolchain 設定テンプレート
  - `targets/luckfox-rv1106/hardware/`: SC3336 + ILI9341 + KY-040 の初期ハードウェア定義
- `targets/*/target.json`: `gar setup` が読む target manifest。推奨 backend と tools root を宣言する。
- `docs/`: シミュレーション設定と AI エージェント操作メモ

## Build

```bash
make
make clean
```

Codespace build VM では ARM64 向けにビルドします。EC2 への転送、simulation runtime 操作、Virtual Hardware 操作は WSL hub 側の Gapless Agent Runtime から行います。

## GPIO CUSE spike

`targets/linux-device/runtime/gpio-stub/` に `cuse_gpio` の実装スパイクがあります。GPIO chip metadata と bridge 連携の検証用です。

注意: Linux GPIO chardev の line request ioctl は呼び出し元プロセスに新しい fd を返すため、CUSE だけでは既存アプリの `gpio_shim.so` を完全透過に置き換えられません。詳細は `targets/linux-device/runtime/gpio-stub/README.md` を参照してください。

2026-06-02 時点の確認:

- Codespace build VM で `aarch64-linux-gnu-gcc` による ARM64 ビルドが通る。
- EC2 Graviton に `/home/ubuntu/cuse_gpio` としてデプロイ済み。
- EC2 では既存の `/dev/gpiochip0` が存在するため、衝突回避名 `/dev/gar-gpiochip0` で CUSE 起動を確認。
- `GPIO_GET_CHIPINFO_IOCTL` は `name=gpiochip0_sim`, `label=gar CUSE GPIO`, `lines=54` を返す。
- LED/Button の bridge 連携と line request fd 問題は未解決。
