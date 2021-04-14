#
# Copyright (c) European Synchrotron Radiation Facility (ESRF)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

__authors__ = ["O. Svensson"]
__license__ = "MIT"
__date__ = "12/04/2021"


import os
import fabio
import numpy
import shutil
import scipy.ndimage

from PIL import Image
from PIL import ImageOps
from PIL import ImageFile
from PIL import ImageDraw
from PIL import ImageFont

from edna2.tasks.AbstractTask import AbstractTask
from edna2.tasks.ReadImageHeader import ReadImageHeader

from edna2.utils import UtilsPath
from edna2.utils import UtilsImage
from edna2.utils import UtilsConfig
from edna2.utils import UtilsLogging

logger = UtilsLogging.getLogger()


class DiffractionThumbnail(AbstractTask):
    """
    Generates diffraction thumbnail for PyArch
    """

    def getInDataSchema(self):
        return {
            "type": "object",
            "required": ["image"],
            "properties": {
                "image": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "forcedOutputDirectory": {"type": "string"},
                "waitForFileTimeOut": {"type": "number"},
                "format": {"type": "string"}
            }
        }

    def getOutDataSchema(self):
        return {
            "type": "object",
            "properties": {
                "pathToJPEGImage": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "pathToThumbImage": {
                    "type": "array",
                    "items": {"type": "string"}
                },
            },
        }

    def run(self, inData):
        # Loop through all images
        listJPEGTask = []
        listThumbTask = []
        for imagePath in inData["image"]:
            # Check image file extension
            imageFileName, suffix = os.path.splitext(os.path.basename(imagePath))
            if not suffix in [".img", ".marccd", ".mccd", ".cbf", ".h5"]:
                raise RuntimeError("Unknown image file name extension for pyarch thumbnail generator: %s" % imagePath)
            # Wait for image file
            if suffix == ".h5":
                h5MasterFilePath, h5DataFilePath, h5FileNumber = UtilsImage.getH5FilePath(imagePath)
                waitFilePath = h5DataFilePath
            else:
                waitFilePath = imagePath
            expectedSize = self.getExpectedSize(imagePath)
            hasTimedOut, finalSize = UtilsPath.waitForFile(waitFilePath, expectedSize=expectedSize)
            if hasTimedOut:
                raise RuntimeError("Waiting for file {0} timed out!".format(imagePath))
            outputFileName = imageFileName + ".jpeg"
            # Create JPEG with resolution rings
            inDataReadHeader = {
                'imagePath': [imagePath],
            }
            readHeader = ReadImageHeader(
                inData=inDataReadHeader,
                workingDirectorySuffix=imageFileName
            )
            readHeader.execute()
            experimentalCondition = readHeader.outData["subWedge"][0]["experimentalCondition"]
            detector = experimentalCondition["detector"]
            beam = experimentalCondition["beam"]
            inDataCreateJPEG = {
                "image": imagePath,
                "height": 1024,
                "width": 1024,
                "outputFileName": outputFileName,
                "doResolutionRings": True,
                "pixelSizeX": detector["pixelSizeX"],
                "pixelSizeY": detector["pixelSizeY"],
                "beamPositionX": detector["beamPositionX"],
                "beamPositionY": detector["beamPositionY"],
                "distance": detector["distance"],
                "wavelength": beam["wavelength"],
            }
            createJPEG = CreateThumbnail(
                inData=inDataCreateJPEG,
                workingDirectorySuffix=imageFileName + "_JPEG"
            )
            createJPEG.start()
            listJPEGTask.append(createJPEG)
            # Create thumbnail
            outputFileName = imageFileName + ".thumb.jpeg"
            inDataCreateThumb = {
                "image": imagePath,
                "height": 256,
                "width": 256,
                "outputFileName": outputFileName,
                "doResolutionRings": True,
                "pixelSizeX": detector["pixelSizeX"],
                "pixelSizeY": detector["pixelSizeY"],
                "beamPositionX": detector["beamPositionX"],
                "beamPositionY": detector["beamPositionY"],
                "distance": detector["distance"],
                "wavelength": beam["wavelength"],
            }
            createThumb = CreateThumbnail(
                inData=inDataCreateThumb,
                workingDirectorySuffix = imageFileName + "_thumbnail"
            )
            createThumb.start()
            listThumbTask.append(createThumb)
        outData = {
            "pathToJPEGImage": [],
            "pathToThumbImage": []
        }
        for task in listJPEGTask:
            task.join()
            pyarchPath = self.copyThumbnailToPyarch(task)
            outData["pathToJPEGImage"].append(pyarchPath)
        for task in listThumbTask:
            task.join()
            pyarchPath = self.copyThumbnailToPyarch(task)
            outData["pathToThumbImage"].append(pyarchPath)
        return outData

    def getExpectedSize(self, imagePath):
        # Not great but works...
        expectedSize = 1000000
        for beamline in ["id23eh1", "id23eh2", "id30a1", "id30a2", "id30a3", "id30b"]:
            if beamline in imagePath:
                taskConfig = UtilsConfig.getTaskConfig("ExpectedFileSize", "esrf_"+beamline)
                expectedSize = int(taskConfig["image"])
                break
        return expectedSize

    def copyThumbnailToPyarch(self, task):
        imagePath = task.inData["image"]
        thumbNailPath = task.outData["thumbNail"]
        pyarchThumbnailDir = UtilsPath.createPyarchFilePath(os.path.dirname(imagePath))
        if pyarchThumbnailDir is None:
            pyarchThumbnailPath = thumbNailPath
        else:
            if not os.path.exists(pyarchThumbnailDir):
                os.makedirs(pyarchThumbnailDir, 0o755)
            pyarchThumbnailPath = os.path.join(
                pyarchThumbnailDir,
                os.path.basename(thumbNailPath)
            )
            shutil.copy2(thumbNailPath, pyarchThumbnailPath)
        return pyarchThumbnailPath

