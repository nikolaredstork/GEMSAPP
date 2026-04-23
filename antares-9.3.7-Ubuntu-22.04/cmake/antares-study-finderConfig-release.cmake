#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "antares-study-finder" for configuration "Release"
set_property(TARGET antares-study-finder APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(antares-study-finder PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/antares-study-finder"
  )

list(APPEND _cmake_import_check_targets antares-study-finder )
list(APPEND _cmake_import_check_files_for_antares-study-finder "${_IMPORT_PREFIX}/bin/antares-study-finder" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
