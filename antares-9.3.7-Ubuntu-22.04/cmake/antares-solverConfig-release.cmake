#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "antares-solver" for configuration "Release"
set_property(TARGET antares-solver APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(antares-solver PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/antares-solver"
  )

list(APPEND _cmake_import_check_targets antares-solver )
list(APPEND _cmake_import_check_files_for_antares-solver "${_IMPORT_PREFIX}/bin/antares-solver" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
