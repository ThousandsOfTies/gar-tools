"""GC9A01 transport contract; does not require a running CUSE driver."""
import asyncio
import base64
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bridge


class Gc9a01Test(unittest.TestCase):
    def test_existing_ili9341_default_dimensions_stay_320_by_240(self):
        state=copy.deepcopy(bridge.state)
        pixels=base64.b64encode(bytes(320*240*2)).decode()
        loop=asyncio.new_event_loop()
        try:
            with patch.object(bridge,'state',state), patch.object(bridge,'HARDWARE_CONFIG',SimpleNamespace(device_drivers={'ili9341'})), patch.object(bridge,'_schedule_broadcast') as broadcast:
                bridge.handle_stub_message(json.dumps({'event':'set','device':'ili9341','pixels':pixels}),loop)
                self.assertEqual(state['spi']['ili9341'],{'pixels':pixels,'width':320,'height':240})
                self.assertEqual(broadcast.call_args.args[0]['type'],'ili9341')
        finally:
            loop.close()

    def test_gc9a01_frame_dimensions_payload_and_device_isolation(self):
        state=copy.deepcopy(bridge.state)
        loop=asyncio.new_event_loop()
        frame=base64.b64encode(bytes([0xf8,0x00])*240*240).decode()
        message={'event':'set','device':'gc9a01','width':240,'height':240,'pixels':frame}
        try:
            with patch.object(bridge,'state',state), patch.object(bridge,'HARDWARE_CONFIG',SimpleNamespace(device_drivers={'gc9a01'})), patch.object(bridge,'_schedule_broadcast') as broadcast:
                old_ili=copy.deepcopy(state['spi']['ili9341'])
                bridge.handle_stub_message(json.dumps(message),loop)
                self.assertEqual(state['spi']['gc9a01']['pixels'],frame)
                self.assertEqual(state['spi']['ili9341'],old_ili)
                self.assertEqual(broadcast.call_args.args[0]['type'],'gc9a01')
                for bad in [dict(message,width=320),dict(message,pixels='AAAA'),dict(message,device='ili9341')]:
                    before=copy.deepcopy(state)
                    with self.assertLogs(bridge.LOGGER,level='WARNING'):
                        bridge.handle_stub_message(json.dumps(bad),loop)
                    self.assertEqual(state,before)
                self.assertEqual(broadcast.call_count,1)
        finally:
            loop.close()

if __name__=='__main__':unittest.main()
