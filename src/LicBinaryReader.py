"""
    Lic - Instruction Book Creation software
    Copyright (C) 2010 Remi Gagne

    This file (LicBinaryReader.py) is part of Lic.

    Lic is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Lic is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/
"""

import logging

from LicCommonImports import *

from LicModel import *
import LicTemplate
import LicCustomPages

def ro(targetType):
    def tmp(self):
        c = targetType()
        self >> c
        return c
    return tmp

QDataStream.readQPixmap = ro(QPixmap)
QDataStream.readQColor = ro(QColor)
QDataStream.readQBrush = ro(QBrush)
QDataStream.readQFont = ro(QFont)
QDataStream.readQPen = ro(QPen)
QDataStream.readQRectF = ro(QRectF)
QDataStream.readQPointF = ro(QPointF)
QDataStream.readQString = ro(QString)
QDataStream.readQSizeF = ro(QSizeF)
QDataStream.readQSize = ro(QSize)

# To check file version:
#    if stream.licFileVersion >= 6:
#        do whatever

# Variables used throughout this module.  
# Having these global here avoids having to pass them as arguments to every single method in here
partDict = {}
colorDict = None

def loadLicFile(filename, instructions, FileVersion, MagicNumber):
    
    fh, stream = __createStream(filename, FileVersion, MagicNumber)

    if stream.licFileVersion >= 14:
        yield stream.readInt32()
    else:
        yield 500  # Some entirely arbitrary, made up sky number, for older files

    template = __readTemplate(stream, instructions)
    yield

    for unused in __readInstructions(stream, instructions):
        yield

    instructions.licFileVersion = stream.licFileVersion

    if template:
        template.submodel = instructions.mainModel

    template.lockIcon.resetPosition()
    instructions.mainModel.template = template

    if fh is not None:
        fh.close()

def loadLicTemplate(filename, instructions, FileVersion, MagicNumber):

    fh, stream = __createStream(filename, FileVersion, MagicNumber, True)
    template = __readTemplate(stream, instructions)
    if fh is not None:
        fh.close()

    return template

def loadLicTemplateSettings(filename, instructions, FileVersion, MagicNumber):

    fh, stream = __createStream(filename, FileVersion, MagicNumber, True)
    instructions.templateSettings.readFromStream(stream)
    if fh is not None:
        fh.close()

def __createStream(filename, FileVersion, MagicNumber, template = False):

    fh = QFile(filename)
    if not fh.open(QIODevice.ReadOnly):
        raise IOError, unicode(fh.errorString())

    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)

    ext = ".lit" if template else ".lic"
    magic = stream.readInt32()
    if magic != MagicNumber:
        raise IOError, "not a valid " + ext + " file"

    stream.licFileVersion = stream.readInt16()
    if stream.licFileVersion > FileVersion:
        raise IOError, "Cannot read file %s. It was created with a newer version of Lic (%d) than you're using (%d)." % (filename, stream.licFileVersion, FileVersion)
    return fh, stream
    
def __readTemplate(stream, instructions):

    filename = str(stream.readQString())
    if stream.licFileVersion >= 15:
        LicTemplate.TemplatePage.separatorsVisible = stream.readBool()

    if stream.licFileVersion >= 16:
        LicTemplate.TemplatePLI.includeSubmodels = stream.readBool()

    # Read in the entire abstractPart dictionary
    global partDict, colorDict
    colorDict = instructions.colorDict
    partDict = {}
    for unused in __readPartDictionary(stream, instructions):
        pass

    submodelPart = __readSubmodel(stream, None)
    template = __readPage(stream, instructions.mainModel, instructions, submodelPart)
    template.submodelPart = submodelPart

    if stream.licFileVersion >= 12:
        class T(object):
            pass
        t = template.staticInfo = T()
        t.page, t.csi, t.pli, t.smp = T(), T(), T(), T()
        __readStaticInfo(stream, instructions, t.page, t.csi, t.pli, t.smp)

    if stream.licFileVersion >= 5:
        values = []
        for unused in range(stream.readInt32()):
            values.append(stream.readFloat())
        LicGLHelpers.setLightParameters(*values)

    for part in template.submodelPart.parts:
        part.abstractPart = partDict[part.filename]

        template.steps[0].csi.addPart(part)

    for abstractPart in partDict.values():
        if abstractPart.glDispID == LicGLHelpers.UNINIT_GL_DISPID:
            abstractPart.createGLDisplayList()

    for glItem in template.glItemIterator():
        if hasattr(glItem, 'createGLDisplayList'):
            glItem.createGLDisplayList()

    template.submodelPart.createGLDisplayList()
    template.submodelItem.setAbstractPart(template.submodelPart)
    template.postLoadInit(filename)

    return template

