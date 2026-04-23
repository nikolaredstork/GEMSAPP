if(NOT TARGET libscip)
  include(CMakeFindDependencyMacro)
  if(0)
    find_dependency(ZIMPL REQUIRED NO_MODULE)
  endif()
  if(0)
    find_dependency(SOPLEX REQUIRED NO_MODULE)
  endif()

  include("${CMAKE_CURRENT_LIST_DIR}/scip-targets.cmake")
endif()

# Legacy
set(SCIP_LIBRARIES libscip)
set(SCIP_INCLUDE_DIRS "${CMAKE_CURRENT_LIST_DIR}/../../../include")
set(SCIP_FOUND TRUE)
