from PyQt4.QtCore import *

from Model import *

def loadLicFile(filename, instructions):
    global FileVersion, MagicNumber

    fh = QFile(filename)
    if not fh.open(QIODevice.ReadOnly):
        raise IOError, unicode(fh.errorString())

    stream = QDataStream(fh)
    stream.setVersion(QDataStream.Qt_4_3)

    magic = stream.readInt32()
    if magic != MagicNumber:
        raise IOError, "not a valid .lic file"

    fileVersion = stream.readInt16()
    if fileVersion != FileVersion:
        raise IOError, "unrecognized .lic file version"

    __readInstructions(stream, instructions)
    instructions.mainModel.selectPage(1)

    if fh is not None:
        fh.close()

def __readInstructions(stream, instructions):
    global partDictionary, submodelDictionary

    instructions.emit(SIGNAL("layoutAboutToBeChanged()"))
    partDictionary = instructions.getPartDictionary()
    submodelDictionary = instructions.getSubmodelDictionary()
    
    filename = QString()
    stream >> filename
    instructions.filename = str(filename)

    CSI.scale = stream.readFloat()
    PLI.scale = stream.readFloat()

    # Read in the entire partOGL dictionary
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPartOGL(stream)
        partDictionary[part.filename] = part

    # Each partOGL can contain several parts, but those parts do
    # not have valid sub-partOGLs.  Create those now.
    for partOGL in partDictionary.values():
        for part in partOGL.parts:
            part.partOGL = partDictionary[part.filename]

    partCount = stream.readInt32()
    for i in range(0, partCount):
        model = __readSubmodel(stream, instructions)
        submodelDictionary[model.filename] = model

    instructions.mainModel = __readSubmodel(stream, instructions)

    for model in submodelDictionary.values():
        __linkModelPartNames(model)

    __linkModelPartNames(instructions.mainModel)

    for submodel in submodelDictionary.values():
        if submodel._parent == "":
            submodel._parent = instructions
        elif submodel._parent == filename:
            submodel._parent = instructions.mainModel
        else:
            submodel._parent = submodelDictionary[submodel._parent]

    instructions.initGLDisplayLists()
    instructions.emit(SIGNAL("layoutChanged()"))

def __readSubmodel(stream, instructions):

    submodel = __readPartOGL(stream, True)
    submodel.instructions = instructions

    pageCount = stream.readInt32()
    for i in range(0, pageCount):
        page = __readPage(stream, submodel, instructions)
        submodel.pages.append(page)

    filename = QString()
    submodelCount = stream.readInt32()
    for i in range(0, submodelCount):
        stream >> filename
        model = submodelDictionary[str(filename)]
        model.used = True
        submodel.submodels.append(model)

    submodel._row = stream.readInt32()
    stream >> filename
    submodel._parent = str(filename)
    return submodel

def __readPartOGL(stream, createSubmodel = False):
    filename = QString()
    name = QString()
    stream >> filename >> name

    part = Submodel() if createSubmodel else PartOGL()
    part.filename = str(filename)
    part.name = str(name)

    part.isPrimitive = stream.readBool()
    part.width = stream.readInt32()
    part.height = stream.readInt32()
    part.leftInset = stream.readInt32()
    part.bottomInset = stream.readInt32()
    stream >> part.center
    
    primitiveCount = stream.readInt32()
    for i in range(0, primitiveCount):
        p = __readPrimitive(stream)
        part.primitives.append(p)
        
    partCount = stream.readInt32()
    for i in range(0, partCount):
        p = __readPart(stream)
        part.parts.append(p)
    return part

def __readPrimitive(stream):
    invert = stream.readBool()
    color = stream.readInt32()
    type = stream.readInt16()
    count = 9 if type == GL.GL_TRIANGLES else 12
    points = []
    for i in range(0, count):
        points.append(stream.readFloat())
    return Primitive(color, points, type, invert)

def __readPart(stream):
    filename = QString()
    stream >> filename
    filename = str(filename)
    
    invert = stream.readBool()
    color = stream.readInt32()
    matrix = []

    for i in range(0, 16):
        matrix.append(stream.readFloat())
    
    useDisplacement = stream.readBool()
    if useDisplacement:
        displacement = [stream.readFloat(), stream.readFloat(), stream.readFloat()]
        displaceDirection = stream.readInt32()
        
    if filename == 'arrow':
        arrow = Arrow(displaceDirection)
        arrow.matrix = matrix
        return arrow
    
    part = Part(filename, color, matrix, invert, False)

    if useDisplacement:
        part.displacement = displacement
        part.displaceDirection = displaceDirection

    return part

