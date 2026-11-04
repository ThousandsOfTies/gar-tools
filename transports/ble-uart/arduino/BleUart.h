#pragma once
#include <NimBLEDevice.h>
#include <freertos/stream_buffer.h>
#include <atomic>
#include <algorithm>
#include <deque>
#include <functional>
#include <string>

namespace gar {
// Generic single-peer encrypted byte pipe. No JSON, UI, session or board facts.
class BleUart {
 public:
  struct Options {const char *name,*service,*rx,*tx;};
  struct Hooks {
    std::function<void(const char*,size_t)> receive;
    std::function<void()> reset;
    std::function<void(uint32_t)> confirm;
    std::function<void(bool)> authenticated;
  };
  void begin(Options options,Hooks hooks) {
    hooks_=hooks;rxBuffer_=xStreamBufferCreate(16384,1);if(!rxBuffer_)return;
    NimBLEDevice::init(options.name);
    NimBLEDevice::setSecurityAuth(true,true,true);
    NimBLEDevice::setSecurityIOCap(BLE_HS_IO_DISPLAY_YESNO);
    NimBLEDevice::setMTU(247);
    server_=NimBLEDevice::createServer();server_->setCallbacks(&serverCallbacks_,false);
    auto service=server_->createService(options.service);
    tx_=service->createCharacteristic(options.tx,NIMBLE_PROPERTY::NOTIFY);
    tx_->setCallbacks(&characteristicCallbacks_);
    auto rx=service->createCharacteristic(options.rx,NIMBLE_PROPERTY::WRITE|NIMBLE_PROPERTY::WRITE_ENC|NIMBLE_PROPERTY::WRITE_AUTHEN);
    rx->setCallbacks(&characteristicCallbacks_);
    service->start();auto advertising=NimBLEDevice::getAdvertising();
    // A 128-bit UUID plus the device name cannot fit in one legacy 31-byte
    // advertisement. Keep discovery's UUID in the primary packet.
    NimBLEAdvertisementData advertisement,response;
    advertisement.setFlags(0x06);advertisement.addServiceUUID(options.service);
    response.setName(options.name);
    advertising->setAdvertisementData(advertisement);advertising->setScanResponseData(response);
    advertising->enableScanResponse(true);
    ready_=advertising->start();
  }
  bool ready() const{return ready_;}
  bool connected() const{return secure_ && subscribed_;}
  void confirm(bool accepted) {
    const auto handle=confirmHandle_.exchange(BLE_HS_CONN_HANDLE_NONE);
    if(handle!=BLE_HS_CONN_HANDLE_NONE && server_){auto info=server_->getPeerInfoByHandle(handle);NimBLEDevice::injectConfirmPasskey(info,accepted);}
  }
  void send(const std::string& bytes) {
    if(!connected())return;
    if(queued_+bytes.size()>65536){disconnect();return;}
    queued_+=bytes.size();outgoing_.push_back(bytes);
  }
  void poll() {
    if(!ready_)return;
    if(epoch_.exchange(false)) {
      char buffer[256];while(xStreamBufferReceive(rxBuffer_,buffer,sizeof(buffer),0)){}
      outgoing_.clear();queued_=0;offset_=0;hooks_.reset();
    }
    if(overflow_.exchange(false)){disconnect();return;}
    const auto number=number_.exchange(UINT32_MAX);if(number!=UINT32_MAX)hooks_.confirm(number);
    const int auth=auth_.exchange(0);if(auth)hooks_.authenticated(auth>0);
    if(!connected())return;
    char buffer[256];
    for(int i=0;i<4;++i){auto size=xStreamBufferReceive(rxBuffer_,buffer,sizeof(buffer),0);if(!size)break;hooks_.receive(buffer,size);}
    if(!outgoing_.empty()) {
      auto& packet=outgoing_.front();const auto count=std::min(packet.size()-offset_,size_t(payload_.load()));
      if(!tx_->notify(reinterpret_cast<const uint8_t*>(packet.data()+offset_),count,handle_)){disconnect();return;}
      offset_+=count;queued_-=count;
      if(offset_==packet.size()){outgoing_.pop_front();offset_=0;}
    }
  }
 private:
  Hooks hooks_;NimBLEServer* server_=nullptr;NimBLECharacteristic* tx_=nullptr;
  StreamBufferHandle_t rxBuffer_=nullptr;
  std::atomic<bool> secure_{false},subscribed_{false},epoch_{false},overflow_{false};
  std::atomic<uint16_t> handle_{BLE_HS_CONN_HANDLE_NONE},confirmHandle_{BLE_HS_CONN_HANDLE_NONE},payload_{20};
  std::atomic<uint32_t> number_{UINT32_MAX};std::atomic<int> auth_{0};
  bool ready_=false;std::deque<std::string> outgoing_;size_t queued_=0,offset_=0;
  void disconnect(){secure_=false;subscribed_=false;epoch_=true;if(server_)server_->disconnect(handle_);}
  class ServerCallbacks:public NimBLEServerCallbacks {
    BleUart& pipe_;
   public:
    explicit ServerCallbacks(BleUart& pipe):pipe_(pipe){}
    void onConnect(NimBLEServer* server,NimBLEConnInfo& info) override {
      if(pipe_.handle_!=BLE_HS_CONN_HANDLE_NONE){server->disconnect(info.getConnHandle());return;}
      pipe_.handle_=info.getConnHandle();pipe_.payload_=20;pipe_.epoch_=true;
      // Bonding alone does not encrypt a new connection. Request link security.
      NimBLEDevice::startSecurity(info.getConnHandle());
    }
    void onDisconnect(NimBLEServer*,NimBLEConnInfo& info,int) override {
      if(pipe_.handle_!=info.getConnHandle())return;
      pipe_.secure_=false;pipe_.subscribed_=false;pipe_.handle_=BLE_HS_CONN_HANDLE_NONE;
      pipe_.confirmHandle_=BLE_HS_CONN_HANDLE_NONE;pipe_.number_=UINT32_MAX;
      pipe_.epoch_=true;NimBLEDevice::startAdvertising();
    }
    void onMTUChange(uint16_t mtu,NimBLEConnInfo&) override {pipe_.payload_=std::min<uint16_t>(244,mtu>3?mtu-3:20);}
    void onConfirmPassKey(NimBLEConnInfo& info,uint32_t number) override {
      if(info.getConnHandle()!=pipe_.handle_)return;
      pipe_.confirmHandle_=info.getConnHandle();pipe_.number_=number;
    }
    void onAuthenticationComplete(NimBLEConnInfo& info) override {
      if(info.getConnHandle()!=pipe_.handle_)return;
      const bool ok=info.isEncrypted()&&info.isAuthenticated()&&info.isBonded();
      pipe_.secure_=ok;pipe_.auth_=ok?1:-1;if(!ok)pipe_.disconnect();
    }
  } serverCallbacks_{*this};
  class CharacteristicCallbacks:public NimBLECharacteristicCallbacks {
    BleUart& pipe_;
   public:
    explicit CharacteristicCallbacks(BleUart& pipe):pipe_(pipe){}
    void onSubscribe(NimBLECharacteristic*,NimBLEConnInfo& info,uint16_t value) override {
      if(info.getConnHandle()==pipe_.handle_)pipe_.subscribed_=(value&1)!=0;
    }
    void onWrite(NimBLECharacteristic* characteristic,NimBLEConnInfo& info) override {
      if(info.getConnHandle()!=pipe_.handle_ || !info.isEncrypted() || !info.isAuthenticated())return;
      const auto bytes=characteristic->getValue();
      if(xStreamBufferSend(pipe_.rxBuffer_,bytes.data(),bytes.size(),0)!=bytes.size())pipe_.overflow_=true;
    }
  } characteristicCallbacks_{*this};
};
}
