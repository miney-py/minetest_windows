"""
Compile minetest for windows with luasocket.

Copyright (C) 2019 Robert Lieback <robertlieback@zetabyte.de>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation; either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import os
from os import path
import shutil
import logging
from subprocess import run
from datetime import datetime
from distutils.dir_util import copy_tree
import urllib.request
from zipfile import ZipFile

# create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

start_time = datetime.now()

if len(sys.argv) > 1:
    if "x86" in sys.argv:
        ARCH = "x86"
    elif "x64" in sys.argv:
        ARCH = "x64"
    else:
        ARCH = "x86"
    if "--force-rebuild" in sys.argv:
        logger.info("Forcing rebuild")
        FORCE_REBUILD = True
        if os.path.isdir('build'):
            shutil.rmtree('build')
    else:
        FORCE_REBUILD = False
else:
    ARCH = "x86"
logger.info(f"Set CPU architecture to {ARCH}")

join = path.join

# Create build paths
ROOT_PATH = os.getcwd()
if not path.isdir("build"):
    os.mkdir("build")
if not path.isdir(join("build", ARCH)):
    os.mkdir(join("build", ARCH))
os.chdir(join(os.getcwd(), "build", ARCH))
if not path.isdir("tools"):
    os.mkdir("tools")

BUILD = os.getcwd()
BUILD_TOOLS = join(BUILD, "tools")
VCPKG = join(BUILD_TOOLS, "vcpkg", "vcpkg.exe")
LUAROCKS = join(BUILD_TOOLS, "luarocks_" + ARCH, "luarocks.bat")
DIST = join(ROOT_PATH, "dist", "minetest_" + ARCH)

logger.info(f"Building into {BUILD}")

# vcpkg
if not path.isdir(join(BUILD_TOOLS, "vcpkg")):
    logger.info("vcpkg - Download vcpkg from github")
    ret = run(
        [
            "git", "clone", "--single-branch", "--branch", "2020.11", "-c", "advice.detachedHead=false",
            "https://github.com/microsoft/vcpkg.git", join(BUILD_TOOLS, "vcpkg")
        ],
    )
    if ret.returncode != 0:
        raise Exception("vcpkg - Couldn't download vcpkg from github")
else:
    logger.info("vcpkg - found folder")

if not path.isfile(VCPKG):
    logger.info("vcpkg - Bootstrapping vcpkg")
    ret = run([join(BUILD_TOOLS, "vcpkg", "bootstrap-vcpkg.bat"), "-disableMetrics"], cwd=join(BUILD_TOOLS, "vcpkg"))
    if ret.returncode != 0:
        raise Exception("vcpkg - Couldn't bootstrapping vcpkg")
else:
    logger.info("vcpkg - found executable")

# vcpkg - compile depencies
if not path.isdir(join(BUILD_TOOLS, "vcpkg", "buildtrees", "sqlite3", ARCH+"-windows-rel")):
    logger.info("vcpkg - Compiling build depencies")
    ret = run(
        [VCPKG, "install",
         "irrlicht", "zlib", "curl[winssl]", "openal-soft", "libvorbis", "libogg", "sqlite3", "freetype", "luajit",
         "gettext", "--triplet", f"{ARCH}-windows", "--no-binarycaching"],  # gettext for translations
        cwd=join(BUILD_TOOLS, "vcpkg")
    )
    if ret.returncode != 0:
        raise Exception("vcpkg - Couldn't compiling build depencies")
else:
    logger.info("vcpkg - Found compiled depencies")

# gettext - download missing gettext tools
if not path.isdir(join(BUILD_TOOLS, "gettext_tools")):
    logger.info("gettext - Download missing gettext tools")
    urllib.request.urlretrieve("https://github.com/mlocati/gettext-iconv-windows/releases/download/v0.19.8.1-v1.15/gettext0.19.8.1-iconv1.15-shared-32.zip", join(BUILD_TOOLS, "gettext_tools.zip"))
    with ZipFile(join(BUILD_TOOLS, "gettext_tools.zip"), "r") as zipfile:
        zipfile.extractall(join(BUILD_TOOLS, "gettext_tools"))
    os.unlink(join(BUILD_TOOLS, "gettext_tools.zip"))
else:
    logger.info("gettext - Found gettext tools")

# luarocks
if not path.isdir(join(BUILD_TOOLS, "luarocks")):
    logger.info("luarocks - Clone luarocks from github")
    ret = run(["git", "clone", "--single-branch", "--branch", "v3.4.0", "-c", "advice.detachedHead=false", "https://github.com/luarocks/luarocks.git", join(BUILD_TOOLS, "luarocks")])
    if ret.returncode != 0:
        raise Exception("luarocks - Couldn't clone luarocks from github")
else:
    logger.info("luarocks - found luarocks repo directory")

# luarocks arch env
if not path.isfile(LUAROCKS):
    logger.info("luarocks - install to " + join(BUILD_TOOLS, "luarocks_" + ARCH))
    ret = run(
        [
            join(BUILD_TOOLS, "luarocks", "install.bat"),
            "/SELFCONTAINED", "/NOREG", "/NOADMIN", "/Q",
            "/P", join(BUILD_TOOLS, "luarocks_" + ARCH),  # the luarocks install target
            "/LUA", join(BUILD_TOOLS, "vcpkg", "buildtrees", "luajit", ARCH + "-windows-rel"),
            "/INC", join(BUILD_TOOLS, "vcpkg", "buildtrees", "luajit", "src",
                         os.listdir(join(BUILD_TOOLS, "vcpkg", "buildtrees", "luajit", "src"))[0], "src")
        ],
        cwd=join(BUILD_TOOLS, "luarocks")
    )
    if ret.returncode != 0:
        raise Exception("luarocks - Couldn't install luarocks")

    # fix path to vcvars to specify architecture
    with open(LUAROCKS, "rb+") as f:
        file_source = str(f.read(), encoding="ascii").replace('vcvarsall', 'vcvars32')
        f.seek(0)
        write_file = f.write(file_source.encode("ascii"))
        f.truncate()
else:
    logger.info("luarocks - found installed luarocks")

# luasocket and lua-cjson
if not path.isfile(join(BUILD_TOOLS, "luarocks_" + ARCH, "systree", "lib", "lua", "5.1", "cjson.dll")) or \
        not path.isfile(join(BUILD_TOOLS, "luarocks_" + ARCH, "systree", "lib", "lua", "5.1", "socket", "core.dll")):
    logger.info("luarocks - Installing luasocket and lua-cjson")
    ret = run([LUAROCKS, "install", "luasocket"])
    if ret.returncode != 0:
        raise Exception("luarocks - Couldn't install luasocket")
    ret = run([LUAROCKS, "install", "lua-cjson"])
    if ret.returncode != 0:
        raise Exception("luarocks - Couldn't install lua-cjson")
else:
    logger.info("luarocks - Found luasocket and lua-cjson")

# minetest
if not os.path.isdir(join(BUILD, "minetest")):
    logger.info("minetest - Cloning from stable repo")
    ret = run(["git", "clone", "--single-branch", "--branch", "5.3.0", "-c", "advice.detachedHead=false", "https://github.com/minetest/minetest.git", join(BUILD, "minetest")])
    if ret.returncode != 0:
        raise Exception("Minetest - Couldn't clone from stable repo")

# minetest - compile
if not path.isfile(join(BUILD, "minetest", "bin", "Release_" + ARCH, "minetest.exe")):
    logger.info("Minetest - Compiling Minetest")
    if ARCH == "x64":
        carch = "x64"
    else:
        carch = "Win32"

    # find cmake in vcpkg
    cmake_dir1 = [i for i in os.listdir(join(BUILD_TOOLS, "vcpkg", "downloads", "tools")) if "cmake" in i][0]
    cmake_dir2 = os.listdir(join(BUILD_TOOLS, "vcpkg", "downloads", "tools", cmake_dir1))[0]
    cmake_path = join(BUILD_TOOLS, "vcpkg", "downloads", "tools", cmake_dir1, cmake_dir2, "bin", "cmake.exe")
    
    # delete cmake caches
    if path.isdir(join(BUILD, "minetest", "CMakeFiles")):
        os.system(f'rmdir /s /q "{join(BUILD, "minetest", "CMakeFiles")}"')
    if path.isfile(join(BUILD, "minetest", "CMakeCache.txt")):
        os.unlink(join(BUILD, "minetest", "CMakeCache.txt"))

    ret = run(
        [
            cmake_path, ".",
            "-G", "Visual Studio 16 2019",
            "-A", carch,
            f"-DCMAKE_TOOLCHAIN_FILE={BUILD_TOOLS}/vcpkg/scripts/buildsystems/vcpkg.cmake",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DENABLE_GETTEXT=1",
            f"-DGETTEXT_MSGFMT={BUILD_TOOLS}/gettext_tools/bin/msgfmt.exe",
            # f"-DGETTEXT_DLL={BUILD_TOOLS}/vcpkg/buildtrees/gettext/{ARCH}-windows-rel/libintl.dll",
            f"-DGETTEXT_ICONV_DLL={BUILD_TOOLS}/vcpkg/buildtrees/libiconv/{ARCH}-windows-rel/libiconv.dll",
            "-DENABLE_CURSES=0",
            "-DRUN_IN_PLACE=TRUE"
        ],
        cwd=join(BUILD, "minetest")
    )
    if ret.returncode != 0:
        raise Exception("Minetest - Couldn't prepair minetest")
    ret = run(
        [
            cmake_path, "--build", ".", "--config", "Release"
        ], cwd=join(BUILD, "minetest")
    )
    if ret.returncode != 0:
        raise Exception("Minetest - Couldn't build minetest")
    # rename directory
    os.rename(join(BUILD, "minetest", "bin", "Release"), join(BUILD, "minetest", "bin", "Release_" + ARCH))
else:
    logger.info("minetest - found compiled minetest")

# minetest - game
if not path.isdir(join(BUILD, "minetest_game")):
    logger.info("minetest game - cloning repo")
    ret = run(
        ["git", "clone", "--single-branch", "--branch", "stable-5", "-c", "advice.detachedHead=false", "https://github.com/minetest/minetest_game.git"]
    )
    if ret.returncode != 0:
        raise Exception("Minetest - Couldn't clone minetest")
else:
    logger.info("minetest game - found directory")

# Build distribution
if not path.isdir(join(ROOT_PATH, "dist")):
    os.mkdir(join(ROOT_PATH, "dist"))
if not path.isdir(DIST):
    logger.info("Building distribution")
    os.mkdir(DIST)
    copy_tree(os.path.join(BUILD, "minetest", "bin", "Release_" + ARCH), join(DIST, "bin"))
    copy_tree(os.path.join(BUILD, "minetest", "builtin"), join(DIST, "builtin"))
    copy_tree(os.path.join(BUILD, "minetest", "client"), join(DIST, "client"))
    copy_tree(os.path.join(BUILD, "minetest", "clientmods"), join(DIST, "clientmods"))
    copy_tree(os.path.join(BUILD, "minetest", "doc"), join(DIST, "doc"))
    copy_tree(os.path.join(BUILD, "minetest", "fonts"), join(DIST, "fonts"))
    copy_tree(os.path.join(BUILD, "minetest", "games"), join(DIST, "games"))
    copy_tree(os.path.join(BUILD, "minetest", "mods"), join(DIST, "mods"))
    copy_tree(os.path.join(BUILD, "minetest", "locale"), join(DIST, "locale"))
    copy_tree(os.path.join(BUILD, "minetest", "textures"), join(DIST, "textures"))
    shutil.copyfile(os.path.join(BUILD, "minetest", "LICENSE.txt"), join(DIST, "LICENSE.txt"))
    os.unlink(join(DIST, "bin", "minetest.pdb"))

    copy_tree(os.path.join(BUILD, "minetest_game"), join(DIST, "games", "minetest_game"))
    os.system('rmdir /s /q "%s"' % join(DIST, "games", "minetest_game", ".git"))
    os.mkdir(join(DIST, "worlds"))

    copy_tree(os.path.join(BUILD_TOOLS, "luarocks_" + ARCH, "systree", "lib", "lua", "5.1"), join(DIST, "bin"))
    copy_tree(os.path.join(BUILD_TOOLS, "luarocks_" + ARCH, "systree", "share", "lua", "5.1"), join(DIST, "bin", "lua"))

logger.info("That run took " + str(datetime.now() - start_time))
