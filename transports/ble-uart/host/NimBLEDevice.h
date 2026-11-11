#pragma once
// Host substitute for only the NimBLE 2.3.6 API surface used by BleUart.
// No application packets, session state or UI behavior belongs here.
#include <cstdint>
#include <string>
#include <map>
#include <memory>
#include <deque>
#include <algorithm>
constexpr uint16_t BLE_HS_CONN_HANDLE_NONE=65535;
constexpr int BLE_HS_IO_DISPLAY_YESNO=1;
namespace NIMBLE_PROPERTY { constexpr int NOTIFY=1,WRITE=2,WRITE_ENC=4,WRITE_AUTHEN=8; }
class NimBLEServer;class NimBLECharacteristic;
struct NimBLEConnInfo {
 uint16_t handle=1;bool encrypted=false,authenticated=false,bonded=false;
 uint16_t getConnHandle()const{return handle;}
 bool isEncrypted()const{return encrypted;}bool isAuthenticated()const{return authenticated;}bool isBonded()const{return bonded;}
};
class NimBLEServerCallbacks {public:virtual ~NimBLEServerCallbacks()=default;
 virtual void onConnect(NimBLEServer*,NimBLEConnInfo&){} virtual void onDisconnect(NimBLEServer*,NimBLEConnInfo&,int){}
 virtual void onMTUChange(uint16_t,NimBLEConnInfo&){} virtual void onConfirmPassKey(NimBLEConnInfo&,uint32_t){}
 virtual void onAuthenticationComplete(NimBLEConnInfo&){} };
class NimBLECharacteristicCallbacks {public:virtual ~NimBLECharacteristicCallbacks()=default;
 virtual void onSubscribe(NimBLECharacteristic*,NimBLEConnInfo&,uint16_t){} virtual void onWrite(NimBLECharacteristic*,NimBLEConnInfo&){} };
namespace gar::nimble_host {
inline NimBLEServer* server=nullptr;inline NimBLEConnInfo peer;
inline bool linked=false,subscribed=false,advertising=false,securityRequested=false,allowSecurity=true,notifyFailure=false;
inline unsigned securityRequests=0,rejectedWrites=0;inline uint16_t mtu=23;
inline std::deque<std::string> notifications;
}
class NimBLECharacteristic {
 public:std::string uuid,value;int properties;NimBLECharacteristicCallbacks* callbacks=nullptr;
 NimBLECharacteristic(const char* id,int flags):uuid(id),properties(flags){}
 void setCallbacks(NimBLECharacteristicCallbacks* c){callbacks=c;}
 std::string getValue()const{return value;}
 bool notify(const uint8_t* bytes,size_t n,uint16_t handle){using namespace gar::nimble_host;
 if(!linked||!subscribed||!peer.encrypted||!peer.authenticated||handle!=peer.handle||notifyFailure||n>mtu-3)return false;
 notifications.emplace_back(reinterpret_cast<const char*>(bytes),n);return true;}
};
class NimBLEService {public:std::map<std::string,std::unique_ptr<NimBLECharacteristic>> characteristics;
 NimBLECharacteristic* createCharacteristic(const char* id,int flags){auto c=std::make_unique<NimBLECharacteristic>(id,flags);auto p=c.get();characteristics[id]=std::move(c);return p;}void start(){} };
class NimBLEServer {public:NimBLEServerCallbacks* callbacks=nullptr;NimBLEService service;
 void setCallbacks(NimBLEServerCallbacks* c,bool){callbacks=c;}NimBLEService* createService(const char*){return &service;}
 NimBLEConnInfo getPeerInfoByHandle(uint16_t){return gar::nimble_host::peer;}
 void disconnect(uint16_t handle){using namespace gar::nimble_host;if(!linked||handle!=peer.handle)return;linked=false;subscribed=false;callbacks->onDisconnect(this,peer,0);}
};
class NimBLEAdvertisementData {public:void setFlags(int){}void addServiceUUID(const char*){}void setName(const char*){} };
class NimBLEAdvertising {public:void setAdvertisementData(NimBLEAdvertisementData&){}void setScanResponseData(NimBLEAdvertisementData&){}void enableScanResponse(bool){}bool start(){gar::nimble_host::advertising=true;return true;} };
class NimBLEDevice {public:
 static void init(const char*){} static void setSecurityAuth(bool,bool,bool){}static void setSecurityIOCap(int){}static void setMTU(int){}
 static NimBLEServer* createServer(){return gar::nimble_host::server=new NimBLEServer;}
 static NimBLEAdvertising* getAdvertising(){static NimBLEAdvertising a;return &a;}
 static void startAdvertising(){getAdvertising()->start();}
 static bool startSecurity(uint16_t handle){using namespace gar::nimble_host;if(!linked||handle!=peer.handle)return false;securityRequested=true;++securityRequests;return true;}
 static void injectConfirmPasskey(NimBLEConnInfo&,bool accepted){using namespace gar::nimble_host;
 if(!linked||!securityRequested)return;peer.encrypted=peer.authenticated=accepted;peer.bonded=accepted;server->callbacks->onAuthenticationComplete(peer);}
};
namespace gar::nimble_host {
inline NimBLECharacteristic* characteristic(bool tx){for(auto& item:server->service.characteristics)if(bool(item.second->properties&NIMBLE_PROPERTY::NOTIFY)==tx)return item.second.get();return nullptr;}
inline void connect(bool bonded=true){if(linked||!advertising)return;peer={1,false,false,bonded};linked=true;subscribed=false;securityRequested=false;notifications.clear();server->callbacks->onConnect(server,peer);}
inline void authenticate(bool success){if(!linked||!securityRequested)return;peer.encrypted=peer.authenticated=peer.bonded=success;server->callbacks->onAuthenticationComplete(peer);}
inline void subscribe(bool enabled){if(!linked)return;subscribed=enabled;auto tx=characteristic(true);tx->callbacks->onSubscribe(tx,peer,enabled?1:0);}
inline void progress(){if(linked&&securityRequested&&allowSecurity&&!peer.encrypted)authenticate(true);}
inline bool write(const char* bytes,size_t n){if(!linked||!peer.encrypted||!peer.authenticated||n>mtu-3){++rejectedWrites;return false;}auto rx=characteristic(false);rx->value.assign(bytes,n);rx->callbacks->onWrite(rx,peer);return true;}
inline void disconnect(){if(linked)server->disconnect(peer.handle);notifications.clear();}
inline void reset(){disconnect();securityRequests=rejectedWrites=0;securityRequested=false;allowSecurity=true;notifyFailure=false;}
}
