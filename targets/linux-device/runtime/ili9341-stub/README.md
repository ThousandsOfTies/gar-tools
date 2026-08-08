# cuse_spi_ili9341 — CUSE SPI stub (ILI9341 320×240 sim, gar-stream-rx)

`gar-stream-rx`（Luckfox Lyra Plus 上のビデオモニター）の `ili9341.py` が使う
`/dev/spidevX.Y` を CUSE で userspace に生やし、未改変のアプリがそのまま
ILI9341 パネルへ描画できるようにするスタブです。`spi-stub/cuse_spi`
（MFRC-522 sim）と同じ ioctl プラミングを再利用し、デバイス固有の状態機械
だけを `ili9341_sim.c` に分離しています。

同じ `/dev/spidev0.0` という慣習的なノード名を使いますが、対象アプリ
シナリオが異なる（`spi-stub` は gar-adhoc-app の sensor_demo、
こちらは gar-stream-rx）ため、**同時に2つを起動する想定はありません**。
どちらか一方だけを、そのシナリオに合わせて起動してください。

## なぜ DC (data/command) の扱いが特別か

ILI9341 は `SPI_IOC_MESSAGE` だけでは「今送っているバイト列がコマンドか
ピクセルデータか」を判別できません。実機・`ili9341.py` はこれを別の GPIO
（DC ピン）で表現します（`DC=0` でコマンド、`DC=1` でデータ）。この GPIO は
SPI ioctl の外側にあるため、`cuse_spi_ili9341` は SPI 転送を受け取るたびに
web bridge（`GAR_HW_SIM_SOCK` または `GAR_RUNTIME_DIR/hw_sim.sock`）に
「DC ピンの現在値」を問い合わせ、それに応じてコマンド/データを振り分けます。

DCピンのgpio-sim上のline番号は`--dc-line=N`で指定します。通常のruntime
起動では、targetの`hardware/gpio.csv`にある`lcd_dc`のlineをlauncherと
web bridgeが共有するため、個別指定は不要です。

## 対応 ioctl

| ioctl | 動作 |
|---|---|
| `write(2)` | `spidev.SpiDev.writebytes()` の送信データを処理 |
| `SPI_IOC_RD/WR_MODE` | 受理（値を保持して読み返す） |
| `SPI_IOC_RD/WR_LSB_FIRST` | 受理 |
| `SPI_IOC_RD/WR_BITS_PER_WORD` | 受理 |
| `SPI_IOC_RD/WR_MAX_SPEED_HZ` | 受理 |
| `SPI_IOC_RD/WR_MODE32` | 受理 |
| `SPI_IOC_MESSAGE(N)` | DC 状態に応じてコマンド/ピクセルデータとして処理 |

## 追跡しているコマンド

`ili9341_sim.c` は以下だけを理解します（それ以外は受理して無視）。

| コマンド | 意味 |
|---|---|
| `0x2A` CASET | 列アドレス範囲 (x0,x1) |
| `0x2B` PASET | 行アドレス範囲 (y0,y1) |
| `0x2C` RAMWR | RGB565 ピクセルストリームを現在のウィンドウへ書き込む |
| `0x36` MADCTL | `MV`（行列入れ替え）ビットだけを見て 320×240 / 240×320 を切り替える |

`RAMWR` で書き込まれたフレームバッファは base64 化して web bridge へ
`{"event":"set","device":"ili9341","width":W,"height":H,"pixels":"..."}` として
送信します（`video_monitor.py` の 15fps 更新をそのまま流すとブラウザ側が
詰まるため、送信は最大 5 回/秒に間引いています）。Virtual Hardware Panel
はこれを 320×240 の `<canvas>` に描画します。

## ビルド

通常は選択済みのBuildEnvironmentでGARにbuild・配置させます。

```bash
gar sim runtime build
gar sim runtime deploy
```

componentを単独で調査するときだけ、その環境に合うcompilerを明示します。

```bash
# aarch64 simulation host向けcross build
make -C targets/linux-device/runtime/ili9341-stub CC=aarch64-linux-gnu-gcc

# local host向け
make -C targets/linux-device/runtime/ili9341-stub CC=gcc
```

`libfuse3-dev`（`/usr/include/fuse3`）が必要です。

## 起動

```bash
# /dev/fuse へのアクセスが必要
sudo ./cuse_spi_ili9341 -f --devname=spidev0.0 --dc-line=<lcd-dc-line>
```

`-f`はforeground実行です。通常の常駐起動、hardware CSVの反映、device nodeの
permission設定は`gar sim runtime start`が担当します。

## 動作確認の受け入れ基準

1. `gar sim runtime start`で`cuse_spi_ili9341`が常駐し、`/dev/spidev0.0`が見える
2. `video_monitor.py`（LD_PRELOAD なし）が初期化シーケンスを流せてエラーにならない
3. カラーバー分岐を表示させた状態で Virtual Hardware Panel の ILI9341 canvas に
   映像が表示される
4. Hardware PanelからKY-040を回転させても表示が壊れない
5. `gar sim runtime diag --json`がruntime全体を正常と判定する
