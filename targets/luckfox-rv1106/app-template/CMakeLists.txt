cmake_minimum_required(VERSION 3.16)
project(gar_luckfox_streamer LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(gar_luckfox_streamer
  src/main.cpp
)

target_compile_options(gar_luckfox_streamer PRIVATE
  -Wall
  -Wextra
  -Wpedantic
)

target_link_libraries(gar_luckfox_streamer PRIVATE pthread dl)

install(TARGETS gar_luckfox_streamer RUNTIME DESTINATION bin)