def __readStaticInfo(stream, instructions, page, csi, pli, smp):

    page.PageSize = stream.readQSize()
    page.Resolution = stream.readFloat()
    if stream.licFileVersion >= 11:
        page.NumberPos = stream.readQString()

    if stream.licFileVersion < 21:
        settings = instructions.templateSettings
        settings.CSI.scale = stream.readFloat()
        settings.PLI.scale = stream.readFloat()
        settings.SubmodelPreview.scale = stream.readFloat()
    
        settings.CSI.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        settings.PLI.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        settings.SubmodelPreview.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]

def __readInstructions(stream, instructions):

    global partDict, colorDict
    partDict = instructions.partDictionary
    colorDict = instructions.colorDict

    filename = str(stream.readQString())
    instructions.filename = filename

    __readStaticInfo(stream, instructions, LicCustomPages.Page, CSI, PLI, SubmodelPreview)

    for unused in __readPartDictionary(stream, instructions):
        yield

    if stream.licFileVersion < 6:
        for unused in range(stream.readInt32()):
            model = __readSubmodel(stream, instructions)
            partDict[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions, True)

    instructions.mainModel.titlePage = __readTitlePage(stream, instructions)
    if instructions.mainModel.titlePage is not None:
        instructions.mainModel._hasTitlePage = True

    for unused in range(stream.readInt32()):
        newPage = __readPartListPage(stream, instructions)
        instructions.mainModel.partListPages.append(newPage)

    for unused in range(stream.readInt32()):
        instructions.scene.addGuide(stream.readInt32(), stream.readQPointF())

    __linkModelPartNames(instructions.mainModel)

    for submodel in [p for p in partDict.values() if p.isSubmodel]:
        if submodel._parent == "":
            submodel._parent = instructions
        elif submodel._parent == filename:
            submodel._parent = instructions.mainModel
        else:
            submodel._parent = partDict[submodel._parent]

    for unused in instructions.initGLDisplayLists():
        yield

    if instructions.mainModel.hasTitlePage() and instructions.mainModel.titlePage.submodelItem:
        item = instructions.mainModel.titlePage.submodelItem
        item.abstractPart.createGLDisplayList(False)

def __readSubmodel(stream, instructions, createMainmodel = False):

    submodel = __readAbstractPart(stream, True, createMainmodel)
    submodel.instructions = instructions

    for unused in range(stream.readInt32()):
        page = __readPage(stream, submodel, instructions)
        submodel.pages.append(page)

    submodel.submodelNames = []
    for unused in range(stream.readInt32()):
        if stream.licFileVersion < 6:
            filename = str(stream.readQString())
            model = partDict[filename]
            model.used = True
            submodel.submodels.append(model)
        else:
            submodel.submodelNames.append(str(stream.readQString()))

    submodel._row = stream.readInt32()
    submodel._parent = str(stream.readQString())
    submodel.isSubAssembly = stream.readBool()

    return submodel

def __readLicColor(stream):
    if stream.licFileVersion >= 13:
        if stream.readBool():
            r, g, b, a = stream.readFloat(), stream.readFloat(), stream.readFloat(), stream.readFloat()
            name = str(stream.readQString())
            if (stream.licFileVersion >= 23):
                code = stream.readInt32()
            else:
                color = next((x for x in colorDict.values() if hasattr(x, 'name') and x.name == name), None)
                code = color.ldrawCode if color else 16
            newColor = LicHelpers.LicColor(r, g, b, a, name, code)
            dictColor = colorDict.get(code)
            if dictColor and dictColor != newColor:
                logging.debug('Loading a color that does not match colorDict:\n\tdict: %s\n\tload: %s', dictColor, newColor)
            return dictColor if dictColor else newColor  #  PROBLEM: what if a loaded color matches (by code) a color in the dict, but has different rgb values?
        return None
    return colorDict[stream.readInt32()]

def __readPartDictionary(stream, instructions):

    global partDict
    for unused in range(stream.readInt32()):
        abstractPart = __readAbstractPart(stream)
        partDict[abstractPart.filename] = abstractPart
        yield

    if stream.licFileVersion >= 6:
        for unused in range(stream.readInt32()):
            abstractPart = __readSubmodel(stream, instructions)
            partDict[abstractPart.filename] = abstractPart
            yield

    # Each AbstractPart can contain several Parts, but those Parts do
    # not yet have valid AbstractParts of their own.  Create those now.
    for abstractPart in partDict.values():
        for part in abstractPart.parts:
            part.abstractPart = partDict[part.filename]

