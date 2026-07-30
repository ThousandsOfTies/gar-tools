# gar-tools

Gapless Agent Runtime（GAR）が利用する、target固有の定義とsimulation
runtimeをまとめたリポジトリです。通常の操作入口はこのリポジトリ内の個別
scriptではなく、`GaplessAgentRuntime`の`gar` CLIです。

主な内容:

- `targets/linux-device/`: Linux `/dev`互換runtimeとlocal Docker環境
- `targets/esp32/`: ESP32/M5Stack向けWokwi、QEMU、Renode、実機probe
- `targets/luckfox-rv1106/`: Luckfox Pico Plus/Pro/Max向けhardware定義、
  application雛形、simulation helper
- `targets/*/target.json`: `gar setup`が検証・選択するtarget manifest
- `docs/`: simulation設定とAI agent向けの補足資料

各targetの`hardware/*.csv`はhardware定義のテンプレートです。product固有の
定義は`gar hw init`でworkspaceへ展開してから編集します。

## GARから使う

`GaplessAgentRuntime`のrootでtargetとenvironmentを選択した後、用途ごとの
commandを実行します。

```bash
scripts/gar setup
scripts/gar hw init --dir path/to/product/hardware

# Linux simulationの代表的な流れ
scripts/gar sim host start
scripts/gar sim runtime build
scripts/gar sim runtime deploy
scripts/gar sim runtime start
scripts/gar sim runtime diag --json
```

application artifactは`gar sim app build/deploy`、実機用artifactは
`gar target build/deploy`で扱います。workspaceを複数登録している場合は
各commandへ`--workspace NAME`を指定します。

## runtimeを個別に開発する

Linux runtimeだけを手元で変更・確認するときは、リポジトリrootのMakefileを
直接利用できます。

```bash
make
make check
make clean
```

`make`は通常のLinux runtimeだけをbuildし、既定のcross compilerは
`aarch64-linux-gnu-gcc`です。local host向けには`make linux-runtime CC=gcc`を
使います。sample applicationは`make examples`、GPIO CUSEなどの実験実装は
`make experiments`へ分離されており、通常buildには含まれません。
`make check`には、siblingの`GaplessAgentRuntime`（別の場所にある場合は
`GAR_RUNTIME_ROOT`で指定）、Node.js、host C compilerが必要です。

GAR経由のbuildでは、選択したsimulation environmentに応じて`CC`と
`GAR_SIM_ARCH`が設定されます。

## GPIO CUSE spike

`targets/linux-device/runtime/gpio-stub/`の`cuse_gpio`は、GPIO chip metadataと
bridge連携を確認するために残している実験実装です。

Linux GPIO chardevのline request ioctlは呼び出し元processへ新しいfdを返します。
CUSE daemonだけではそのfdを別processへ渡せないため、既存applicationに対する
完全透過なGPIO実装にはなりません。現在のsimulation runtimeではkernel-backedな
`gpio-sim`を利用します。詳細は`targets/linux-device/runtime/gpio-stub/README.md`
を参照してください。
