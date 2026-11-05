#pragma once
#include <deque>
#include <cstdint>
struct GarStream { size_t capacity; std::deque<uint8_t> bytes; };
using StreamBufferHandle_t=GarStream*;
inline StreamBufferHandle_t xStreamBufferCreate(size_t capacity,int){return new GarStream{capacity,{}};}
inline size_t xStreamBufferSend(StreamBufferHandle_t s,const void* data,size_t n,int){auto p=static_cast<const uint8_t*>(data);size_t i=0;while(i<n&&s->bytes.size()<s->capacity)s->bytes.push_back(p[i++]);return i;}
inline size_t xStreamBufferReceive(StreamBufferHandle_t s,void* data,size_t n,int){auto p=static_cast<uint8_t*>(data);size_t i=0;while(i<n&&!s->bytes.empty()){p[i++]=s->bytes.front();s->bytes.pop_front();}return i;}
