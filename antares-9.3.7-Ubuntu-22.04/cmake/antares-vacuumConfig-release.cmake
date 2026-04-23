#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "antares-vacuum" for configuration "Release"
set_property(TARGET antares-vacuum APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(antares-vacuum PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/antares-vacuum"
  )

list(APPEND _cmake_import_check_targets antares-vacuum )
list(APPEND _cmake_import_check_files_for_antares-vacuum "${_IMPORT_PREFIX}/bin/antares-vacuum" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
