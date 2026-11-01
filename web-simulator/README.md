# Reusable GAR simulator parts

Appやtargetに依存しない表示・入力・通信部品を集めたライブラリです。
Productはこれらをimportし、Appの状態・メッセージ・配線・校正・動作シナリオを接続します。
画面一式をProductごとにコピーする必要はありません。npmやCDNは不要です。

設計・変更の前に[設計方針・NG例・完成条件](DESIGN_PRINCIPLES.md)を読んでください。
「生の部品感」を残し、見た目から別のAppでの使い道を思いつけることも品質の条件です。
Product固有のデザインで、共通部品の姿や基本操作を覆い隠さないようにします。

## 試す

gar-toolsのrootで実行します。

```powershell
python web-simulator/serve.py
# http://127.0.0.1:8765
python web-simulator/serve.py --panel web-simulator/examples/pwm-parts --port 8766
python web-simulator/serve.py --panel web-simulator/examples/input-parts --port 8767
python web-simulator/serve.py --panel /path/to/product/panel
python web-simulator/serve.py --panel /path/to/product/panel --export /path/to/empty-output
```

標準サンプルは同じ部品で320×180のセンサー画面と128×64の状態表示を構成します。
PWMサンプルは独立した2つのPCA9685・サーボを並べ、Product固有の動作を使いません。
入力サンプルは設定の異なるノブとゲームパッドを2個ずつ並べます。回る指標を見ながら、
ボタン・矢印キー・フォーカス中のホイールで回転を入力できます。
`make web-simulator`も共通サンプルを開きます。

## 部品を選ぶ

| 部品 | API・用途 |
| --- | --- |
| `display.mjs` / `<gar-display>` | `width`, `height`, `powered`, `brightness`, `label`。`displayContext`に描画、または`writeFrame(bytes, {littleEndian})`でRGB565を表示。`gar-touch`に画素座標とstart/move/end/cancelを通知。 |
| `framebuffer.mjs` | `decodeRgb565(bytes, {width, height, littleEndian})`。DOMなしで画素変換。旧boolean引数は240×240として対応。 |
| `lvgl-surface.mjs` / `LvglSurface` | WASMの解像度に合わせて描画と入力を接続。App接続は交換可能なadapter。 |
| `controls.mjs` / `<gar-sim-controls>` | 配列schemaからrange/checkbox/select/actionを生成。`values`と`gar-control`で接続。 |
| `event-log.mjs` / `<gar-event-log>` | `append(text)`、`clear()`、件数上限付きのログ。 |
| `connection-status.mjs` / `<gar-connection-status>` | `.source`に`connection`イベントを持つ接続Adapterを渡して状態を表示。通信は行わない。 |
| `rotary.mjs` / `<gar-rotary>` | 回転・押下を`gar-rotary-input`で通知し、`.value`でカウンタ表示を更新。通信は行わない。 |
| `json-transport.mjs` / `JsonTransport` | `{url}`を注入し、`connect()`、`send(message)`、`close()`でJSON通信。`message`と`connection`を通知し、Productのメッセージ解釈は行わない。 |
| `camera-input.mjs` / `<gar-camera-input>` | カメラ選択、映像プレビュー、JPEG WebSocket送信。`endpoint`で送信先を注入。 |
| `pca9685.js`, `sg90.js` | 任意の接続先・アドレス・校正を渡すPWM/サーボ表示。内部DOMとCSSはShadow DOMに閉じます。 |
| `gamepad.js` | ゲームパッド入力を通知。ロボットの動作への割当はProduct側。 |
| `telemetry-transport.mjs` | ローカルデモと読み取り専用WebSocket telemetry。初期状態と受信データの解釈を注入。 |

## 新しいAppのシミュレータを作るとき

最初に既存の部品を確認し、必要なタグと公開APIを決めます。部品の見た目・操作は
`web-simulator/components/`に、BridgeのJSON・Appの状態・操作の割当はProductの
`panel/studio.js`に置きます。`panel/index.html`はタグを並べて物理的な接続や
画面固有のラベルを指定し、配置・色・大きさはPanelのCSSで指定します。

新しい部品は、元のApp名やLinuxのデバイスパスを知らずに使えるAPIにします。
通信が必要な部品は接続先またはtransportを外から渡し、その通信方式が部品の契約に
含まれることを明記します。Productのメッセージ形式を部品の内部で解釈しません。

