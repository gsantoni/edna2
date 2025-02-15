#
# Copyright (c) European Synchrotron Radiation Facility (ESRF)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the 'Software'), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

__authors__ = ['O. Svensson']
__license__ = 'MIT'
__date__ = '2021/07/20'

import os
import shutil
import pathlib
import tempfile
import unittest

from edna2.tasks.DozorM2 import DozorM2

from edna2.utils import UtilsTest


class DozorM2UnitTest(unittest.TestCase):

    def setUp(self):
        self.dataPath = UtilsTest.prepareTestDataPath(__file__)

    def test_generateCommandsOneScan(self):
        workingDir = pathlib.Path(tempfile.mkdtemp(prefix="DozorM2_"))
        referenceDataPath = self.dataPath / 'inDataDozorM2_oneScan.json'
        inData = UtilsTest.loadAndSubstitueTestData(referenceDataPath)
        command = DozorM2.generateCommands(inData, workingDir)
        print(command)
        shutil.rmtree(workingDir)

    def test_generateCommandsTwoScans(self):
        workingDir = pathlib.Path(tempfile.mkdtemp(prefix="DozorM2_"))
        referenceDataPath = self.dataPath / 'inDataDozorM2_twoScans.json'
        inData = UtilsTest.loadAndSubstitueTestData(referenceDataPath)
        command = DozorM2.generateCommands(inData, workingDir)
        print(command)
        shutil.rmtree(workingDir)

    def test_unit_parseDozorm2LogFile_1(self):
        logPath = self.dataPath / 'dozorm2.log'
        dictCoord = DozorM2.parseDozorm2LogFile(logPath)
        # pprint.pprint(scan1)
        # pprint.pprint(scan2)
        # pprint.pprint(coord)
        self.assertEqual(len(dictCoord["scan1"]), 8)
        self.assertEqual(len(dictCoord["scan2"]), 8)
        self.assertEqual(len(dictCoord["coord"]), 7)

    def test_unit_DozorM2_parseMap(self):
        mapPath = self.dataPath / 'dozorm_001.map'
        dictMap = DozorM2.parseMap(mapPath)
        # pprint.pprint(dictMap)
        self.assertEqual(dictMap["nx"], 18)
        self.assertEqual(dictMap["ny"], 4)

    def test_unit_DozorM_makePlots(self):
        tmpDir = tempfile.mkdtemp(prefix="test_unit_DozorM_makePlots_")
        mapPath = self.dataPath / 'dozorm_001.map'
        dictMap = DozorM2.parseMap(mapPath)
        imagePath = DozorM2.makeCrystalPlot(dictMap["crystal"], tmpDir, debug=False)
        # os.system("display {0}".format(imagePath))
        self.assertTrue(os.path.exists(imagePath))
        imagePath = DozorM2.makeImageNumberMap(dictMap["imageNumber"], tmpDir, debug=False)
        self.assertTrue(os.path.exists(imagePath))
        shutil.rmtree(tmpDir)
