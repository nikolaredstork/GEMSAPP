#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "antares-ui-simulator" for configuration "Release"
set_property(TARGET antares-ui-simulator APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(antares-ui-simulator PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/antares-ui-simulator"
  )

list(APPEND _cmake_import_check_targets antares-ui-simulator )
list(APPEND _cmake_import_check_files_for_antares-ui-simulator "${_IMPORT_PREFIX}/bin/antares-ui-simulator" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
