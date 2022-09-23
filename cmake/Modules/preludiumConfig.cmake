INCLUDE(FindPkgConfig)
PKG_CHECK_MODULES(PC_PRELUDIUM preludium)

FIND_PATH(
    PRELUDIUM_INCLUDE_DIRS
    NAMES preludium/api.h
    HINTS $ENV{PRELUDIUM_DIR}/include
        ${PC_PRELUDIUM_INCLUDEDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/include
          /usr/local/include
          /usr/include
)

FIND_LIBRARY(
    PRELUDIUM_LIBRARIES
    NAMES gnuradio-preludium
    HINTS $ENV{PRELUDIUM_DIR}/lib
        ${PC_PRELUDIUM_LIBDIR}
    PATHS ${CMAKE_INSTALL_PREFIX}/lib
          ${CMAKE_INSTALL_PREFIX}/lib64
          /usr/local/lib
          /usr/local/lib64
          /usr/lib
          /usr/lib64
)

INCLUDE(FindPackageHandleStandardArgs)
FIND_PACKAGE_HANDLE_STANDARD_ARGS(PRELUDIUM DEFAULT_MSG PRELUDIUM_LIBRARIES PRELUDIUM_INCLUDE_DIRS)
MARK_AS_ADVANCED(PRELUDIUM_LIBRARIES PRELUDIUM_INCLUDE_DIRS)