完成の確認は、元のProductとは無関係な小さなページに同じ部品を設定違いで2個置き、
それぞれの状態とイベントが独立していること、Product側の接続Adapterを外しても
部品を読み込めること、実際のProduct Panelでも入力・表示・配布が動くことです。
`studio.js`のような接続コードまで部品へ押し込まないでください。Appにしか意味が
ない画面や動作はProduct側に残します。

[操作パネル・ログのAPIと最小例](README-parts.md)、
[PWM・サーボ・ゲームパッドのAPIと接続例](SERVO_COMPONENTS.md)を参照してください。
T-Watchの筐体はhardware固有なので`targets/esp32/web-simulator/components/twatch-2020.mjs`に残します。

最小の表示部品:

```html
<gar-display id="screen" width="128" height="64" label="Status"></gar-display>
<script type="module">
  import './gar-components/display.mjs';
  const screen = document.querySelector('#screen');
  screen.displayContext.fillText('Ready', 10, 30);
  screen.addEventListener('gar-touch', ({detail}) => console.log(detail));
</script>
```

共通serverは`/gar-components/`からこれらを配信・静的exportします。
Productの`components/`は引き続き利用できます。古いT-Watchの3つのmodule pathのみ
`/components/`にも互換aliasを提供します。個々の部品にglobalなProduct singletonを埋め込まず、
複数インスタンスを別々の状態・接続先へ接続してください。Product HTMLには部品タグと
接続属性だけを書き、内部の`.servo-card`などを再実装・参照しません。

## LVGL 7を別のAppで使う

```powershell
python web-simulator/build_lvgl.py --lvgl /path/to/lvgl --app /path/to/app --entry /path/to/app/main.c --config /path/to/lv_conf.h --app-api minimal --width 320 --height 180 --output /path/to/panel/runtime --cache /path/to/object-cache
```

EmscriptenとLVGL 7のソースが必要です。`--app-api minimal`ではAppに
`void gar_app_init(void)`だけを実装し、通常のLVGL APIで画面を作れます。
LilyGOやArduinoJsonは必須ではありません。追加includeは`--include`、ソースは`--source`で指定します。
既存T-Watchの`--library`・`--json-library`・既定のlegacy ABIも使用できます。

```js
import { LvglSurface } from './gar-components/lvgl-surface.mjs';
import createUi from './runtime/lvgl-ui.mjs';
const ui = new LvglSurface(await createUi(), document.querySelector('canvas'));
// Dispose on teardown:
window.addEventListener('pagehide', () => ui.destroy());
```

独自App APIがある場合は第3引数の`{adapter}`に必要なhookだけを渡します。
`init`, `refresh`（`{label,nodes}`を返す）, `takeAction`, `receive`, `reset`,
`hardware`, `sideButton`, `scroll`を任意実装できます。`adapter: null`は画素・ポインタだけの接続です。
`nodes`は`id,label,x,y,width,height`を持ち、アクセシビリティ用のボタン位置は実際のLVGL座標を使います。
`[data-lvgl-controls]`を付けた要素をcanvasと同じ領域に重ねると、そのボタンを生成します。
旧`gar_app_hardware`などのVibe互換ABIは`createLegacyLvglAppAdapter`に分離されています。

## 現在の利用先

- GarVibeRemote-TWatch2020: 共通LVGL、シナリオ選択・ハードウェア操作・ログ。Vibe認証とpayloadはProductに保持。
- GarServoPet / GarServoPet-Lyra / GarServoPet-IMX91S: 共通PWM・サーボ・ゲームパッド・telemetry。配線・校正・動作割当はProductに保持。
- Linux Web bridge: `/gar-components/`を同じlibraryから配信。VM配布とGarStreamRx runtime artifactにも同梱。

開発中の変更は各Productの`sources/gar-tools`作業ツリーにも反映しています。
配布時はgar-toolsを先にcommit/pushしてからProductのsubmodule参照を更新します。

## 確認

```powershell
python -m unittest discover -s tests -p test_web_simulator.py -v
python -m unittest discover -s targets/esp32/web-simulator/tests -p 'test_*.py' -v
node --test targets/esp32/web-simulator/tests/*.test.mjs
node --test web-simulator/tests/*.test.mjs
python web-simulator/serve.py --panel web-simulator/tests/browser --port 8768
python web-simulator/serve.py --panel web-simulator/tests/display-browser --port 8769
python web-simulator/serve.py --panel web-simulator/tests/servo-browser --port 8770
python web-simulator/serve.py --panel web-simulator/tests/input-browser --port 8771
```

ブラウザ検証は各URLにPASSを表示します。CPU、無線、電気的挙動を再現する層ではなく、
入出力部品とAppの表示・操作を確認するための部品です。
