cmake_minimum_required(VERSION 2.8.9)

project(TrajectoryReconstructor)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "http://www.example.com/Slicer/Extensions/Locator")
set(EXTENSION_CATEGORY "IGT")
set(EXTENSION_CONTRIBUTORS "Longquan Chen, Junichi Tokuda")
set(EXTENSION_DESCRIPTION "Utility module for MR Tracking Research.")
set(EXTENSION_ICONURL "http://www.example.com/Slicer/Extensions/Locator.png")
set(EXTENSION_SCREENSHOTURLS "http://www.example.com/Slicer/Extensions/TrajectoryReconstructor/Screenshots/1.png")
set(EXTENSION_DEPENDS "Sequences")
#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(TrajectoryReconstructor)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_CPACK})
