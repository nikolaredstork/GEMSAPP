#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "antares-ybyaggregator" for configuration "Release"
set_property(TARGET antares-ybyaggregator APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(antares-ybyaggregator PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/antares-ybyaggregator"
  )

list(APPEND _cmake_import_check_targets antares-ybyaggregator )
list(APPEND _cmake_import_check_files_for_antares-ybyaggregator "${_IMPORT_PREFIX}/bin/antares-ybyaggregator" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
