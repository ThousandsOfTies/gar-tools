cmake_minimum_required(VERSION 3.16)
project(gar_fake_idf C)

add_library(gar_fake_idf STATIC
  src/gar_fake_idf.c
)

target_include_directories(gar_fake_idf
  PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}/include
)

target_compile_features(gar_fake_idf PUBLIC c_std_11)