def __readAbstractPart(stream, createSubmodel = False, createMainmodel = False):

    if createMainmodel:
        part = Mainmodel()
    elif createSubmodel:
        part = Submodel()
    else:
        part = AbstractPart()

    part.filename = str(stream.readQString())
    part.name = str(stream.readQString())

    part.isPrimitive = stream.readBool()
    part.width = stream.readInt32()
    part.height = stream.readInt32()
    part.leftInset = stream.readInt32()
    part.bottomInset = stream.readInt32()
    part.center = stream.readQPointF()

    part.pliScale = stream.readFloat()
    part.pliRotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]

    for unused in range(stream.readInt32()):
        p = __readPrimitive(stream)
        part.addPrimitive(p)

    for unused in range(stream.readInt32()):
        p = __readPart(stream)
        part.parts.append(p)
    return part

def __readPrimitive(stream):
    color = __readLicColor(stream)
    type = stream.readInt16()
    winding = stream.readInt32()
    
    if type == GL.GL_LINES:
        count = 6
    elif type == GL.GL_TRIANGLES:
        count = 9 
    elif type == GL.GL_QUADS:
        count = 12
    
    points = []
    for unused in range(count):
        points.append(stream.readFloat())
    return Primitive(color, points, type, winding)

def __readPart(stream):
    
    filename = str(stream.readQString())
    invert = stream.readBool()
    color = __readLicColor(stream)
    matrix = []

    for unused in range(16):
        matrix.append(stream.readFloat())

    inCallout = stream.readBool()
    pageNumber = stream.readInt32()
    stepNumber = stream.readInt32()
    isInPLI = True
    if stream.licFileVersion >= 7:
        isInPLI = stream.readBool()

    useDisplacement = stream.readBool()
    if useDisplacement:
        displacement = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        displaceDirection = stream.readInt32()
        if filename != 'arrow':
            arrows = []
            if stream.licFileVersion >= 4:
                for unused in range(stream.readInt32()):
                    arrows.append(__readPart(stream))
            else:
                arrows.append(__readPart(stream))
        
    if filename == 'arrow':
        arrow = Arrow(displaceDirection)
        arrow.matrix = matrix
        arrow.displacement = displacement
        arrow.setLength(stream.readInt32())
        arrow.axisRotation = stream.readFloat()
        return arrow
    
    part = Part(filename, color, matrix, invert)
    part.inCallout = inCallout
    part.pageNumber = pageNumber
    part.stepNumber = stepNumber
    part.isInPLI = isInPLI

    if useDisplacement:
        part.displacement = displacement
        part.displaceDirection = displaceDirection
        for arrow in arrows:
            arrow.setParentItem(part)
        part.arrows = arrows

    return part

def __readAnnotationSet(stream, page):
    for unused in range(stream.readInt32()):
        pixmap = stream.readQPixmap()
        filename = str(stream.readQString())
        pos = stream.readQPointF()
        annotation = LicCustomPages.PageAnnotation(page, pixmap, filename, pos)
        page.annotations.append(annotation)
        page.addChild(len(page.children), annotation)

        if stream.licFileVersion >= 10:
            annotation.isAnnotation = stream.readBool()
            annotation.setZValue(stream.readInt32())