class CreateThumbnail(AbstractTask):

    def getInDataSchema(self):
        return {
            "type": "object",
            "required": ["image"],
            "properties": {
                "image": {"type": "string"},
                "height": {"type": "number"},
                "width": {"type": "number"},
                "outputPath": {"type": "string"},
                "outputFileName": {"type": "string"},
                "format": {"type": "string"},
                "doResolutionRings": {"type": "boolean"},
                "pixelSizeX": {"type": "number"},
                "pixelSizeY": {"type": "number"},
                "beamPositionX": {"type": "number"},
                "beamPositionY": {"type": "number"},
                "distance": {"type": "number"},
                "wavelength": {"type": "number"}
            }
        }

    def getOutDataSchema(self):
        return {
            "type": "object",
            "properties": {
                "thumbNail": {"type": "string"}
            }
        }

    def run(self, inData):
        image = inData["image"]
        # Check if format is provided
        format = inData.get("format", None)
        height = inData.get("height", 512)
        width = inData.get("width", 512)
        outputPath = inData.get("outputPath", None)
        outputFileName = inData.get("outputFileName", None)
        doResolutionRings = inData.get("doResolutionRings", False)
        pixelSizeX = inData.get("pixelSizeX", False)
        pixelSizeY = inData.get("pixelSizeY", False)
        beamPositionX = inData.get("beamPositionX", False)
        beamPositionY = inData.get("beamPositionY", False)
        distance = inData.get("distance", False)
        wavelength = inData.get("wavelength", False)
        thumbNail = self.createThumbnail(
            image=image,
            format=format,
            height=height,
            width=width,
            outputPath=outputPath,
            workingDirectory=self.getWorkingDirectory(),
            outputFileName=outputFileName,
            doResolutionRings=doResolutionRings,
            pixelSizeX=pixelSizeX,
            pixelSizeY=pixelSizeY,
            beamPositionX=beamPositionX,
            beamPositionY=beamPositionY,
            distance=distance,
            wavelength=wavelength
        )
        outData = {
            "thumbNail": thumbNail
        }
        return outData


    @staticmethod
    def createThumbnail(image, format="jpg", height=512, width=512,
                        outputPath=None, minLevel=0, maxLevel=99.95,
                        dilatation=4, workingDirectory=None,
                        outputFileName=None, doResolutionRings=False,
                        pixelSizeX=None, pixelSizeY=None,
                        beamPositionX=None, beamPositionY=None,
                        distance=None, wavelength=None,
                        ):
        imageFileName = os.path.basename(image)
        imagePath = image
        imageNameWithoutSuffix, imageSuffix = os.path.splitext(imageFileName)
        if imageSuffix == ".h5":
            imageNumber = UtilsImage.getImageNumber(image)
            h5MasterFilePath, h5DataFilePath, h5FileNumber = UtilsImage.getH5FilePath(image)
            fabioImage = fabio.openimage.openimage(h5MasterFilePath)
            print("No frames: {0}".format(fabioImage.nframes))
            if imageNumber < fabioImage.nframes:
                numpyImage = fabioImage.getframe(imageNumber).data
            else:
                numpyImage = fabioImage.data
            if numpyImage.dtype == numpy.dtype("uint32"):
                numpyImage = numpy.where(numpyImage > 65536*65536-2, 0, numpyImage)
            else:
                numpyImage = numpy.where(numpyImage > 256*256-2, 0, numpyImage)
        else:
            fabioImage = fabio.openimage.openimage(image)
            numpyImage = fabioImage.data
        # Default format
        suffix = "jpg"
        pilFormat = "JPEG"
        if format is not None:
            if format.lower() == "png":
                suffix = "png"
                pilFormat = "PNG"
        # The following code has been adapted from EDPluginExecThumbnail written by J.Kieffer
        dtype = numpyImage.dtype
        sortedArray = numpyImage.flatten()
        sortedArray.sort()
        numpyImage = numpy.maximum(numpyImage, int(minLevel) * numpy.ones_like(numpyImage))
        maxLevel = sortedArray[int(round(float(maxLevel) * sortedArray.size / 100.0))]
        if maxLevel < 25:
            maxLevel = 25
        numpyImage = numpy.minimum(numpyImage, maxLevel * numpy.ones_like(numpyImage))
        numpyImage = scipy.ndimage.morphology.grey_dilation(numpyImage, (dilatation, dilatation))
        mumpyImageFloat = (numpyImage.astype(numpy.float32)) / float(maxLevel)
        numpyImageInt = ( mumpyImageFloat * 255.0 ).astype(numpy.uint8)
        # Check if we should do resolution rings
        listResolution = []
        if doResolutionRings:
            delta = (height+width) / 2000
            if delta < 1.0:
                delta = 1.0
            centreX = beamPositionX / pixelSizeX
            centreY = beamPositionY / pixelSizeY
            sizeY, sizeX = numpyImageInt.shape
            averageSize = (sizeX + sizeY) / 2.0
            yy, xx = numpy.mgrid[:sizeY, :sizeX]
            circle = (xx - centreX) ** 2 + (yy - centreY) ** 2
            for resolution in [1.0, 1.1, 1.2, 1.5, 2.0, 3.0, 4.0]:
                import math
                theta = math.asin(wavelength/(2*resolution))
                radius = math.tan(2*theta)* distance / pixelSizeX
                listResolution.append((resolution, radius / averageSize ))
                numpyImageInt = numpy.where(numpy.logical_and(circle < (radius+delta)**2, circle > (radius-delta)**2), 254, numpyImageInt)
        pilOutputImage = ImageOps.invert(Image.fromarray(numpyImageInt, 'L'))
        if height is not None and width is not None:
            pilOutputImage = pilOutputImage.resize((width, height), Image.ANTIALIAS)
        width, height = pilOutputImage.size
        for resolution, distance in listResolution:
            centreX = width / 2
            centreY = height / 2
            textfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(height/30), encoding="unic")
            resolutionText = "{0} Å".format(resolution)
            imageEditable = ImageDraw.Draw(pilOutputImage)
            newDistance = distance  * (height + width) / 2.0 / math.sqrt(2)
            imageEditable.text((centreX + newDistance - width/20, centreY + newDistance -height/20), resolutionText, 0, font=textfont)
        if width * height > ImageFile.MAXBLOCK:
            ImageFile.MAXBLOCK = width * height
        if outputPath is None:
            if outputFileName is None:
                outputPath = os.path.join(workingDirectory, os.path.splitext(imageFileName)[0] + "." + suffix)
            else:
                outputPath = os.path.join(workingDirectory, outputFileName)
        pilOutputImage.save(outputPath, pilFormat, quality=85, optimize=True)
        logger.info("Output thumbnail path: %s" % outputPath)
        return outputPath
