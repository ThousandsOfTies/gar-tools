# cuse_spi_ili9341 — CUSE SPI stub (ILI9341 320×240 sim, gar-stream-rx)

`gar-stream-rx`（Luckfox Lyra Plus 上のビデオモニター）の `ili9341.py` が使う
`/dev/spidevX.Y` を CUSE で userspace に生やし、未改変のアプリがそのまま
ILI9341 パネルへ描画できるようにするスタブです。`spi-stub/cuse_spi`
（MFRC-522 sim）と同じ ioctl プラミングを再利用し、デバイス固有の状態機械
だけを `ili9341_sim.c` に分離しています。

同じ `/dev/spidev0.0` という慣習的なノード名を使いますが、対象アプリ
シナリオが異なる（`spi-stub` は embedded-poc-app の sensor_demo、
こちらは gar-stream-rx）ため、**同時に2つを起動する想定はありません**。
どちらか一方だけを、そのシナリオに合わせて起動してください。

## なぜ DC (data/command) の扱いが特別か

ILI9341 は `SPI_IOC_MESSAGE` だけでは「今送っているバイト列がコマンドか
ピクセルデータか」を判別できません。実機・`ili9341.py` はこれを別の GPIO
（DC ピン）で表現します（`DC=0` でコマンド、`DC=1` でデータ）。この GPIO は
SPI ioctl の外側にあるため、`cuse_spi_ili9341` は SPI 転送を受け取るたびに
web bridge（`GAR_HW_SIM_SOCK` または `GAR_RUNTIME_DIR/hw_sim.sock`）に
「DC ピンの現在値」を問い合わせ、それに応じてコマンド/データを振り分けます。

DC ピンの gpio-sim 上のライン番号は `--dc-line=N`（既定 16）で指定し、
web bridge 側の `ILI9341_DC_LINE`（`web-bridge/bridge.py`）と一致させて
ください。

## 対応 ioctl

| ioctl | 動作 |
|---|---|
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

**ビルドは Codespaces で行う**（鉄則）。EC2 上では `make` しない。

```bash
# Codespaces: aarch64 cross-build（EC2 Graviton と同じ ABI）
make CC=aarch64-linux-gnu-gcc

# x86_64（構文確認用）
make
```

`libfuse3-dev`（`/usr/include/fuse3`）が必要です。

## 起動

```bash
# /dev/fuse へのアクセスが必要
sudo ./cuse_spi_ili9341 -f --devname=spidev0.0 --dc-line=16
```

起動後は `chmod 666 /dev/spidev0.0` でアプリから読めるようにします。
`-f` は foreground 実行。バックグラウンド常駐は `gar sim start` に組み込みます
（`cuse_spi`/`cuse_i2c` と同様）。

## 動作確認の受け入れ基準

1. `gar sim start` で `cuse_spi_ili9341` が常駐し `/dev/spidev0.0` が見える
2. `video_monitor.py`（LD_PRELOAD なし）が初期化シーケンスを流せてエラーにならない
3. カラーバー分岐を表示させた状態で Virtual Hardware Panel の ILI9341 canvas に
   映像が表示される
4. `gar sim io` 側から回転を送っても（`ky040` 側の変更）表示は壊れない
