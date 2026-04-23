#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "ortools::solve" for configuration "Release"
set_property(TARGET ortools::solve APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ortools::solve PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/solve"
  )

list(APPEND _cmake_import_check_targets ortools::solve )
list(APPEND _cmake_import_check_files_for_ortools::solve "${_IMPORT_PREFIX}/bin/solve" )

# Import target "ortools::ortools" for configuration "Release"
set_property(TARGET ortools::ortools APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(ortools::ortools PROPERTIES
  IMPORTED_LINK_INTERFACE_LANGUAGES_RELEASE "CXX"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libortools.a"
  )

list(APPEND _cmake_import_check_targets ortools::ortools )
list(APPEND _cmake_import_check_files_for_ortools::ortools "${_IMPORT_PREFIX}/lib/libortools.a" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
