
####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was Config.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################

include(CMakeFindDependencyMacro)
find_dependency(Boost REQUIRED)
find_package(minizip-ng QUIET) #Optional, don't use find_dependency it forces return in case of dep not found
if (minizip-ng_FOUND)
	add_library(MINIZIP::minizip ALIAS MINIZIP::minizip-ng)
else ()
	find_dependency(minizip)
	if (NOT minizip_FOUND)
		message (FATAL_ERROR "Minizip dependency (minizip or minizip-ng) not found.")
	endif ()
endif ()
find_dependency(ortools REQUIRED)
find_dependency(sirius_solver REQUIRED)
find_dependency(yaml-cpp REQUIRED)
find_dependency(antlr4-runtime REQUIRED)
find_dependency(fmt REQUIRED)
find_package(Boost REQUIRED COMPONENTS iostreams)
include("${CMAKE_CURRENT_LIST_DIR}/AntaresTargets.cmake")

check_required_components(Antares)