def __readPage(stream, parent, instructions, templateModel = None):

    number = stream.readInt32()
    row = stream.readInt32()
    
    if templateModel:
        page = LicTemplate.TemplatePage(parent, instructions)
        if page.submodel is None:
            page.submodel = templateModel
    else:
        page = LicCustomPages.Page(parent, instructions, number, row)

    __readRoundedRectItem(stream, page)
    if stream.licFileVersion < 20:
        page.color = stream.readQColor()

    if templateModel and stream.licFileVersion < 20:
        instructions.templateSettings.Page.backgroundColor = QColor(page.color);
        
    page.layout.orientation = stream.readInt32()
    page.numberItem.setPos(stream.readQPointF())
    page.numberItem.setFont(stream.readQFont())

    if stream.licFileVersion >= 17:
        if stream.readBool():
            page.numberItem._customNumber = stream.readInt32()

    # Read in each step in this page
    for unused in range(stream.readInt32()):
        page.addStep(__readStep(stream, page))

    # Read in the optional submodel preview image
    if stream.readBool():
        page.submodelItem = __readSubmodelItem(stream, page)
        page.addChild(page.submodelItem._row, page.submodelItem)

    if templateModel and stream.licFileVersion < 20:
        step = page.steps[0]
        arrow = step.callouts[0].arrow
        instructions.templateSettings.Callout.arrow.pen = QPen(arrow.pen())
        instructions.templateSettings.Callout.arrow.pen.cornerRadius = 0
        instructions.templateSettings.Callout.arrow.brush = QBrush(arrow.brush())
        instructions.templateSettings.GraphicsRotateArrowItem.arrowPen = QPen(step.rotateIcon.arrowPen)

    # Read in any page separator lines
    for unused in range(stream.readInt32()):
        separator = page.addStepSeparator(stream.readInt32(), signal = False)
        separator.setPos(stream.readQPointF())
        separator.setRect(stream.readQRectF())
        separator.setPen(stream.readQPen())
        if stream.licFileVersion >= 15:
            separator.enabled = stream.readBool()
        separator.normalizePosition()

    if stream.licFileVersion >= 8:
        __readAnnotationSet(stream, page)

    return page

def __readTitlePage(stream, instructions):
    if not stream.readBool():
        return None

    page = LicCustomPages.TitlePage(instructions)

    __readRoundedRectItem(stream, page)
    if stream.licFileVersion < 20:
        page.color = stream.readQColor()

    if stream.readBool():
        page.submodelItem = __readSubmodelItem(stream, page)
        page.submodelItem.itemClassName = "TitleSubmodelPreview"  # Override regular name so we don't set this in any template action

    for unused in range(stream.readInt32()):
        page.addNewLabel(stream.readQPointF(), stream.readQFont(), str(stream.readQString()))

    if stream.licFileVersion >= 8:
        __readAnnotationSet(stream, page)

    return page

def __readPartListPage(stream, instructions):

    page = LicCustomPages.PartListPage(instructions, stream.readInt32(), stream.readInt32())

    __readRoundedRectItem(stream, page)
    if stream.licFileVersion < 20:
        page.color = stream.readQColor()

    page.numberItem.setPos(stream.readQPointF())
    page.numberItem.setFont(stream.readQFont())

    page.pli = __readPLI(stream, page, True)

    if stream.licFileVersion >= 8:
        __readAnnotationSet(stream, page)

    return page

def __readStep(stream, parent):
    
    stepNumber = stream.readInt32()
    pliExists = stream.readBool()
    hasNumberItem = stream.readBool()
    
    step = Step(parent, stepNumber, pliExists, hasNumberItem)
    
    step.setPos(stream.readQPointF())
    step.setRect(stream.readQRectF())
    step.maxRect = stream.readQRectF()

    step.csi = __readCSI(stream, step)

    if pliExists:
        step.pli = __readPLI(stream, step)

    step._hasPLI = stream.readBool()
    if not step._hasPLI and step.pli:
        step.disablePLI()

    if hasNumberItem:
        step.numberItem.setPos(stream.readQPointF())
        step.numberItem.setFont(stream.readQFont())

    for unused in range(stream.readInt32()):
        callout = __readCallout(stream, step)
        step.callouts.append(callout)

    if stream.licFileVersion >= 3:
        if stream.readBool():
            step.addRotateIcon()
            __readRoundedRectItem(stream, step.rotateIcon)
            if stream.licFileVersion < 20:
                step.rotateIcon.arrowPen = stream.readQPen()

    if stream.licFileVersion >= 17:
        if stream.readBool():
            step.numberItem._customNumber = stream.readInt32()

    return step

def __readCallout(stream, parent):
    
    callout = Callout(parent, stream.readInt32(), stream.readBool())
    callout.borderFit = stream.readInt32()
    __readRoundedRectItem(stream, callout)
    
    callout.arrow.tipRect.point = stream.readQPointF()
    callout.arrow.baseRect.point = stream.readQPointF()
    if stream.licFileVersion < 20:
        callout.arrow.setPen(stream.readQPen())
        callout.arrow.setBrush(stream.readQBrush())

    if stream.readBool():  # has quantity label
        callout.addQuantityLabel(stream.readQPointF(), stream.readQFont())
        callout.setQuantity(stream.readInt32())

    for unused in range(stream.readInt32()):
        step = __readStep(stream, callout)
        callout.steps.append(step)

    for unused in range(stream.readInt32()):
        part = __readPart(stream)
        part.abstractPart = partDict[part.filename]
        step = callout.getStepByNumber(part.stepNumber)
        step.addPart(part)

    return callout

