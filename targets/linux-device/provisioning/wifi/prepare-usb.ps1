param(
    [Parameter(Mandatory=$true)][Guid]$InterfaceGuid,
    [Parameter(Mandatory=$true)][string]$Address,
    [Parameter(Mandatory=$true)][string]$ResultFile
)
$ErrorActionPreference='Stop'
$result=@{ok=$false;error='usb_management_setup_failed'}
try {
    if(-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'administrator_required'}
    $parsed=[Net.IPAddress]::Parse($Address)
    if($parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork){throw 'invalid_address'}
    $adapter=@(Get-NetAdapter | Where-Object {[Guid]$_.InterfaceGuid -eq $InterfaceGuid})
    if($adapter.Count -ne 1 -or $adapter[0].InterfaceDescription -notmatch 'RNDIS|Remote NDIS' -or $adapter[0].Status -ne 'Up'){throw 'usb_adapter_not_ready'}
    $adapter=$adapter[0]
    $conflicts=@(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -eq $Address -and $_.InterfaceIndex -ne $adapter.ifIndex})
    foreach($conflict in $conflicts){if((Get-NetAdapter -InterfaceIndex $conflict.InterfaceIndex).Status -ne 'Disconnected'){throw 'address_in_use_by_connected_adapter'}}
    $snapshot=@{when=(Get-Date).ToString('o');target=@{name=$adapter.Name;guid=$adapter.InterfaceGuid;addresses=@(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength);dhcp=[string](Get-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4).Dhcp};conflicts=@($conflicts | Select-Object InterfaceIndex,IPAddress,PrefixLength)}
    $snapshot | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath ($ResultFile+'.before.json') -Encoding utf8
    foreach($conflict in $conflicts){Remove-NetIPAddress -InputObject $conflict -Confirm:$false}
    Set-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -Dhcp Disabled
    $present=@(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 | Where-Object {$_.IPAddress -eq $Address})
    if(-not $present){New-NetIPAddress -InterfaceIndex $adapter.ifIndex -IPAddress $Address -PrefixLength 24 | Out-Null}
    $result=@{ok=$true;interface=$adapter.Name;address=$Address;internetSharingChanged=$false}
}catch{
    $observed=@()
    if($adapter -and $adapter.ifIndex){$observed=@(Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object {$_.IPAddress -eq $Address -and $_.PrefixLength -eq 24})}
    if($observed -and (Get-NetIPInterface -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4).Dhcp -eq 'Disabled'){
        $result=@{ok=$true;interface=$adapter.Name;address=$Address;internetSharingChanged=$false;postconditionVerified=$true}
    }else{
        $result.error=if($_.Exception.Message -match '^[a-z_]+$'){$_.Exception.Message}else{'usb_management_setup_failed'}
    }
}finally{
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ResultFile -Encoding utf8
}
if(-not $result.ok){exit 1}
