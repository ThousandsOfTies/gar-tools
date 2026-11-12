"""Independent BleUart SDK-boundary test, including a missing-security mutation.
Run with em++ and node on PATH (activate Emscripten first).
"""
from pathlib import Path
import subprocess, tempfile
ROOT=Path(__file__).resolve().parent
SOURCE=r'''#include "BleUart.h"
int main(){
 gar::BleUart pipe;int received=0;
 pipe.begin({"test","service","rx","tx"},{[&](const char*,size_t){++received;},[]{},[](uint32_t){},[](bool){}});
 using namespace gar::nimble_host;
 connect();pipe.poll();
 if(securityRequests!=1)return 10;
 subscribe(true);write("x",1);pipe.poll();if(received||pipe.connected())return 11;
 progress();pipe.poll();write("x",1);pipe.poll();if(received!=1||!pipe.connected())return 12;
 pipe.send("abc");pipe.poll();if(notifications.empty()||notifications.front()!="abc")return 13;
 disconnect();pipe.poll();connect();pipe.poll();if(securityRequests!=2||pipe.connected())return 14;
 authenticate(false);pipe.poll();if(linked)return 15;
 return 0;
}
'''
def main():
 with tempfile.TemporaryDirectory() as folder:
  folder=Path(folder);source=folder/'test.cpp';source.write_text(SOURCE)
  original=(ROOT.parent/'arduino/BleUart.h').read_text()
  for mutation in (False,True):
   header=original.replace('NimBLEDevice::startSecurity(info.getConnHandle());','') if mutation else original
   (folder/'BleUart.h').write_text(header)
   output=folder/('mutated.js' if mutation else 'normal.js')
   subprocess.run(['em++','-std=c++17',str(source),'-I'+str(folder),'-I'+str(ROOT),'-sSINGLE_FILE=1','-o',str(output)],check=True)
   result=subprocess.run(['node',str(output)])
   expected=10 if mutation else 0
   if result.returncode!=expected:raise RuntimeError(f'Expected {expected}, got {result.returncode}')
   print('PASS missing-startSecurity mutation rejected' if mutation else 'PASS independent shared BleUart control path')
if __name__=='__main__':main()
