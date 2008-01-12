import math   # for sqrt
import os     # for output path creation

from OpenGL.GL import *
from OpenGL.GLU import *

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtOpenGL import *

import GLHelpers_qt

from LDrawFileFormat_qt import *
from LDrawColors import *

UNINIT_OGL_DISPID = -1
partDictionary = {}   # x = PartOGL("3005.dat"); partDictionary[x.filename] == x
GlobalGLContext = None
AllFlags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable

def genericItemParent(self):
    return self.parentItem()

def genericItemData(self, index = 0):
    return QVariant(self.dataText)

QGraphicsSimpleTextItem.parent = genericItemParent
QGraphicsSimpleTextItem.data = genericItemData
QGraphicsPixmapItem.parent = genericItemParent
QGraphicsPixmapItem.data = genericItemData
    
def printRect(rect, text = ""):
    print text + ", l: %f, r: %f, t: %f, b: %f" % (rect.left(), rect.right(), rect.top(), rect.bottom())

class Instructions(QAbstractItemModel):

    def __init__(self, parent, scene, glWidget, filename = None):
        QAbstractItemModel.__init__(self, parent)
        global GlobalGLContext
        
        # Part dimensions cache line format: filename width height center.x center.y leftInset bottomInset
        self.partDimensionsFilename = "PartDimensions.cache"
        
        self.filename = ""
        self.scene = scene
        GlobalGLContext = glWidget
        GlobalGLContext.makeCurrent()
        
        self.pages = []
        self.currentStep = None
	
	if filename:
	    self.filename = os.path.splitext(os.path.basename(filename))[0]
	    self.loadModel(filename)

    def data(self, index, role = Qt.DisplayRole):
        if not index.isValid():
            return QVariant(self.filename)

        if role != Qt.DisplayRole:
            return QVariant()

        item = index.internalPointer()

        return QVariant(item.data(0))

    def rowCount(self, parent = QModelIndex()):

        if parent.column() > 0:
            return 0

        if not parent.isValid():
            return len(self.pages)

        item = parent.internalPointer()
	if hasattr(item, "childCount"):
            return item.childCount()
        return 0

    def columnCount(self, parentIndex = QModelIndex()):
        return 1  # Every single item in the tree has exactly 1 column

    def flags(self, index):
        if not index.isValid():
            return 0
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def index(self, row, column, parent = QModelIndex()):
        if row < 0 or column < 0:
            return QModelIndex()

        if parent.isValid():
            parentItem = parent.internalPointer()
        else:
            parentItem = self

        if not hasattr(parentItem, "child"):
            return QModelIndex()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QModelIndex()

    def child(self, row):
        if row < 0 or row >= len(self.pages):
            return None
        return self.pages[row]

    def childCount(self):
        return len(self.pages)

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()
        
        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def headerData(self, section, orientation, role = Qt.DisplayRole):
        return QVariant()

    def loadModel(self, filename):
	self.filename = os.path.splitext(os.path.basename(filename))[0]
	self.importModel(filename)
	self.initDraw()  # generate all part GL display lists on the general glWidget
	self.pages[-1].hide()
	self.pages[0].show()
	
    def clear(self):
        global partDictionary
        self.currentStep = None
        for page in self.pages:
            item = self.scene.removeItem(page)
            del(item)
        self.pages = []
        partDictionary = {}
        Page.NextNumber = 1
        Step.NextNumber = 1
	GlobalGLContext.makeCurrent()
        
    def addPage(self, page):
    
        self.pages.append(page)
        
        for page in self.pages:
            page.hide()
    
        self.pages[-1].show()

    def importModel(self, filename):
        """ Reads in an LDraw model file and popluates this instruction book with the info. """
        
        ldrawFile = LDrawFile(filename)
        
        # Loop over the specified LDraw file array, skipping the first line
        for line in ldrawFile.fileArray[1:]:
            
            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return
            
            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):
        
        if isValidStepLine(line):
            self.addStep()
    
        elif isValidPartLine(line):
            self.addPart(lineToPart(line), line)
    
    def addStep(self):
        # For now, this implicitly adds a new page for each new step
        
        page = Page(self)
        self.addPage(page)
        self.currentStep = Step(page, self.currentStep)
        page.addStep(self.currentStep)

    def addPart(self, p, line):
        try:
            part = Part(p['filename'], p['color'], p['matrix'])
        except IOError:
            # TODO: This should be printed - commented out for debugging
            #print "Could not find file: %s - Ignoring." % p['filename']
            return
        
        if not self.currentStep:
            self.addStep()
        
        self.currentStep.addPart(part)
    
    def drawBuffer(self):
        global GlobalGLContext
    
        size = 300
        pBuffer = QGLPixelBuffer(size,  size, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()
        
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glShadeModel(GL_SMOOTH)
        
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        lightPos = [100.0, 500.0, -500.0]
        ambient = [0.2, 0.2, 0.2]
        diffuse = [0.8, 0.8, 0.8]
        specular = [0.5, 0.5, 0.5]
        
        glLightfv(GL_LIGHT0, GL_POSITION, lightPos)
        glLightfv(GL_LIGHT0, GL_AMBIENT, ambient)
        glLightfv(GL_LIGHT0, GL_DIFFUSE, diffuse)
        glLightfv(GL_LIGHT0, GL_SPECULAR, specular)

        glEnable(GL_DEPTH_TEST)
        glClearColor(1.0, 1.0, 1.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        GLHelpers_qt.adjustGLViewport(0, 0, size, size)
        GLHelpers_qt.rotateToPLIView()
        
        self.mainModel.draw()

        image = pBuffer.toImage()
        if image:
            print "have image"
            image.save("C:\\ldraw\\first_qt_render.png", None)
        
        GlobalGLContext.makeCurrent()
    
    def initDraw(self):
        
        # First initialize all GL display lists
        for part in partDictionary.values():
            part.createOGLDisplayList()
            
        # Calculate the width and height of each partOGL in the part dictionary
        self.initPartDimensionsManually()

        # Calculate the width and height of each CSI in this instruction book
        self.initCSIDimensions()
        
        # Layout each step on each page.  
        # TODO: This should only happen if we're importing a new model.  Otherwise, layout should be pulled from load / save binary blob
        for page in self.pages:
            for step in page.steps:
                step.initLayout()
    
    def initPartDimensionsManually(self):
        """
        Calculates each uninitialized part's display width and height.
        Creates GL buffer to render a temp copy of each part, then uses those raw pixels to determine size.
        Will append results to the part dimension cache file.
        """
        global GlobalGLContext
        
        partList = [part for part in partDictionary.values() if (not part.isPrimitive) and (part.width == part.height == -1)]
        
        if not partList:
            return    # If there's no parts to initialize, we're done here
    
        partList2 = []
        lines = []
        sizes = [128, 256, 512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels
        
        for size in sizes:
            
            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()
            
            # Render each image and calculate their sizes
            for partOGL in partList:
                
                if partOGL.initSize(size, pBuffer):  # Draw image and calculate its size:                    
                    lines.append(partOGL.dimensionsToString())
                else:
                    partList2.append(partOGL)
            
            if len(partList2) < 1:
                break  # All images initialized successfully
            else:
                partList = partList2  # Some images rendered out of frame - loop and try bigger frame
                partList2 = []
        
        # Append any newly calculated part dimensions to cache file
        print ""
        if lines:
            f = open(self.partDimensionsFilename, 'a')
            f.writelines(lines)
            f.close()
    
    def initCSIDimensions(self):
        global GlobalGLContext

        csiList = []
        for page in self.pages:
            for step in page.steps:
                csiList.append(step.csi)

        if csiList == []:
            return  # All CSIs initialized - nothing to do here
        
        GlobalGLContext.makeCurrent()
        for csi in csiList:
            csi.createOGLDisplayList()
            
        csiList2 = []
        sizes = [512, 1024, 2048] # Frame buffer sizes to try - could make configurable by user, if they've got lots of big submodels
        
        for size in sizes:
            
            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, QGLFormat(), GlobalGLContext)
            pBuffer.makeCurrent()

            # Render each CSI and calculate its size
            for csi in csiList:
                if not csi.initSize(size, pBuffer):
                    csiList2.append(csi)
            
            if len(csiList2) < 1:
                break  # All images initialized successfully
            else:
                csiList = csiList2  # Some images rendered out of frame - loop and try bigger frame
                csiList2 = []
    
    def selectItem(self, item):
	pass
    
    def writeToStream(self, stream):
        global partDictionary
        
        stream.writeInt32(len(partDictionary))
        for partOGL in partDictionary.values():
            partOGL.writeToStream(stream)
        
        stream.writeInt32(len(self.pages))
        for page in self.pages:
            page.writeToStream(stream)
            
    def readFromStream(self, stream, filename):
        global partDictionary
        
	self.filename = os.path.splitext(os.path.basename(filename))[0]
        partCount = stream.readInt32()
        for i in range(0, partCount):
            part = PartOGL.readFromStream(stream)
            partDictionary[part.filename] = part
            
        pageCount = stream.readInt32()
        for i in range(0, pageCount):
            page = Page.readFromStream(stream, self)
            self.addPage(page)
    
class Page(QGraphicsRectItem):
    """ A single page in an instruction book.  Contains one or more Steps. """
    
    NextNumber = 1
    inset = QPointF(15, 15)
    pageInset = 10
    
    def __init__(self, instructions, number = -1):
        QGraphicsRectItem.__init__(self, None, instructions.scene)
        
        # Position this rectangle inset from the containing scene
        rect = instructions.scene.sceneRect().adjusted(Page.pageInset, Page.pageInset, -Page.pageInset, -Page.pageInset)
        self.setRect(rect)
        
        self.instructions = instructions
        self.steps = []

        # Give this page a number
        if number == -1:
            self.number = Page.NextNumber
            Page.NextNumber += 1
        else:
            self.number = number
            Page.NextNumber = number + 1
        
        # Setup this page's page number
        self.numberItem = QGraphicsSimpleTextItem(str(self.number), self)
        self.numberItem.setFont(QFont("Arial", 15))
	self.numberItem.dataText = "Page Number Label"

        # Position page number in bottom right page corner
        rect = self.numberItem.boundingRect()
        rect.moveBottomRight(self.rect().bottomRight() - Page.inset)
        self.numberItem.setPos(rect.topLeft())
	self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
	self.numberItem.setFlags(AllFlags)
      
    def parent(self):
        return self.instructions

    def child(self, row):
        if row < 0 or row >= len(self.steps):
            return None
        return self.steps[row]

    def childCount(self):
        return len(self.steps)

    def row(self):
        return self.number - 1

    def data(self, index = 0):
        return QVariant("Page %d" % self.number)

    def addStep(self, step):       
        self.steps.append(step)

    def writeToStream(self, stream):
        stream << self.pos() << self.rect()
        stream.writeInt32(self.number)
        stream << self.numberItem.pos() << self.numberItem.font()
        stream.writeInt32(len(self.steps))
        for step in self.steps:
            step.writeToStream(stream)
    
    @staticmethod
    def readFromStream(stream, instructions):
	pos = QPointF()
	rect = QRectF()
	font = QFont()
	
	stream >> pos >> rect
	number = stream.readInt32()
	page = Page(instructions, number)
	page.setPos(pos)
	page.setRect(rect)
	
	stream >> pos >> font
	page.numberItem.setPos(pos)
	page.numberItem.setFont(font)
	
	stepCount = stream.readInt32()
	step = None
	for i in range(0, stepCount):
	    step = Step.readFromStream(stream, page, step)
	    page.steps.append(step)
	return page
    
    def paint(self, painter, option, widget = None):
        # Draw a slightly down-right translated black rectangle, for the page shadow effect
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawRect(self.rect().translated(3, 3))

        # Draw the page itself - white with a thin black border
        painter.setPen(QPen(Qt.black))
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(self.rect())
        
        # Draw a (debug) rect around the page number label
        rect = self.numberItem.boundingRect()
        rect.translate(self.numberItem.pos())
        painter.drawRect(rect)

	
class Step(QGraphicsRectItem):
    """ A single step in an instruction book.  Contains one optional PLI and exactly one CSI. """

    NextNumber = 1
    inset = QPointF(15.5, 15.5)
    
    def __init__(self, parentPage, prevStep, number = -1):
        QGraphicsRectItem.__init__(self, parentPage)
    
        self.page = parentPage
        self.prevStep = prevStep
        self.setPos(parentPage.rect().topLeft())
        
        # Give this page a number
        if number == -1:
            self.number = Step.NextNumber
            Step.NextNumber += 1
        else:
            self.number = number
            Step.NextNumber = number + 1
        
        # Initialize Step's number label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem(str(self.number), self)
        self.numberItem.setFont(QFont("Arial", 15))
	self.numberItem.setFlags(AllFlags)
	self.numberItem.dataText = "Step Number Label"
	self.setFlags(AllFlags)

        self.parts = []
        self.pli = PLI(self.pos() + Step.inset, self)
        self.csi = CSI(self)

    def parent(self):
        return self.page

    def child(self, row):
        if row == 0:
            return self.numberItem
        if row == 1:
            return self.pli
        if row == 2:
            return self.csi
        return None

    def childCount(self):
        return 3

    def row(self):
        return self.number - 1

    def data(self, index = 0):
        return QVariant("Step %d" % self.number)

    def addPart(self, part):
    
        self.parts.append(part)
        
        if self.pli:
            self.pli.addPart(part)

    def initLayout(self):
    
        print "initializing step: %d" % self.number
        self.pli.initLayout()
        self.csi.initLayout()
        
        # Position the Step number label beneath the PLI
        self.numberItem.setPos(self.pos() + Step.inset)
        self.numberItem.moveBy(0, self.pli.rect().height() + Step.inset.y() + 0.5)
        
        """
        # Ensure all sub model PLIs and steps are also initialized
        for part in self.parts:
            for page in part.partOGL.pages:
                for step in page.steps:
                    step.initLayout(context)
        
        # Tell this step's CSI about the PLI, so it can center itself vertically better
        if self.csi.fileLine is None:
            self.csi.offsetPLI = topGap
            self.csi.resize()
        """
    
    def writeToStream(self, stream):
        stream << self.pos() << self.rect()
        stream.writeInt32(self.number)
        stream << self.numberItem.pos() << self.numberItem.font()
        self.csi.writeToStream(stream)
        self.pli.writeToStream(stream)
        stream.writeInt32(len(self.parts))
        for part in self.parts:
            part.writeToStream(stream)        
        
    @staticmethod
    def readFromStream(stream, parentPage, prevPage):
	pos = QPointF()
	rect = QRectF()
	font = QFont()
	stream >> pos >> rect
	
	number = stream.readInt32()
	step = Step(parentPage, prevPage, number)
	step.setPos(pos)
	step.setRect(rect)
	
	stream >> pos >> font
	step.numberItem.setPos(pos)
	step.numberItem.setFont(font)
	
	step.csi = CSI.readFromStream(stream, step)
	step.pli = PLI.readFromStream(stream, step)
	
	partCount = stream.readInt32()
	for i in range(0, partCount):
	    part = Part.readFromStream(stream)
	    part.partOGL = partDictionary[part.filename]
	    step.parts.append(part)
	return step
    
    def paint(self, painter, option, widget = None):
        rect = self.numberItem.boundingRect()
        rect.translate(self.numberItem.pos())
        painter.drawRect(rect)
        QGraphicsRectItem.paint(self, painter, option, widget)
    
class PLIItem(QGraphicsRectItem):
    """ Represents one part inside a PLI along with its quantity label. """

    def __init__(self, parent, partOGL, color):
        QGraphicsRectItem.__init__(self, parent)
	
        self.partOGL = partOGL
        self.color = color
        self._count = 1
        
        # Initialize the quantity label (position set in initLayout)
        self.numberItem = QGraphicsSimpleTextItem(str(self._count), self)
        self.numberItem.setFont(QFont("Arial", 10))

        self.pixmapItem = QGraphicsPixmapItem(self)
        self.pixmapItem.dataText = "Image"

        self.setPos(parent.inset)
	self.setFlags(AllFlags)
	self.numberItem.setFlags(AllFlags)
	self.pixmapItem.setFlags(AllFlags)

    def parent(self):
        return self.parentItem()

    def child(self, row):
        if row == 0:
            return self.pixmapItem
        if row == 1:
            return self.numberItem
        return None
      
    def childCount(self):
        return 2

    def row(self):
        pli = self.parentItem()
        for index, item in enumerate(pli.pliItems):
            if item is self:
                return index
        return 0

    def data(self, index = 0):
        return QVariant("%s - %s" % (self.partOGL.name, getColorName(self.color)))

    def paint(self, painter, option, widget = None):
#        rect = self.numberItem.boundingRect()
#        rect.translate(self.numberItem.pos())
#        painter.drawRect(rect)
#        QGraphicsRectItem.paint(self, painter, option, widget)
        pass

    def initLayout(self):
    
        part = self.partOGL
        lblHeight = self.numberItem.boundingRect().height() / 2.0
        
        # Set this item to the same width & height as its part image
        self.setRect(0, 0, part.width, part.height)
        
        # Position quantity label based on part corner, empty corner triangle and label's size
        if part.leftInset == part.bottomInset == 0:
            dx = -3   # Bottom left triangle is full - shift just a little, for a touch more padding
        else:
            slope = part.leftInset / float(part.bottomInset)
            dx = ((part.leftInset - lblHeight) / slope) - 3  # 3 for a touch more padding

        self.numberItem.setPos(dx, self.rect().height() - lblHeight)

	# TODO: getPixmap can return None; trying to set a pixmap to None crashes... handle...
	pixmap = part.getPixmap(self.color)
	if pixmap:
	    self.pixmapItem.setPixmap(pixmap)
	    
	self.numberItem.setZValue(self.pixmapItem.zValue() + 1)

    def _setCount(self, count):
        self._count = count
        self.numberItem.setText("x%d" % self._count)
        self.numberItem.dataText = "Qty. Label (x%d)" % self._count

    def _getCount(self):
        return self._count
    
    count = property(fget = _getCount, fset = _setCount)
    
    def writeToStream(self, stream):
        stream << QString(self.partOGL.filename) << self.pos() << self.rect()
        stream.writeInt32(self.color)
        stream.writeInt32(self.count)
        stream << self.numberItem.pos() << self.numberItem.font() << self.pixmapItem.pixmap()
	
    @staticmethod
    def readFromStream(stream, pli):
	filename = QString()
	pos = QPointF()
	rect = QRectF()
	stream >> filename >> pos >> rect
	filename = str(filename)
	
	color = stream.readInt32()
	count = stream.readInt32()

	if filename in partDictionary:
	    partOGL = partDictionary[filename]
	else:
	    print "LOAD ERROR: Could not find part in part dict: " + filename
	pliItem = PLIItem(pli, partOGL, color)
	pliItem.count = count
	pliItem.setPos(pos)
	pliItem.setRect(rect)
	
	font = QFont()
	pixmap = QPixmap()
	stream >> pos >> font >> pixmap
	
	pliItem.numberItem.setPos(pos)
	pliItem.numberItem.setFont(font)
	pliItem.pixmapItem.setPixmap(pixmap)
	pliItem.numberItem.setZValue(pliItem.pixmapItem.zValue() + 1)
	return pliItem
    
class PLI(QGraphicsRectItem):
    """ Parts List Image.  Includes border and layout info for a list of parts in a step. """
    
    inset = QPointF(15, 15)
    
    def __init__(self, pos, parent):
        QGraphicsRectItem.__init__(self, parent)
        
        self.setPos(pos)
        self.setPen(QPen(Qt.black))
        self.pliItems = []  # {(part filename, color): PLIItem instance}
	self.setFlags(AllFlags)

    def parent(self):
        return self.parentItem()

    def child(self, row):
        if row < 0 or row >= len(self.pliItems):
            return None
        return self.pliItems[row] 

    def childCount(self):
        return len(self.pliItems)

    def row(self):
        return 1

    def data(self, index = 0):
        return QVariant("PLI")

    def isEmpty(self):
        return True if len(self.pliItems) == 0 else False

    def addPart(self, part):
      
        found = False
        for item in self.pliItems:
            if item.color == part.color and item.filename == part.partOGL.filename:
                item.count += 1
                found = True
                break
        if not found:
            item = PLIItem(self, part.partOGL, part.color)
            item.setParentItem(self)
            self.pliItems.append(item)
    
    def initLayout(self):
        """ 
        Allocate space for all parts in this PLI, and choose a decent layout.
        """

        # If this PLI is empty, nothing to do here
        if len(self.pliItems) < 1:
            return
        
        # Initialize each item in this PLI, so they have good rects and properly positioned quantity labels
	for item in self.pliItems:
            item.initLayout()
    
        # Return the height of the part in the specified layout item
        def itemHeight(layoutItem):
            return layoutItem.partOGL.height
        
        # Compare the width of layout Items 1 and 2
        def compareLayoutItemWidths(item1, item2):
            """ Returns 1 if part 2 is wider than part 1, 0 if equal, -1 if narrower. """
            if item1.partOGL.width < item2.partOGL.width:
                return 1
            if item1.partOGL.width == item2.partOGL.width:
                return 0
            return -1
        
        # Sort the list of parts in this PLI from widest to narrowest, with the tallest one first
        partList = self.pliItems
        tallestPart = max(partList, key=itemHeight)
        partList.remove(tallestPart)
        partList.sort(compareLayoutItemWidths)
        partList.insert(0, tallestPart)
        
        b = self.rect()
        inset = PLI.inset.x()
        overallX = inset
        b.setSize(QSizeF(-1, -1))
        
        for i, item in enumerate(partList):
            
            # Move this PLIItem to its new position
            item.setPos(overallX, inset)
            
            # Check if the current PLI box is big enough to fit this part *below* the previous part,
            # without making the box any bigger.  If so, position part there instead.
            newWidth = item.rect().width()
            if i > 0:
                prevItem = partList[i-1]
                remainingHeight = b.height() - inset - inset - prevItem.rect().height()
                if item.rect().height() < remainingHeight:
                    overallX = prevItem.pos().x()
                    newWidth = prevItem.rect().width()
                    x = overallX + (newWidth - item.rect().width())
                    y = prevCorner.y + b.internalGap + item.rect().height()
                    item.setPos(x, y)
            
            # Increase overall x, box width and box height to make PLI box big enough for this part
            overallX += newWidth + inset
            b.setWidth(round(overallX))
            
            lblHeight = item.numberItem.boundingRect().height() / 2.0
            newHeight = item.rect().height() + lblHeight + (inset * 2)
            b.setHeight(round(max(b.height(), newHeight)))
            self.setRect(b)
            
    def writeToStream(self, stream):
        stream << self.pos() << self.rect() << self.pen()
        stream.writeInt32(len(self.pliItems))
	for item in self.pliItems:
            item.writeToStream(stream)
	    
    @staticmethod
    def readFromStream(stream, parentStep):
	pos = QPointF()
	rect = QRectF()
	pen = QPen()
	stream >> pos >> rect >> pen
	
	pli = PLI(pos, parentStep)
	pli.setPen(pen)
	pli.setRect(rect)
	
	itemCount = stream.readInt32()
	for i in range(0, itemCount):
	    pliItem = PLIItem.readFromStream(stream, pli)
	    pli.pliItems.append(pliItem)
	return pli

class CSI(QGraphicsPixmapItem):
    """
    Construction Step Image.  Includes border and positional info.
    """

    def __init__(self, step):
        QGraphicsPixmapItem.__init__(self, step)
        
        self.step = step
        self.center = QPointF()
        self.width = self.height = UNINIT_OGL_DISPID
        self.oglDispID = UNINIT_OGL_DISPID
        self.partialGLDispID = UNINIT_OGL_DISPID
	self.setFlags(AllFlags)
   
    def parent(self):
        return self.step

    def data(self, index = 0):
        return QVariant("CSI")

    def callPreviousOGLDisplayLists(self):
        
        if self.oglDispID == UNINIT_OGL_DISPID:
            # TODO: remove this check once all is well
            print "Trying to call previous CSI that has no display list"
            return

        # Call all previous step's CSI display list
        if self.step.prevStep:
            self.step.prevStep.csi.callPreviousOGLDisplayLists()
        
        # Now call this CSI's display list
        glCallList(self.partialGLDispID)

    def createOGLDisplayList(self):
        
        # Ensure all parts in this step have proper display lists
        # TODO: remove this check once all is well
        for part in self.step.parts:
            if part.partOGL.oglDispID == UNINIT_OGL_DISPID:
                part.partOGL.createOGLDisplayList()
        
        # Create a display list for just the parts in this CSI
        self.partialGLDispID = glGenLists(1)
        glNewList(self.partialGLDispID, GL_COMPILE)

        for part in self.step.parts:
            part.callOGLDisplayList()
            
        glEndList()
        
        # Create a display list that includes all previous CSIs plus this one,
        # for a single display list giving a full model rendering up to this step.
        self.oglDispID = glGenLists(1)
        glNewList(self.oglDispID, GL_COMPILE)
        self.callPreviousOGLDisplayLists()
        glEndList()

    def initLayout(self):
        x = (self.step.page.rect().width() / 2.0) - (self.width / 2.0)
        pliBottom = self.step.pli.rect().bottom() + self.step.pli.pos().y()
        y = pliBottom + ((self.step.page.rect().height() - pliBottom) / 2.0) - (self.height / 2.0)
        self.setOffset(x, y)
        
    def initSize(self, size, pBuffer):
        """
        Initialize this CSI's display width, height and center point. To do
        this, draw this CSI to the already initialized GL Frame Buffer Object.
        These dimensions are required to properly lay out PLIs and CSIs.
        Note that an appropriate FBO *must* be initialized before calling initSize.
        
        Parameters:
            size: Width & height of FBO to render to, in pixels.  Note that FBO is assumed square.
        
        Returns:
            True if CSI rendered successfully.
            False if the CSI has been rendered partially or wholly out of frame.
        """
        
        if self.oglDispID == UNINIT_OGL_DISPID:
            print "Trying to init a CSI size that has no display list"
            return
        
        rawFilename = self.step.page.instructions.filename
        filename = "%s_step_%d" % (rawFilename, self.step.number)
        
        params = GLHelpers_qt.initImgSize(size, size, self.oglDispID, True, filename, None, pBuffer)
        if params is None:
            return False
        
        # TODO: update some kind of load status bar her - this function is *slow*
        print "CSI %s step %d - size %d" % (filename, self.step.number, size)
        self.width, self.height, self.center, x, y = params
        self.initPixmap()
        return True

    def initPixmap(self):
        global GlobalGLContext
        
        pBuffer = QGLPixelBuffer(self.width, self.height, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()
        
        GLHelpers_qt.initFreshContext()
        GLHelpers_qt.adjustGLViewport(0, 0, self.width, self.height)
        GLHelpers_qt.rotateToDefaultView(self.center.x(), self.center.y(), 0.0)
        
        glCallList(self.oglDispID)

        image = pBuffer.toImage()
        self.setPixmap(QPixmap.fromImage(image))
        GlobalGLContext.makeCurrent()

    def boundingRect(self):
        return QRectF(self.offset().x(), self.offset().y(), self.width, self.height)
            
    def keyReleaseEvent(self, event = None):
	offset = 1
	if event.modifiers() & Qt.ShiftModifier:
	    if event.modifiers() & Qt.ControlModifier:
		offset = 20
	    else:
		offset = 5
	if event.key() == Qt.Key_Left:
	    self.moveBy(-offset, 0)
	elif event.key() == Qt.Key_Right:
	    self.moveBy(offset, 0)
	elif event.key() == Qt.Key_Up:
	    self.moveBy(0, -offset)
	elif event.key() == Qt.Key_Down:
	    self.moveBy(0, offset)
	
    def writeToStream(self, stream):
        stream << self.offset()
        stream.writeInt32(self.width)
        stream.writeInt32(self.height)
        stream << self.center
        stream << self.pixmap()

    @staticmethod
    def readFromStream(stream, step):
	csi = CSI(step)
	offset = QPointF()
	stream >> offset
	csi.setOffset(offset)
	
	csi.width = stream.readInt32()
	csi.height = stream.readInt32()
	stream >> csi.center
	
	pixmap = QPixmap()
	stream >> pixmap
	csi.setPixmap(pixmap)
	return csi

class PartOGL(object):
    """
    Represents one 'abstract' part.  Could be regular part, like 2x4 brick, could be a 
    simple primitive, like stud.dat.  
    Used inside 'concrete' Part below. One PartOGL instance will be shared across several 
    Part instances.  In other words, PartOGL represents everything that two 2x4 bricks have
    in common when present in a model, everything inside 3001.dat.
    """
    
    def __init__(self, filename = None, loadFromFile = False):
        
        self.name = self.filename = filename
        self.inverted = False  # TODO: Fix this! inverted = GL_CW
        self.invertNext = False
        self.parts = []
        self.primitives = []
        self.oglDispID = UNINIT_OGL_DISPID
        self.isPrimitive = False  # primitive here means any file in 'P'
        
        self.width = self.height = -1
        self.leftInset = self.bottomInset = -1
        self.center = QPointF()
        
        if filename and loadFromFile:
            self.loadFromFile()
    
    def loadFromFile(self):
        
        ldrawFile = LDrawFile(self.filename)
        self.isPrimitive = ldrawFile.isPrimitive
        self.name = ldrawFile.name
        
        # Loop over the specified LDraw file array, skipping the first line
        for line in ldrawFile.fileArray[1:]:
            
            # A FILE line means we're finished loading this model
            if isValidFileLine(line):
                return
            
            self._loadOneLDrawLineCommand(line)

    def _loadOneLDrawLineCommand(self, line):
        
        if isValidPartLine(line):
            self.addPart(lineToPart(line), line)
        
        elif isValidTriangleLine(line):
            self.addPrimitive(lineToTriangle(line), GL_TRIANGLES)
        
        elif isValidQuadLine(line):
            self.addPrimitive(lineToQuad(line), GL_QUADS)
        
    def addPart(self, p, line):
        try:
            part = Part(p['filename'], p['color'], p['matrix'])
        except IOError:
            # TODO: This should be printed - commented out for debugging
            #print "Could not find file: %s - Ignoring." % p['filename']
            return
        
        self.parts.append(part)
    
    def addPrimitive(self, p, shape):
        primitive = Primitive(p['color'], p['points'], shape, self.inverted ^ self.invertNext)
        self.primitives.append(primitive)
    
    def createOGLDisplayList(self):
        """ Initialize this part's display list.  Expensive call, but called only once. """
        if self.oglDispID != UNINIT_OGL_DISPID:
            return
        
        # Ensure any parts in this part have been initialized
        for part in self.parts:
            if part.partOGL.oglDispID == UNINIT_OGL_DISPID:
                part.partOGL.createOGLDisplayList()
        
        self.oglDispID = glGenLists(1)
        glNewList(self.oglDispID, GL_COMPILE)
        
        for part in self.parts:
            part.callOGLDisplayList()
        
        for primitive in self.primitives:
            primitive.callOGLDisplayList()
        
        glEndList()

    def draw(self):
        glCallList(self.oglDispID)
    
    def dimensionsToString(self):
        if self.isPrimitive:
            return ""
        return "%s %d %d %d %d %d %d\n" % (self.filename, self.width, self.height, self.center.x(), self.center.y(), self.leftInset, self.bottomInset)

    def initSize(self, size, pBuffer):
        """
        Initialize this part's display width, height, empty corner insets and center point.
        To do this, draw this part to the already initialized GL buffer.
        These dimensions are required to properly lay out PLIs and CSIs.
        
        Parameters:
            size: Width & height of GL buffer to render to, in pixels.  Note that buffer is assumed square
        
        Returns:
            True if part rendered successfully.
            False if the part has been rendered partially or wholly out of frame.
        """
        
        # TODO: If a part is rendered at a size > 256, draw it smaller in the PLI - this sounds like a great way to know when to shrink a PLI image...
        # TODO: Check how many pieces would be rendered successfully at 128 - if significant, test adding that to size list, see if it speeds part generation up
        if self.isPrimitive:
            return True  # Primitive parts need not be sized
        
        params = GLHelpers_qt.initImgSize(size, size, self.oglDispID, False, self.filename, None, pBuffer)
        if params is None:
            return False
        
        # TODO: update some kind of load status bar here - this function is *slow*
        print self.filename + " - size: %d" % (size)
        
        self.width, self.height, self.center, self.leftInset, self.bottomInset = params
        return True

    def getPixmap(self, color = 0):
        global GlobalGLContext

        if self.isPrimitive:
            return None  # Do not generate any pixmaps for primitives
        
        pBuffer = QGLPixelBuffer(self.width, self.height, QGLFormat(), GlobalGLContext)
        pBuffer.makeCurrent()
        
        GLHelpers_qt.initFreshContext()
        GLHelpers_qt.adjustGLViewport(0, 0, self.width, self.height)
        GLHelpers_qt.rotateToPLIView(self.center.x(), self.center.y(), 0.0)
        
        color = convertToRGBA(color)
        if len(color) == 3:
            glColor3fv(color)
        elif len(color) == 4:
            glColor4fv(color)
        
        self.draw()

        image = pBuffer.toImage()
        if image:
            image.save("C:\\ldraw\\tmp\\buffer_%s.png" % self.filename, None)
    
        pixmap = QPixmap.fromImage(image)
        GlobalGLContext.makeCurrent()
        return pixmap
    
    def writeToStream(self, stream):
        
        stream << QString(self.filename) << QString(self.name)
        stream.writeBool(self.isPrimitive)
        stream.writeInt32(self.width)
        stream.writeInt32(self.height)
        stream.writeInt32(self.leftInset)
        stream.writeInt32(self.bottomInset)
        stream << self.center
        stream.writeInt32(len(self.primitives))
        for primitive in self.primitives:
            primitive.writeToStream(stream)
        stream.writeInt32(len(self.parts))
        for part in self.parts:
            part.writeToStream(stream)

    @staticmethod
    def readFromStream(stream):
	filename = QString()
	name = QString()
        stream >> filename >> name
	
	part = PartOGL()
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
	    p = Primitive.readFromStream(stream)
	    part.primitives.append(p)
	partCount = stream.readInt32()
	for i in range(0, partCount):
	    p = Part.readFromStream(stream)
	    p.partOGL = part
	    part.parts.append(p)
	return part

class Part:
    """
    Represents one 'concrete' part, ie, an 'abstract' part (partOGL), plus enough
    info to draw that abstract part in context of a model, ie color, positional 
    info, containing buffer state, etc.  In other words, Part represents everything
    that could be different between two 2x4 bricks in a model, everything contained
    in one LDraw FILE (5) command.
    """
    
    def __init__(self, filename, color = 16, matrix = None, invert = False, setPartOGL = True):
        
        self.filename = filename
        self.color = color
        self.matrix = matrix
        self.inverted = invert
        
        if setPartOGL:
	    if filename in partDictionary:
		self.partOGL = partDictionary[filename]
	    else:
		self.partOGL = partDictionary[filename] = PartOGL(filename, loadFromFile = True)        
            self.name = self.partOGL.name

    def callOGLDisplayList(self):
        
        # must be called inside a glNewList/EndList pair
        color = convertToRGBA(self.color)
        
        if color != CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            if len(color) == 3:
                glColor3fv(color)
            elif len(color) == 4:
                glColor4fv(color)
        
        if self.inverted:
            glPushAttrib(GL_POLYGON_BIT)
            glFrontFace(GL_CW)
        
        if self.matrix:
            glPushMatrix()
            glMultMatrixf(self.matrix)
            
        glCallList(self.partOGL.oglDispID)
        
        if self.matrix:
            glPopMatrix()
        
        if self.inverted:
            glPopAttrib()
        
        if color != CurrentColor:
            glPopAttrib()

    def draw(self):
        self.partOGL.draw()
    
    def writeToStream(self, stream):
        stream << QString(self.partOGL.filename)
        stream.writeBool(self.inverted)
        stream.writeInt32(self.color)
        assert len(self.matrix) == 16
        for point in self.matrix:
            stream.writeFloat(point)

    @staticmethod
    def readFromStream(stream):
	filename = QString()
	stream >> filename
	invert = stream.readBool()
	color = stream.readInt32()
	matrix = []
	for i in range(0, 16):
	    matrix.append(stream.readFloat())
	return Part(str(filename), color, matrix, invert, False)
    
class Primitive:
    """
    Not a primitive in the LDraw sense, just a single line/triangle/quad.
    Used mainly to construct an OGL display list for a set of points.
    """
    
    def __init__(self, color, points, type, invert = True):
        self.color = color
        self.type = type
        self.points = points
        self.inverted = invert

    def writeToStream(self, stream):
        stream.writeBool(self.inverted)
        stream.writeInt32(self.color)
        stream.writeInt16(self.type)

        if self.type == GL_QUADS:
            assert len(self.points) == 12
        elif self.type == GL_TRIANGLES:
            assert len(self.points) == 9
            
        for point in self.points:
            stream.writeFloat(point)

    @staticmethod
    def readFromStream(stream):
	invert = stream.readBool()
	color = stream.readInt32()
	type = stream.readInt16()
	count = 9 if type == GL_TRIANGLES else 12
	points = []
	for i in range(0, count):
	    points.append(stream.readFloat())
	return Primitive(color, points, type, invert)
    
    # TODO: using numpy for all this would probably work a lot better
    def addNormal(self, p1, p2, p3):
        Bx = p2[0] - p1[0]
        By = p2[1] - p1[1]
        Bz = p2[2] - p1[2]
        
        Cx = p3[0] - p1[0]
        Cy = p3[1] - p1[1]
        Cz = p3[2] - p1[2]
        
        Ax = (By * Cz) - (Bz * Cy)
        Ay = (Bz * Cx) - (Bx * Cz)
        Az = (Bx * Cy) - (By * Cx)
        l = math.sqrt((Ax*Ax)+(Ay*Ay)+(Az*Az))
        if l != 0:
            Ax /= l
            Ay /= l
            Az /= l
        return [Ax, Ay, Az]
    
    def callOGLDisplayList(self):
        
        # must be called inside a glNewList/EndList pair
        color = convertToRGBA(self.color)
        
        if color != CurrentColor:
            glPushAttrib(GL_CURRENT_BIT)
            if len(color) == 3:
                glColor3fv(color)
            elif len(color) == 4:
                glColor4fv(color)
        
        p = self.points
        
        if self.inverted:
            normal = self.addNormal(p[6:9], p[3:6], p[0:3])
            #glBegin( GL_LINES )
            #glVertex3f(p[3], p[4], p[5])
            #glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #glEnd()
            
            glBegin( self.type )
            glNormal3fv(normal)
            if self.type == GL_QUADS:
                glVertex3f( p[9], p[10], p[11] )
            glVertex3f( p[6], p[7], p[8] )
            glVertex3f( p[3], p[4], p[5] )
            glVertex3f( p[0], p[1], p[2] )
            glEnd()
        else:
            normal = self.addNormal(p[0:3], p[3:6], p[6:9])
            #glBegin( GL_LINES )
            #glVertex3f(p[3], p[4], p[5])
            #glVertex3f(p[3] + normal[0], p[4] + normal[1], p[5] + normal[2])
            #glEnd()
            
            glBegin( self.type )
            glNormal3fv(normal)
            glVertex3f( p[0], p[1], p[2] )
            glVertex3f( p[3], p[4], p[5] )
            glVertex3f( p[6], p[7], p[8] )
            if self.type == GL_QUADS:
                glVertex3f( p[9], p[10], p[11] )
            glEnd()
        
        if color != CurrentColor:
            glPopAttrib()