def __readPage(stream, parent, instructions):
    pos = QPointF()
    rect = QRectF()
    font = QFont()
    pen = QPen()

    stream >> pos >> rect
    number = stream.readInt32()
    page = Page(parent, instructions, number)
    page.setPos(pos)
    page.setRect(rect)

    page._row = stream.readInt32()

    stream >> pos >> font
    page.numberItem.setPos(pos)
    page.numberItem.setFont(font)
    
    # Read in each step in this page
    stepCount = stream.readInt32()
    step = None
    for i in range(0, stepCount):
        step = __readStep(stream, page)
        page.addStep(step)

    # Read in the optional submodel preview image
    hasSubmodelItem = stream.readBool()
    if hasSubmodelItem:
        pixmap = QPixmap()
        childRow = stream.readInt32()
        stream >> pos >> rect >> pen
        stream >> pixmap
        
        page.addSubmodelImage(childRow)
        page.submodelItem.setPos(pos)
        page.submodelItem.setRect(rect)
        page.submodelItem.setPen(pen)
        page.submodelItem.children()[0].setPixmap(pixmap)

    # Read in any page separator lines
    borderCount = stream.readInt32()
    for i in range(0, borderCount):
        childRow = stream.readInt32()
        stream >> pos >> rect >> pen
        border = page.addStepSeparator(childRow)
        border.setPos(pos)
        border.setRect(rect)
        border.setPen(pen)

    return page

def __readStep(stream, parentPage):
    
    pos = QPointF()
    rect = QRectF()
    font = QFont()
    stream >> pos >> rect

    number = stream.readInt32()
    step = Step(parentPage, number)
    step.setPos(pos)
    step.setRect(rect)

    stream >> pos >> font
    step.numberItem.setPos(pos)
    step.numberItem.setFont(font)
    
    step.maxRect = QRectF()
    stream >> step.maxRect

    step.csi = __readCSI(stream, step)
    step.pli = __readPLI(stream, step)
    return step

def __readCSI(stream, step):
    csi = CSI(step)
    pos = QPointF()
    stream >> pos
    csi.setPos(pos)

    csi.width = stream.readInt32()
    csi.height = stream.readInt32()
    stream >> csi.center

    pixmap = QPixmap()
    stream >> pixmap
    csi.setPixmap(pixmap)

    global partDictionary, submodelDictionary
    partCount = stream.readInt32()
    for i in range(0, partCount):
        part = __readPart(stream)
        part.parentCSI = csi
        if part.filename in partDictionary:
            part.partOGL = partDictionary[part.filename]
        elif part.filename in submodelDictionary:
            part.partOGL = submodelDictionary[part.filename]
            part.partOGL.used = True
        elif part.filename != 'arrow':
            print "LOAD ERROR: could not find a partOGL for part: " + part.filename

        csi.parts.append(part)
        if part.filename == 'arrow':
            csi.arrows.append(part)
            part.setParentItem(csi)

    return csi

def __readPLI(stream, parentStep):
    pos = QPointF()
    rect = QRectF()
    pen = QPen()
    stream >> pos >> rect >> pen

    pli = PLI(parentStep)
    pli.setPos(pos)
    pli.setPen(pen)
    pli.setRect(rect)

    itemCount = stream.readInt32()
    for i in range(0, itemCount):
        pliItem = __readPLIItem(stream, pli)
        pli.pliItems.append(pliItem)

    # Link all the parts in the associated CSI with the parts in each PLIItem
    for part in parentStep.csi.parts:
        for item in pli.pliItems:
            if item.color == part.color and item.partOGL.filename == part.partOGL.filename:
                item.addPart(part)

    # Make sure we've added the right number of parts to the right spot
    for item in pli.pliItems:
        if item.__count == len(item.parts):
            del(item.__count)
        else:
            print "LOAD ERROR: Have PLIItem with %d count, but %d parts" % (item.__count, len(item.parts))

    return pli

def __readPLIItem(stream, pli):
    
    filename = QString()
    pos = QPointF()
    rect = QRectF()
    transform = QTransform()

    stream >> filename >> pos >> rect >> transform
    filename = str(filename)

    color = stream.readInt32()
    count = stream.readInt32()

    global partDictionary, submodelDictionary
    if filename in partDictionary:
        partOGL = partDictionary[filename]
    elif filename in submodelDictionary:
        partOGL = submodelDictionary[filename]
    else:
        print "LOAD ERROR: Could not find part in part dict: " + filename

    pliItem = PLIItem(pli, partOGL, color)
    pliItem.__count = count
    pliItem.setPos(pos)
    pliItem.setRect(rect)

    font = QFont()
    pixmap = QPixmap()
    stream >> pos >> font >> pixmap

    pliItem.numberItem.setPos(pos)
    pliItem.numberItem.setFont(font)
    pliItem.pixmapItem.setPixmap(pixmap)
    pliItem.numberItem.setZValue(pliItem.pixmapItem.zValue() + 1)
    pliItem.setTransform(transform)
    return pliItem

def __linkModelPartNames(model):

    global partDictionary, submodelDictionary

    for m in model.submodels:
        __linkModelPartNames(m)

    for part in model.parts:
        if part.filename in partDictionary:
            part.partOGL = partDictionary[part.filename]
        elif part.filename in submodelDictionary:
            part.partOGL = submodelDictionary[part.filename]
            part.partOGL.used = True
        else:
            print "LOAD ERROR: could not find a partOGL for part: " + part.filename