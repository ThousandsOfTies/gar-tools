# cuse_spi — CUSE SPI stub (MFRC-522 sim)

LD_PRELOAD の `spi_shim.so` を置き換える、CUSE ベースの SPI スタブです。
本物の `/dev/spidev0.0` を userspace で生やし、未改変の `sensor_demo`
バイナリがそのまま MFRC-522（RFID リーダ）を読めるようにします。

`i2c-stub/cuse_i2c`（I2C）と同じ構造で、デバイス固有のレジスタ模擬は
`mfrc522_sim.c` に分離しています。カード提示状態は web bridge
（`GAR_HW_SIM_SOCK` または `GAR_RUNTIME_DIR/hw_sim.sock`）から取得するので、
`gar sim io set --device rfid --uid <UID>` でタップを注入できます。

## なぜ CUSE か（spi_shim との違い）

`spi_shim.so` は `LD_PRELOAD` でアプリ内の `open()/ioctl()` を横取りする方式で、
アプリの起動コマンドに `LD_PRELOAD=...` を足す必要がありました。CUSE 版は
カーネルが spidev の ioctl を `/dev/fuse` 経由でこのプロセスに配送するため、
アプリ側は本番（RasPi5）と同じ`./sensor_demo`一発で済みます。差し替えの
責務をアプリから Gapless Agent Runtime runtime 側へ閉じ込めるのが狙いです。

## 対応 ioctl

| ioctl | 動作 |
|---|---|
| `SPI_IOC_RD/WR_MODE` | 受理（値を保持して読み返す） |
| `SPI_IOC_RD/WR_LSB_FIRST` | 受理 |
| `SPI_IOC_RD/WR_BITS_PER_WORD` | 受理 |
| `SPI_IOC_RD/WR_MAX_SPEED_HZ` | 受理 |
| `SPI_IOC_RD/WR_MODE32` | 受理 |
| `SPI_IOC_MESSAGE(N)` | MFRC-522 レジスタ模擬で応答 |

MFRC-522 の SPI は 2 バイト転送です。

```
tx[0]: アドレスバイト = (reg << 1) & 0x7E、MSB=1 READ / 0 WRITE
tx[1]: データ（書き込み時）/ 0x00（読み出し時、応答は rx[1]）
```

`VersionReg(0x37)` は `0x92`（MFRC-522 v2.0）を返します。REQA / ANTICOLL で
ATQA・UID を返し、UID は bridge から取得したカードのものを使います。

## ビルド

通常は選択済みのBuildEnvironmentでGARにbuildさせます。

```bash
gar sim runtime build
gar sim runtime deploy
```

componentを単独で調査するときだけ、その環境に合うcompilerを明示してMakefileを
利用します。simulation hostや実機は実行先であり、build先ではありません。

```bash
# aarch64 simulation host向けcross build
make -C targets/linux-device/runtime/spi-stub CC=aarch64-linux-gnu-gcc

# local host向け
make -C targets/linux-device/runtime/spi-stub CC=gcc
```

`libfuse3-dev`（`/usr/include/fuse3`）が必要です。GARは生成したruntime
artifactを`gar sim runtime deploy`で選択済みsimulation hostへ配置します。

## 起動

```bash
# /dev/fuse へのアクセスが必要
sudo ./cuse_spi -f --devname=spidev0.0
```

`-f`はforeground実行です。通常の常駐起動とdevice nodeのpermission設定は
`gar sim runtime start`が担当します。

## 動作確認の受け入れ基準

「`/dev/spidev0.0` が生えた」「ioctl が通った」だけでは done にしません。

1. `gar sim runtime start`で`cuse_spi`が常駐し、`/dev/spidev0.0`が見える
2. `sensor_demo`（LD_PRELOADなし）がVersionReg=0x92を読んで初期化に成功する
3. `gar sim io set --device rfid --uid 04:AB:CD:EF:01:23`の後にUIDが表示される
4. `gar sim io clear --device rfid`でカード無しの挙動に戻る
5. `gar sim runtime diag --json`がruntime全体を正常と判定する

ここまで確認できて初めて S4 完了です。
