# Raspberry Pi 5 / Raspberry Pi OS Target

このTargetはRaspberry Pi OSを動かすRaspberry Pi 5実機を対象にします。
applicationはreal `/dev/gpiochip*`、`/dev/spidev*`、`/dev/video*`を直接使用します。
CUSE、gpio-sim、simulation Web Panelは実機へdeployしません。

## Hardware boundary

`hardware/capabilities.json` is the Target Pack contract for verified GPIO,
SPI, USB video, and network resources. It records board capabilities only;
application requirements and physical wiring belong to the product and its
versioned Target binding. The empty CSV templates under `hardware/` are copied
into a product workspace by `gar hw init` before an assignment is made.

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
- root所有の`/usr/local/lib/gar/gar-target-lifecycle`
- root所有の共通systemd template `gar-app@.service`
- root管理の標準directory `/opt/gar/apps`、`/etc/gar`、`/var/lib/gar-target/state`
- 論理Target ID `/etc/gar/target-id`
- GAR限定installerだけを許可するsudoers rule

旧GAR試作版が作った`/etc/sudoers.d/90-gar-deploy`は`NOPASSWD: ALL`だったため、
recipeが削除して限定ruleへ移行します。このGAR所有file以外の管理者sudoers設定は
変更しません。

## Product artifact contract

通常の`gar target deploy`はSSH accountで一時directoryへ転送した後、限定installerで
次だけを更新できます。

- `/opt/gar/apps/<app>`
- 必要な場合の`/etc/gar/<app>.env`
- system が解決して一時適用する`/etc/gar/system/<app>.env`（root所有・0644）

applicationは実行可能な`/opt/gar/apps/<app>/run`を提供します。GARは対応する
`gar-app@<app>.service`をenableしてrestartします。`/etc/gar/<app>.env`は任意の
上書き設定であり、存在する場合だけ読み込みます。PnPや安全なdefaultを持つproductは
envなしで起動できます。
`/etc/gar/system/<app>.env`はpersistent設定の後に読み込まれ、同じkeyはruntime値が
優先されます。通常のapplication deployは両方のenvを変更しません。

product artifactは独自のroot所有service unitを配布しません。boot統合、`gar`account、
device group、systemd hardeningはTarget/OS recipeに集約します。product固有の永続設定は
`/etc/gar`へ分離され、通常のapplication deployで上書きされません。

## Lifecycle contract

manifestの`gar-app-lifecycle-v1` capabilityは、systemdの差をTarget recipe内へ閉じ込め、
次の共通操作を提供します。

```text
gar-target-lifecycle status APP
gar-target-lifecycle log APP [--lines N]
gar-target-lifecycle health APP
gar-target-lifecycle reload APP --build-id BUILD_ID
gar-target-lifecycle running-build-id APP
```

通常userのSSH接続ではGARが限定sudoers ruleを通して`sudo -n`でhelperを呼びます。
`reload`はservice restartとhealth確認が成功し、deployed
`/opt/gar/apps/APP/.gar-artifact.json`のschema v2 build IDと一致した場合だけ、
health確認済みIDを記録します。`running-build-id`はserviceがhealthyで、記録IDと
deployed markerが一致する場合だけIDを返します。artifactに実行可能な`health`が
あれば、serviceと同じ`gar` userで追加probeとして実行します。
deploy時は限定installerの`register-app`がunitのenableだけを行い、processの
restartと収束判定は続くlifecycle `reload`へ一元化します。従来の直接利用向け
`enable-app` actionはregister後にrestartする互換入口として残します。

`provisioning/raspberry-pi-os-systemd/`がsystemd型Target recipeのreference templateです。
別distribution、別init system、read-only rootfsはGaplessAgentRuntimeへ条件分岐を
追加せず、それぞれのTarget recipe/backendとして実装します。