def __readSubmodelItem(stream, page):
    
    submodelItem = SubmodelPreview(page, page.submodel)
    submodelItem._row = stream.readInt32()
    __readRoundedRectItem(stream, submodelItem)
    submodelItem.scaling = stream.readFloat()
    submodelItem.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
    submodelItem.isSubAssembly = stream.readBool()
    if submodelItem.isSubAssembly:
        submodelItem.pli = __readPLI(stream, submodelItem)

    if stream.licFileVersion >= 9:
        if stream.readBool():  # Have a quantity label
            submodelItem.quantity = stream.readInt32()
            submodelItem.addQuantityLabel(submodelItem.quantity)
            submodelItem.numberItem.setPos(stream.readQPointF())
            submodelItem.numberItem.setFont(stream.readQFont())

    if submodelItem.scaling != 1.0:
        part, scale = submodelItem.abstractPart, submodelItem.scaling
        part.width *= scale
        part.height *= scale

    if stream.licFileVersion >= 18:
        submodelItem.abstractPart.width = stream.readInt32()
        submodelItem.abstractPart.height = stream.readInt32()
        submodelItem.abstractPart.center.setX(stream.readInt32())
        submodelItem.abstractPart.center.setY(stream.readInt32())

    return submodelItem

def __readCSI(stream, step):

    csi = CSI(step)
    csi.setPos(stream.readQPointF())

    csi.setRect(0.0, 0.0, stream.readInt32(), stream.readInt32())
    csi.center = stream.readQPointF()

    csi.scaling = stream.readFloat()
    csi.rotation = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
    csi.isDirty = False

    return csi

def __readPLI(stream, parent, makePartListPLI = False):

    if makePartListPLI:
        pli = LicCustomPages.PartListPLI(parent)
    else:
        pli = PLI(parent)
    __readRoundedRectItem(stream, pli)

    for unused in range(stream.readInt32()):
        pliItem = __readPLIItem(stream, pli)
        pli.pliItems.append(pliItem)

    return pli

def __readPLIItem(stream, pli):

    filename = str(stream.readQString())
    abstractPart = partDict[filename]
    color = __readLicColor(stream)

    pliItem = PLIItem(pli, abstractPart, color, stream.readInt32())
    pliItem.setPos(stream.readQPointF())
    pliItem.setRect(stream.readQRectF())

    pliItem.numberItem.setPos(stream.readQPointF())
    pliItem.numberItem.setFont(stream.readQFont())

    if stream.licFileVersion >= 2:
        if stream.readBool():  # Have a length indicator
            li = pliItem.lengthIndicator
            li.setPos(stream.readQPointF())
            li.setRect(stream.readQRectF())
            li.setFont(stream.readQFont())
            li.lengthText = str(stream.readQString())
            li.labelColor = stream.readQColor()
            li.setPen(stream.readQPen())
            li.setBrush(stream.readQBrush())

    return pliItem

def __readRoundedRectItem(stream, parent):
    parent.setPos(stream.readQPointF())
    parent.setRect(stream.readQRectF())
    
    if stream.licFileVersion < 20:
        pen = stream.readQPen()
        parent.setBrush(stream.readQBrush())
        pen.cornerRadius = stream.readInt16()
        parent.setPen(pen)

def __linkModelPartNames(model):

    for modelName in model.submodelNames:
        newSubmodel = partDict[modelName]
        newSubmodel.used = True
        model.submodels.append(newSubmodel)

    for m in model.submodels:
        __linkModelPartNames(m)

    for part in model.parts:
        part.abstractPart = partDict[part.filename]
        if part.abstractPart.isSubmodel:
            part.abstractPart.used = True

    for part in model.parts:
        if part.pageNumber >= 0 and part.stepNumber >= 0:
            page = model.getPage(part.pageNumber)
            csi = page.getStepByNumber(part.stepNumber).csi
            csi.addPart(part)

    # Associate each part that has a matching part in a callout to that matching part, and vice versa
    for part in [p for p in model.parts if p.inCallout]:
        for callout in part.getStep().callouts:
            for calloutPart in callout.getPartList():
                if (calloutPart.filename == part.filename) and (calloutPart.matrix == part.matrix) and (calloutPart.color == part.color):
                    part.calloutPart = calloutPart
                    calloutPart.originalPart = part
                    break

