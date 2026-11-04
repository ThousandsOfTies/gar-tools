"""Encrypted GATT byte pipe over stdio. No application packets or credentials."""
import argparse
import asyncio
import base64
import json
import sys
import threading

def emit(value):
    print(json.dumps(value), flush=True)

async def write_chunks(client, characteristic, data):
    # ATT Write Request payload, serialized and acknowledged by the peer stack.
    size=max(1,min(244,client.mtu_size-3))
    for offset in range(0,len(data),size):
        await asyncio.wait_for(client.write_gatt_char(characteristic,data[offset:offset+size],response=True),10)

async def pipe(args):
    from bleak import BleakClient, BleakScanner
    if args.scan:
        devices=await BleakScanner.discover(timeout=8,return_adv=True)
        for device,advert in devices.values():
            if args.service.lower() in [s.lower() for s in advert.service_uuids]:
                emit({'event':'device','address':device.address,'name':advert.local_name})
        return
    if not args.address:raise ValueError('Explicit device address required')
    closed=asyncio.Event()
    device=await BleakScanner.find_device_by_address(args.address,timeout=15)
    if device is None:raise ValueError('Device unavailable')
    # Rediscover GATT handles after firmware updates; Windows may retain stale handles.
    async with BleakClient(device,pair=True,timeout=90,winrt={"use_cached_services":False},disconnected_callback=lambda _:closed.set()) as client:
        service=client.services.get_service(args.service)
        if service is None:raise ValueError('Wrong service')
        rx=service.get_characteristic(args.rx);tx=service.get_characteristic(args.tx)
        if rx is None or tx is None or 'write' not in rx.properties or 'notify' not in tx.properties:
            raise ValueError('Wrong characteristics')
        def received(_,data):emit({'event':'data','data':base64.b64encode(data).decode('ascii')})
        await client.start_notify(tx,received)
        emit({'event':'open'})
        loop=asyncio.get_running_loop()
        commands=asyncio.Queue(maxsize=1)
        def read_stdin():
            try:
                while True:
                    line=sys.stdin.buffer.readline(100000)
                    asyncio.run_coroutine_threadsafe(commands.put(line),loop).result()
                    if not line:return
            except Exception:
                return
        # A disconnected GATT link must not wait for a blocking Windows stdin
        # read when asyncio.run shuts down its default executor.
        threading.Thread(target=read_stdin,daemon=True).start()
        while not closed.is_set():
            read=asyncio.create_task(commands.get())
            disconnected=asyncio.create_task(closed.wait())
            done,_=await asyncio.wait([read,disconnected],return_when=asyncio.FIRST_COMPLETED)
            if disconnected in done:
                read.cancel();break
            disconnected.cancel();line=read.result()
            if not line:break
            command=json.loads(line)
            if command.get('type')=='close':break
            if command.get('type')!='write':raise ValueError('Invalid pipe command')
            data=base64.b64decode(command['data'],validate=True)
            if not 0<len(data)<=65537:raise ValueError('Invalid byte length')
            await write_chunks(client,rx,data)
            emit({'event':'written','id':command['id']})
        if client.is_connected:await client.stop_notify(tx)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address');parser.add_argument('--scan',action='store_true')
    for name in ('service','rx','tx'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    try:asyncio.run(pipe(args))
    except KeyboardInterrupt:return 130
    except Exception:
        emit({'event':'error','message':'GATT connection or transfer failed'});return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
