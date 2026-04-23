#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "GLPK::GLPK" for configuration "Release"
set_property(TARGET GLPK::GLPK APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GLPK::GLPK PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libGLPK.so.5.0"
  IMPORTED_SONAME_RELEASE "libGLPK.so.5.0"
  )

list(APPEND _cmake_import_check_targets GLPK::GLPK )
list(APPEND _cmake_import_check_files_for_GLPK::GLPK "${_IMPORT_PREFIX}/lib/libGLPK.so.5.0" )

# Import target "GLPK::glpsol" for configuration "Release"
set_property(TARGET GLPK::glpsol APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(GLPK::glpsol PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/bin/glpsol"
  )

list(APPEND _cmake_import_check_targets GLPK::glpsol )
list(APPEND _cmake_import_check_files_for_GLPK::glpsol "${_IMPORT_PREFIX}/bin/glpsol" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
