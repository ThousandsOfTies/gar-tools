# Raspberry Pi 5 / Raspberry Pi OS Target

このTargetはRaspberry Pi OSを動かすRaspberry Pi 5実機を対象にします。
applicationはreal `/dev/gpiochip*`、`/dev/spidev*`、`/dev/video*`を直接使用します。
CUSE、gpio-sim、simulation Web Panelは実機へdeployしません。

## 標準フロー

`target.json`の`provisioning.ssh_scp`がRaspberry Pi OS/systemd recipeを選択します。

```bash
gar target prepare --workspace Local/Product  # 初回・recipe更新時
gar target build --workspace Local/Product
gar target deploy --workspace Local/Product
```

SSH accountは通常の鍵認証を使います。`prepare`でsudo passwordが必要な場合は
接続したvisible terminalへ入力します。recipeは冪等で、次を導入します。

- GAR reference application用のPython/GStreamer/V4L2 runtime package
- system service account `gar`
- 存在する`gpio`、`spi`、`video`、`i2c`groupへの`gar`追加
- root所有の`/usr/local/lib/gar/gar-target-install`
- root所有の共通systemd template `gar-app@.service`
- root管理の標準directory `/opt/gar/apps`と`/etc/gar`
- GAR限定installerだけを許可するsudoers rule

旧GAR試作版が作った`/etc/sudoers.d/90-gar-deploy`は`NOPASSWD: ALL`だったため、
recipeが削除して限定ruleへ移行します。このGAR所有file以外の管理者sudoers設定は
変更しません。

## Product artifact contract

通常の`gar target deploy`はSSH accountで一時directoryへ転送した後、限定installerで
次だけを更新できます。

- `/opt/gar/apps/<app>`
- 必要な場合の`/etc/gar/<app>.env`

applicationは実行可能な`/opt/gar/apps/<app>/run`を提供します。GARは対応する
`gar-app@<app>.service`をenableしてrestartします。`/etc/gar/<app>.env`は任意の
上書き設定であり、存在する場合だけ読み込みます。PnPや安全なdefaultを持つproductは
envなしで起動できます。

product artifactは独自のroot所有service unitを配布しません。boot統合、`gar`account、
device group、systemd hardeningはTarget/OS recipeに集約します。product固有の永続設定は
`/etc/gar`へ分離され、通常のapplication deployで上書きされません。

`provisioning/raspberry-pi-os-systemd/`がsystemd型Target recipeのreference templateです。
別distribution、別init system、read-only rootfsはGaplessAgentRuntimeへ条件分岐を
追加せず、それぞれのTarget recipe/backendとして実装します。
